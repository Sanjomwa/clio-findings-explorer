from sqlalchemy import inspect, text

from alembic import command
from tests.integration.conftest import alembic_config

EXPECTED = {
    "regime_weeks", "acled_signal_context", "ooni_weekly_signals",
    "google_transparency_requests", "snapshot_meta", "snapshot_tables",
    "findings", "finding_caveats",
}  # fmt: skip


def tables(engine):
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_downgrade_upgrade(empty_engine):
    config = alembic_config(empty_engine)
    command.upgrade(config, "head")
    assert tables(empty_engine) == EXPECTED
    command.downgrade(config, "base")
    assert tables(empty_engine) == set()
    with empty_engine.connect() as conn:
        left = conn.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'enforce_finding_has_caveat'")
        ).scalar_one()
    assert left == 0
    command.upgrade(config, "head")
    assert tables(empty_engine) == EXPECTED


def test_snapshot_meta_allows_only_one_row(migrated_engine):
    import pytest
    from sqlalchemy.exc import IntegrityError

    insert = text(
        "INSERT INTO snapshot_meta (version, exported_at, acled_access_date, manifest) "
        "VALUES (:v, now(), '2026-03-26', '{}')"
    )
    with migrated_engine.begin() as conn:
        conn.execute(insert, {"v": "a"})
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(insert, {"v": "b"})
