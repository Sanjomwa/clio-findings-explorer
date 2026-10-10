import pytest
from sqlalchemy import text

from app.seed.__main__ import run
from tests.integration.conftest import FIXTURE_CONTENT, NO_CONTENT, REAL_SNAPSHOT

COUNTS = {
    "regime_weeks": 1523,
    "acled_signal_context": 85,
    "ooni_weekly_signals": 550,
    "google_transparency_requests": 85,
}


def scalar(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar_one()


def test_real_snapshot_row_counts(seeded_engine):
    for table, expected in COUNTS.items():
        assert scalar(seeded_engine, f"SELECT count(*) FROM {table}") == expected
    assert scalar(seeded_engine, "SELECT count(*) FROM snapshot_tables") == 4
    assert scalar(seeded_engine, "SELECT count(*) FROM findings") == 0


def test_snapshot_meta(seeded_engine):
    assert scalar(seeded_engine, "SELECT version FROM snapshot_meta") == "2026-10-10.1"
    assert str(scalar(seeded_engine, "SELECT acled_access_date FROM snapshot_meta")) == "2026-03-26"
    assert scalar(seeded_engine, "SELECT manifest->>'version' FROM snapshot_meta") == "2026-10-10.1"


def test_null_columns_stored_as_null(seeded_engine):
    assert (
        scalar(seeded_engine, "SELECT count(*) FROM regime_weeks WHERE velocity_band IS NULL") == 1
    )
    assert (
        scalar(seeded_engine, "SELECT count(*) FROM regime_weeks WHERE conversion_band IS NULL")
        == 602
    )


def test_second_run_is_idempotent(seeded_engine):
    before = scalar(seeded_engine, "SELECT loaded_at FROM snapshot_meta")
    lines = run(REAL_SNAPSHOT, NO_CONTENT, engine=seeded_engine)
    assert "snapshot already loaded" in lines
    assert "no content/ directory: 0 findings" in lines
    assert scalar(seeded_engine, "SELECT loaded_at FROM snapshot_meta") == before
    for table, expected in COUNTS.items():
        assert scalar(seeded_engine, f"SELECT count(*) FROM {table}") == expected


def test_content_sync_and_removal(seeded_engine, tmp_path):
    lines = run(REAL_SNAPSHOT, FIXTURE_CONTENT, engine=seeded_engine)
    assert "findings loaded: 1" in lines
    assert scalar(seeded_engine, "SELECT count(*) FROM finding_caveats") == 2
    # Re-running replaces caveats rather than duplicating them.
    run(REAL_SNAPSHOT, FIXTURE_CONTENT, engine=seeded_engine)
    assert scalar(seeded_engine, "SELECT count(*) FROM finding_caveats") == 2
    # A content/findings directory with no files removes the finding.
    (tmp_path / "findings").mkdir()
    run(REAL_SNAPSHOT, tmp_path, engine=seeded_engine)
    assert scalar(seeded_engine, "SELECT count(*) FROM findings") == 0
    assert scalar(seeded_engine, "SELECT count(*) FROM finding_caveats") == 0


def test_reload_that_would_orphan_a_finding_fails_cleanly(seeded_engine, snapshot_copy):
    from app.seed import SeedError

    run(REAL_SNAPSHOT, FIXTURE_CONTENT, engine=seeded_engine)
    # The fixture snapshot has a different version and lacks the finding's week.
    with pytest.raises(SeedError, match="findings reference"):
        run(snapshot_copy, FIXTURE_CONTENT, engine=seeded_engine)
    assert scalar(seeded_engine, "SELECT count(*) FROM regime_weeks") == 1523
    assert scalar(seeded_engine, "SELECT version FROM snapshot_meta") == "2026-10-10.1"
