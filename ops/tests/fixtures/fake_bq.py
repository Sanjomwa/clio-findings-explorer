"""A fake `bq` runner and fixture data for ops/tests.

Everything here is invented test data shaped like what `bq query --format=json`
returns: one JSON array of objects, with numbers and booleans as strings and
NULL as null. None of it comes from CLIO or describes real events. Values are
marked FIXTURE wherever a string allows it.

Row counts are generated rather than stored, because the export's minimum-row
checks (1,523 regime weeks, 550 OONI rows, 85 Google rows) need full-size
tables.
"""

import json
import re
from datetime import date, timedelta

FIRST_WEEK = date(1997, 1, 11)
REGIME_WEEKS = 1523
OONI_FIRST_WEEK = date(2023, 5, 27)
OONI_WEEKS = 110
OONI_TESTS = ("facebook_messenger", "signal", "telegram", "web_connectivity", "whatsapp")
GOOGLE_PERIODS = 30
FAKE_BYTES = 1048576

# BigQuery type for each declared column type (INFORMATION_SCHEMA.data_type).
BQ_TYPE_FOR = {
    "date": "DATE", "timestamp": "TIMESTAMP", "string": "STRING",
    "int": "INT64", "float": "FLOAT64", "bool": "BOOL",
}


def regime_row(week):
    return {
        "week_start_date": week.isoformat(),
        "country": "Kenya",
        "iso2": "KE",
        "primary_regime": "STABLE",
        "confidence_level": "FIXTURE",
        "previous_regime": "STABLE",
        "transition_detected": "false",
        "transition_type": None,
        "regime_duration_weeks": "3",
        "weeks_in_current_regime": "3",
        "regime_held_by_exit_persistence": "false",
        "fallback_used": "false",
        "methodology_caveat_required": "true",
        "protest_band": "FIXTURE",
        "violence_band": "FIXTURE",
        "suppression_band": "FIXTURE",
        "velocity_band": "FIXTURE",
        "conversion_band": "FIXTURE",
        "classification_reason": "FIXTURE row for tests",
        "regime_methodology_version": "fixture-1",
        "feature_version": "fixture-1",
        "computed_at": "2026-03-15 04:12:33.123456 UTC",
    }


def regime_rows():
    rows = [regime_row(FIRST_WEEK + timedelta(weeks=i)) for i in range(REGIME_WEEKS)]
    # The first week has no previous regime; bq may leave the key out.
    del rows[0]["previous_regime"]
    return rows


def window_weeks(anchor):
    return [anchor + timedelta(weeks=i) for i in range(-12, 5)]


def signal_rows(anchors):
    rows = []
    for week in sorted(w for a in anchors for w in window_weeks(date.fromisoformat(a))):
        rows.append({
            "week_start_date": week.isoformat(),
            "total_events": "7",
            "total_fatalities": "1",
            "signal_valid": "true",
            "protest_pressure_z": "0.25",
            "violence_pressure_z": "-1.5",
            "suppression_z": None,
            "protest_active_baseline_weeks": "12",
            "violence_active_baseline_weeks": "12",
            "suppression_active_baseline_weeks": "0",
            "sparse_protest_baseline_flag": "false",
            "sparse_violence_baseline_flag": "false",
            "sparse_suppression_baseline_flag": "true",
            "zero_variance_flag": "false",
            "low_event_density_flag": "false",
            "high_methodology_risk_flag": "false",
        })
    return rows


def ooni_rows():
    rows = []
    for i in range(OONI_WEEKS):
        week = OONI_FIRST_WEEK + timedelta(weeks=i)
        for test_name in OONI_TESTS:
            rows.append({
                "week_start_date": week.isoformat(),
                "test_name": test_name,
                "anomalous_total_scored": "40",
                "anomalous_count": "2",
                "anomalous_rate": "0.05",
                "anomalous_baseline_rate_12w": "0.04",
                "anomalous_zscore_12w": "0.3",
                "anomalous_low_sample_flag": "false",
                "anomalous_sparse_baseline_flag": "false",
                "blocked_total_observations": "40",
                "blocked_count": "0",
                "blocked_rate": "0",
                "blocked_baseline_rate_12w": "0",
                "blocked_zscore_12w": None,
                "blocked_low_sample_flag": "false",
                "blocked_sparse_baseline_flag": "false",
                "feature_version": "fixture-1",
            })
    return rows


def google_rows():
    rows = []
    for i in range(GOOGLE_PERIODS):
        year, half = 2012 + i // 2, 1 + i % 2
        period_date = date(year, 6, 30) if half == 1 else date(year, 12, 31)
        for product in ("FIXTURE product A", "FIXTURE product B", "FIXTURE product C"):
            rows.append({
                "time_period": f"{year}-H{half}",
                "period_date": period_date.isoformat(),
                "requestor": "FIXTURE requestor",
                "product": product,
                "reason": "FIXTURE reason",
                "number_of_requests": "1",
                "items_requested_removal": "2",
                "items_removed_legal": "0",
                "items_removed_policy": "1",
            })
    return rows


def default_schema(exports):
    """table -> list of (column_name, data_type), from the script's declarations."""
    schema = {}
    for export in exports:
        columns = schema.setdefault(export.source_table, [])
        for name, kind in export.source_columns:
            if name not in [c for c, _ in columns]:
                columns.append((name, BQ_TYPE_FOR[kind]))
    # Source tables have columns the export never reads.
    schema["intelligence.acled_pressure_regimes"].append(("fixture_unexported_note", "STRING"))
    return schema


class FakeBq:
    """Stands in for export_snapshot.run_bq. Records every call."""

    def __init__(self, export_module):
        self.module = export_module
        self.schema = default_schema(export_module.EXPORTS)
        self.data = {
            "intelligence.acled_pressure_regimes": regime_rows(),
            "features.acled_pressure_signals": signal_rows(export_module.FINDING_ANCHORS),
            "features.ooni_weekly_signals": ooni_rows(),
            "stg.google_transparency_requests": google_rows(),
        }
        # When set, the raw stdout to return for a table instead of its rows.
        self.raw = {}
        self.calls = []

    def __call__(self, sql, *, dry_run=False, max_rows=None):
        self.calls.append({"sql": sql, "dry_run": dry_run, "max_rows": max_rows})
        schema_match = re.search(r"FROM (\w+)\.INFORMATION_SCHEMA\.COLUMNS", sql)
        if dry_run:
            # Assumed shape of `bq --format=json --dry_run`: the job resource.
            return json.dumps({"statistics": {"totalBytesProcessed": str(FAKE_BYTES)}})
        if schema_match:
            dataset = schema_match.group(1)
            names = re.findall(r"'(\w+)'", sql)
            rows = [
                {"table_name": name, "column_name": column, "data_type": data_type}
                for name in names
                for column, data_type in self.schema.get(f"{dataset}.{name}", [])
            ]
            return json.dumps(rows)
        table = re.search(r"FROM (\w+\.\w+)", sql).group(1)
        if table in self.raw:
            return self.raw[table]
        return json.dumps(self.data[table])

    def data_calls(self):
        return [c for c in self.calls if "INFORMATION_SCHEMA" not in c["sql"]]
