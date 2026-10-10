import json
from datetime import UTC, date, datetime

import pytest

from app.seed import SeedError
from app.seed.__main__ import run
from app.seed.snapshot import FILE_MODELS, cast_row, load_manifest, read_rows, verify_snapshot


class NoDatabase:
    """Stands in for an engine: any attempt to open a transaction fails the test."""

    def begin(self):
        raise AssertionError("the database was touched")


def test_fixture_snapshot_verifies(snapshot_copy):
    verify_snapshot(snapshot_copy, load_manifest(snapshot_copy))


def test_checksum_mismatch_fails_and_writes_nothing(snapshot_copy, tmp_path):
    path = snapshot_copy / "regime_weeks.ndjson"
    path.write_bytes(path.read_bytes().replace(b"KE", b"KX", 1))
    with pytest.raises(SeedError, match=r"regime_weeks.ndjson: sha256"):
        run(snapshot_copy, tmp_path / "no-content", engine=NoDatabase())


def test_unlisted_extra_file_fails_and_writes_nothing(snapshot_copy, tmp_path):
    (snapshot_copy / "extra.ndjson").write_text("{}\n")
    with pytest.raises(SeedError, match=r"extra.ndjson: present .* not in the manifest"):
        run(snapshot_copy, tmp_path / "no-content", engine=NoDatabase())


def test_row_count_mismatch_fails_and_writes_nothing(snapshot_copy, tmp_path):
    manifest_path = snapshot_copy / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"][0]["row_count"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(SeedError, match=r"manifest row_count is"):
        run(snapshot_copy, tmp_path / "no-content", engine=NoDatabase())


def test_missing_file_fails(snapshot_copy):
    (snapshot_copy / "ooni_weekly_signals.ndjson").unlink()
    with pytest.raises(SeedError, match=r"ooni_weekly_signals.ndjson: listed .* missing"):
        verify_snapshot(snapshot_copy, load_manifest(snapshot_copy))


@pytest.mark.parametrize("file", sorted(FILE_MODELS))
def test_one_row_per_table_casts(snapshot_copy, file):
    rows = read_rows(snapshot_copy, file)
    assert len(rows) == 2
    model = FILE_MODELS[file]
    assert set(rows[0]) == {c.name for c in model.__table__.columns}


def test_regime_week_types(snapshot_copy):
    row = read_rows(snapshot_copy, "regime_weeks.ndjson")[0]
    assert row["week_start_date"] == date(1997, 1, 11)
    assert row["computed_at"] == datetime(2026, 6, 25, 2, 24, 25, tzinfo=UTC)
    assert row["transition_detected"] is False
    assert isinstance(row["regime_duration_weeks"], int)
    assert row["velocity_band"] is None


def test_float_and_nulls_cast(snapshot_copy):
    rows = read_rows(snapshot_copy, "ooni_weekly_signals.ndjson")
    assert all(isinstance(r["blocked_rate"], float) for r in rows)
    assert any(r["anomalous_zscore_12w"] is None for r in rows)


def test_null_in_not_null_column_rejected(snapshot_copy):
    row = json.loads(
        (snapshot_copy / "google_transparency_requests.ndjson").read_text().splitlines()[0]
    )
    row["reason"] = None
    with pytest.raises(SeedError, match="NOT NULL"):
        cast_row(FILE_MODELS["google_transparency_requests.ndjson"], row)


def test_wrong_json_type_rejected(snapshot_copy):
    row = json.loads(
        (snapshot_copy / "google_transparency_requests.ndjson").read_text().splitlines()[0]
    )
    row["number_of_requests"] = "1"
    with pytest.raises(SeedError, match="expected a JSON integer"):
        cast_row(FILE_MODELS["google_transparency_requests.ndjson"], row)


def test_unknown_column_rejected(snapshot_copy):
    row = json.loads((snapshot_copy / "acled_signal_context.ndjson").read_text().splitlines()[0])
    row["surprise"] = 1
    with pytest.raises(SeedError, match="extra"):
        cast_row(FILE_MODELS["acled_signal_context.ndjson"], row)
