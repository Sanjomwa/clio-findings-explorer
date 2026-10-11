#!/usr/bin/env python3
"""Export a snapshot of CLIO's BigQuery output for the CLIO Findings Explorer.

Run by Sam only, by hand, in an environment where the `bq` CLI is authenticated
and its default project is CLIO's. Coding agents write and test this script
against fixtures and never run it against BigQuery (AGENTS.md, "Data rules").
How to run it: ops/README.md.

What it does, in order. Any failure stops the export with a message and exit 1,
and nothing is written to --out:

1. Checks --out: it must be outside every git working tree, except this
   repository's data/snapshot/, and must not exist or be empty.
2. Deny-list: refuses pinned data SQL that mentions a denied term.
3. Schema read (always real, even with --dry-run): reads INFORMATION_SCHEMA.COLUMNS
   for every source table. Stops if any column name ends in "is_synthetic"
   (the synthetic gate), or if an expected column is missing or has an
   unexpected BigQuery type.
4. With --dry-run: dry-runs every data query, prints the bytes each would
   process, and stops there, writing nothing.
5. Runs every data query; checks shape, deny-list, types and row counts.
6. Builds the NDJSON files and MANIFEST.json in a temporary directory beside
   --out, then renames it into place.

Standard library only. Every query goes through run_bq(), which tests replace.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# --- Finding windows ---------------------------------------------------------

# Anchor weeks of the curated findings (CLIO weeks start on Saturday). To add a
# finding window, add its week_start_date here; everything else follows.
FINDING_ANCHORS = (
    "2024-06-22",
    "2022-08-06",
    "2008-01-19",
    "2023-07-15",
    "2025-06-21",
)
WEEKS_BEFORE = 12
WEEKS_AFTER = 4
WINDOW_WEEKS = WEEKS_BEFORE + 1 + WEEKS_AFTER
WINDOW_RULE = (
    f"A window is the anchor week, the {WEEKS_BEFORE} weeks before it and the "
    f"{WEEKS_AFTER} weeks after it ({WINDOW_WEEKS} weeks, by week_start_date)."
)

# --- Guards ------------------------------------------------------------------

# Passed to bq as --max_rows. A result with this many rows may be truncated,
# so reaching it stops the export.
MAX_ROWS = 100_000

# Never exported: CLIO's Lumen-derived signal and its composite pressure score.
DENY_TERMS = ("lumen", "composite_pressure_score", "legal_pressure")

# A source table with any column whose name ends in this is refused outright.
SYNTHETIC_SUFFIX = "is_synthetic"

MIN_REGIME_WEEKS = 1523
MIN_OONI_ROWS = 550
MIN_GOOGLE_ROWS = 85

# --- Column types ------------------------------------------------------------

# Declared type of each exported column, and the BigQuery types
# (INFORMATION_SCHEMA.COLUMNS.data_type) each one accepts.
DATE, TIMESTAMP, STRING, INT, FLOAT, BOOL = (
    "date", "timestamp", "string", "int", "float", "bool",
)
BQ_TYPES = {
    DATE: {"DATE"},
    TIMESTAMP: {"TIMESTAMP"},
    STRING: {"STRING"},
    INT: {"INT64"},
    FLOAT: {"FLOAT64", "NUMERIC", "BIGNUMERIC"},
    BOOL: {"BOOL"},
}

# --- Errors and the bq runner ------------------------------------------------


class ExportError(Exception):
    """A guard or check failed. The message says which and why."""


Runner = Callable[..., str]


def run_bq(sql: str, *, dry_run: bool = False, max_rows: int = MAX_ROWS) -> str:
    """Run one query with the bq CLI and return its stdout.

    `--quiet` (a bq global flag) keeps job-status lines out of stdout so the
    output is pure JSON.
    """
    cmd = [
        "bq", "--quiet", "query",
        "--use_legacy_sql=false", "--format=json", f"--max_rows={max_rows}",
    ]
    if dry_run:
        cmd.append("--dry_run")
    cmd.append(sql)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise ExportError("the bq CLI was not found on PATH") from None
    if proc.returncode != 0:
        detail = (proc.stderr.strip() or proc.stdout.strip())[:2000]
        raise ExportError(f"bq exited with status {proc.returncode}:\n{detail}\nSQL:\n{sql}")
    return proc.stdout


# --- Pinned queries ----------------------------------------------------------


def window_weeks(anchor: date) -> list[date]:
    return [anchor + timedelta(weeks=i) for i in range(-WEEKS_BEFORE, WEEKS_AFTER + 1)]


def anchor_dates() -> list[date]:
    return [date.fromisoformat(a) for a in FINDING_ANCHORS]


def _window_predicate() -> str:
    windows = sorted(window_weeks(a) for a in anchor_dates())
    ranges = [f"week_start_date BETWEEN DATE '{w[0]}' AND DATE '{w[-1]}'" for w in windows]
    return "(\n    " + "\n    OR ".join(ranges) + "\n  )"


def _select_list(items: Sequence[str]) -> str:
    return ",\n  ".join(items)


def _names(columns: Sequence[tuple[str, str]]) -> list[str]:
    return [name for name, _ in columns]


def _order_by(columns: Sequence[tuple[str, str]], *leading: str) -> str:
    """The leading sort keys, then every other selected column as a tie-breaker,
    so the row order (and each file's sha256) does not depend on BigQuery."""
    rest = [name for name in _names(columns) if name not in leading]
    return "ORDER BY\n  " + ",\n  ".join([*leading, *rest])


REGIME_COLUMNS = (
    ("week_start_date", DATE),
    ("country", STRING),
    ("iso2", STRING),
    ("primary_regime", STRING),
    ("confidence_level", STRING),
    ("previous_regime", STRING),
    ("transition_detected", BOOL),
    ("transition_type", STRING),
    ("regime_duration_weeks", INT),
    ("weeks_in_current_regime", INT),
    ("regime_held_by_exit_persistence", BOOL),
    ("fallback_used", BOOL),
    ("methodology_caveat_required", BOOL),
    ("protest_band", STRING),
    ("violence_band", STRING),
    ("suppression_band", STRING),
    ("velocity_band", STRING),
    ("conversion_band", STRING),
    ("classification_reason", STRING),
    ("regime_methodology_version", STRING),
    ("feature_version", STRING),
    ("computed_at", TIMESTAMP),
)

REGIME_SQL = f"""SELECT
  {_select_list(_names(REGIME_COLUMNS))}
FROM intelligence.acled_pressure_regimes
WHERE country = 'Kenya'
{_order_by(REGIME_COLUMNS, "week_start_date")}"""

SIGNAL_COLUMNS = (
    ("week_start_date", DATE),
    ("total_events", INT),
    ("total_fatalities", INT),
    ("signal_valid", BOOL),
    ("protest_pressure_z", FLOAT),
    ("violence_pressure_z", FLOAT),
    ("suppression_z", FLOAT),
    ("protest_active_baseline_weeks", INT),
    ("violence_active_baseline_weeks", INT),
    ("suppression_active_baseline_weeks", INT),
    ("sparse_protest_baseline_flag", BOOL),
    ("sparse_violence_baseline_flag", BOOL),
    ("sparse_suppression_baseline_flag", BOOL),
    ("zero_variance_flag", BOOL),
    ("low_event_density_flag", BOOL),
    ("high_methodology_risk_flag", BOOL),
)

SIGNAL_SQL = f"""SELECT
  {_select_list(_names(SIGNAL_COLUMNS))}
FROM features.acled_pressure_signals
WHERE country = 'Kenya'
  AND {_window_predicate()}
{_order_by(SIGNAL_COLUMNS, "week_start_date")}"""

OONI_COLUMNS = (
    ("week_start_date", DATE),
    ("test_name", STRING),
    ("anomalous_total_scored", INT),
    ("anomalous_count", INT),
    ("anomalous_rate", FLOAT),
    ("anomalous_baseline_rate_12w", FLOAT),
    ("anomalous_zscore_12w", FLOAT),
    ("anomalous_low_sample_flag", BOOL),
    ("anomalous_sparse_baseline_flag", BOOL),
    ("blocked_total_observations", INT),
    ("blocked_count", INT),
    ("blocked_rate", FLOAT),
    ("blocked_baseline_rate_12w", FLOAT),
    ("blocked_zscore_12w", FLOAT),
    ("blocked_low_sample_flag", BOOL),
    ("blocked_sparse_baseline_flag", BOOL),
    ("feature_version", STRING),
)

OONI_SQL = f"""SELECT
  {_select_list(_names(OONI_COLUMNS))}
FROM features.ooni_weekly_signals
WHERE country = 'KE'
{_order_by(OONI_COLUMNS, "week_start_date", "test_name")}"""

GOOGLE_COLUMNS = (
    ("time_period", STRING),
    ("period_date", DATE),
    ("requestor", STRING),
    ("product", STRING),
    ("reason", STRING),
    ("number_of_requests", INT),
    ("items_requested_removal", INT),
    ("items_removed_legal", INT),
    ("items_removed_policy", INT),
)

GOOGLE_SQL = f"""SELECT
  {_select_list(_names(GOOGLE_COLUMNS))}
FROM stg.google_transparency_requests
WHERE country = 'Kenya'
{_order_by(GOOGLE_COLUMNS, "period_date", "requestor", "product", "reason")}"""

SCHEMA_SQL_TEMPLATE = """SELECT
  table_name,
  column_name,
  data_type
FROM {dataset}.INFORMATION_SCHEMA.COLUMNS
WHERE table_name IN ({tables})
ORDER BY table_name, ordinal_position"""

SCHEMA_KEYS = ("table_name", "column_name", "data_type")

# --- Row checks --------------------------------------------------------------


def _weeks(rows: list[dict]) -> list[date]:
    return [date.fromisoformat(r["week_start_date"]) for r in rows]


def _first(items: Sequence, n: int = 5) -> str:
    shown = ", ".join(str(i) for i in list(items)[:n])
    return shown + (f" (and {len(items) - n} more)" if len(items) > n else "")


def check_regime_weeks(rows: list[dict]) -> None:
    if len(rows) < MIN_REGIME_WEEKS:
        raise ExportError(f"{len(rows)} rows, expected at least {MIN_REGIME_WEEKS}")
    weeks = _weeks(rows)
    not_saturday = [w for w in weeks if w.weekday() != 5]
    if not_saturday:
        raise ExportError(f"week_start_date is not a Saturday: {_first(not_saturday)}")
    seen, dupes = set(), []
    for w in weeks:
        if w in seen:
            dupes.append(w)
        seen.add(w)
    if dupes:
        raise ExportError(f"duplicate week_start_date: {_first(dupes)}")
    breaks = [(a, b) for a, b in zip(weeks, weeks[1:]) if b - a != timedelta(weeks=1)]
    if breaks:
        raise ExportError(
            "weeks are not consecutive (gap or wrong order) between: "
            + _first([f"{a} and {b}" for a, b in breaks])
        )


def _check_in_windows(rows: list[dict]) -> list[date]:
    weeks = _weeks(rows)
    allowed = {w for a in anchor_dates() for w in window_weeks(a)}
    outside = sorted({w for w in weeks if w not in allowed})
    if outside:
        raise ExportError(f"rows outside every finding window: {_first(outside)}")
    return weeks


def check_signal_context(rows: list[dict]) -> None:
    weeks = _check_in_windows(rows)
    for anchor in anchor_dates():
        expected = window_weeks(anchor)
        expected_set = set(expected)
        got = [w for w in weeks if w in expected_set]
        if len(got) == WINDOW_WEEKS and set(got) == expected_set:
            continue
        missing = sorted(expected_set - set(got))
        dupes = sorted({w for w in got if got.count(w) > 1})
        raise ExportError(
            f"anchor {anchor}: {len(got)} rows, expected exactly {WINDOW_WEEKS} "
            f"(one per week {expected[0]} to {expected[-1]})"
            + (f"; missing weeks: {_first(missing)}" if missing else "")
            + (f"; duplicated weeks: {_first(dupes)}" if dupes else "")
        )


def check_ooni(rows: list[dict]) -> None:
    if len(rows) < MIN_OONI_ROWS:
        raise ExportError(f"{len(rows)} rows, expected at least {MIN_OONI_ROWS}")
    seen, dupes = set(), []
    for row in rows:
        key = (row["week_start_date"], row["test_name"])
        if key in seen:
            dupes.append(key)
        seen.add(key)
    if dupes:
        raise ExportError(
            "duplicate (week_start_date, test_name): "
            + _first([f"({w}, {t})" for w, t in dupes])
        )


def _check_min_rows(minimum: int) -> Callable[[list[dict]], None]:
    def check(rows: list[dict]) -> None:
        if len(rows) < minimum:
            raise ExportError(f"{len(rows)} rows, expected at least {minimum}")
    return check


# --- Exports -----------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Export:
    file: str
    source_table: str
    # Output columns, in file order, with their declared types.
    columns: tuple[tuple[str, str], ...]
    # Source-table columns the SQL reads, checked against INFORMATION_SCHEMA.
    source_columns: tuple[tuple[str, str], ...]
    # Must be present and non-null in every returned row.
    key_column: str
    sql: str
    check: Callable[[list[dict]], None]


EXPORTS = (
    Export(
        file="regime_weeks.ndjson",
        source_table="intelligence.acled_pressure_regimes",
        columns=REGIME_COLUMNS,
        source_columns=REGIME_COLUMNS,
        key_column="week_start_date",
        sql=REGIME_SQL,
        check=check_regime_weeks,
    ),
    Export(
        file="acled_signal_context.ndjson",
        source_table="features.acled_pressure_signals",
        columns=SIGNAL_COLUMNS,
        source_columns=SIGNAL_COLUMNS + (("country", STRING),),
        key_column="week_start_date",
        sql=SIGNAL_SQL,
        check=check_signal_context,
    ),
    Export(
        file="ooni_weekly_signals.ndjson",
        source_table="features.ooni_weekly_signals",
        columns=OONI_COLUMNS,
        source_columns=OONI_COLUMNS + (("country", STRING),),
        key_column="week_start_date",
        sql=OONI_SQL,
        check=check_ooni,
    ),
    Export(
        file="google_transparency_requests.ndjson",
        source_table="stg.google_transparency_requests",
        columns=GOOGLE_COLUMNS,
        source_columns=GOOGLE_COLUMNS + (("country", STRING),),
        key_column="period_date",
        sql=GOOGLE_SQL,
        check=_check_min_rows(MIN_GOOGLE_ROWS),
    ),
)

ACLED_FILES = ("regime_weeks.ndjson", "acled_signal_context.ndjson")


def attribution(acled_access_date: str) -> dict:
    return {
        "acled": {
            "name": "Armed Conflict Location & Event Data (ACLED)",
            "licence": "Contractual licence (ACLED terms of use); non-commercial use",
            "access_date": acled_access_date,
            "filter": "Kenya",
            "manipulation": "Weekly aggregation and classification by CLIO",
            "files": list(ACLED_FILES),
        },
        "ooni": {
            "name": "Open Observatory of Network Interference (OONI)",
            "licence": "CC BY-NC-SA 4.0",
            "filter": "Kenya",
            "manipulation": "Weekly aggregation by CLIO",
            "files": ["ooni_weekly_signals.ndjson"],
        },
        "google_transparency": {
            "name": "Google Transparency Report",
            "licence": "Reuse terms not determined",
            "filter": "Kenya",
            "manipulation": (
                "Filtered to Kenya. period_date derived by CLIO from the reporting "
                "period label."
            ),
            "files": ["google_transparency_requests.ndjson"],
        },
    }


# --- Static checks -----------------------------------------------------------

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


def denied_term(text: str) -> str | None:
    lowered = text.lower()
    for term in DENY_TERMS:
        if term in lowered:
            return term
    return None


def check_static(exports: Sequence[Export]) -> None:
    for anchor in anchor_dates():
        if anchor.weekday() != 5:
            raise ExportError(f"finding anchor {anchor} is not a Saturday")
    if len(set(FINDING_ANCHORS)) != len(FINDING_ANCHORS):
        raise ExportError("FINDING_ANCHORS contains a duplicate")
    for export in exports:
        if not _TABLE_RE.match(export.source_table):
            raise ExportError(
                f"{export.file}: source table {export.source_table!r} must be an "
                "unqualified dataset.table name, with no project id"
            )
        term = denied_term(export.sql)
        if term:
            raise ExportError(f"deny-list: the pinned SQL for {export.file} contains {term!r}")


# --- --out -------------------------------------------------------------------


def find_worktree(path: Path) -> Path | None:
    """The nearest directory at or above `path` that holds a .git entry."""
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


_SCRIPT_REPO = Path(__file__).resolve().parents[1]
# This repository's root, when the script runs from a clone of it.
REPO_ROOT = _SCRIPT_REPO if (_SCRIPT_REPO / ".git").exists() else None


def check_out_dir(out: Path, repo_root: Path | None = REPO_ROOT) -> Path:
    """Resolve --out and refuse it unless it is safe to write. Writes nothing."""
    out = out.expanduser().resolve()
    tree = find_worktree(out)
    if tree is not None:
        allowed = (repo_root / "data" / "snapshot").resolve() if repo_root else None
        if allowed is None or out != allowed or tree != repo_root.resolve():
            raise ExportError(
                f"--out {out} is inside the git working tree {tree}. The only place "
                "inside a git working tree this script writes is this repository's "
                "data/snapshot/"
                + (f" ({allowed})" if allowed else "")
                + ". Write somewhere outside any repository and copy it in."
            )
    if out.exists():
        if not out.is_dir():
            raise ExportError(f"--out {out} exists and is not a directory")
        if any(out.iterdir()):
            raise ExportError(f"--out {out} exists and is not empty; clear it first")
    if not out.parent.is_dir():
        raise ExportError(f"the parent of --out does not exist: {out.parent}")
    return out


# --- Parsing and casting -----------------------------------------------------


def parse_rows(output: str, what: str) -> list:
    text = output.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExportError(f"{what}: bq output is not JSON ({exc}); it starts: {text[:200]!r}") from None
    if not isinstance(data, list):
        raise ExportError(f"{what}: expected a JSON array of rows, got {type(data).__name__}")
    if len(data) >= MAX_ROWS:
        raise ExportError(
            f"{what}: {len(data)} rows reached --max_rows={MAX_ROWS}; the result may be "
            "truncated. Raise MAX_ROWS and run again."
        )
    return data


class _CastError(Exception):
    pass


_INT_RE = re.compile(r"^[+-]?\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMBER_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_FRACTION_RE = re.compile(r"(?<=:\d\d)\.(\d+)")


def _cast_timestamp(value) -> str:
    if isinstance(value, bool):
        raise _CastError
    if isinstance(value, (int, float)) or (isinstance(value, str) and _NUMBER_RE.match(value.strip())):
        # Epoch seconds.
        moment = datetime.fromtimestamp(float(value), tz=UTC)
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(" UTC"):
            text = text[: -len(" UTC")]
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if "T" not in text and " " in text:
            text = text.replace(" ", "T", 1)
        # Python before 3.11 parses only 3- or 6-digit fractions; use 6.
        text = _FRACTION_RE.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), text, count=1)
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            raise _CastError from None
        if moment.tzinfo is None:
            # The schema check guarantees a TIMESTAMP column, which BigQuery
            # renders in UTC.
            moment = moment.replace(tzinfo=UTC)
    else:
        raise _CastError
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def cast_value(value, kind: str):
    """Cast one value from bq's JSON to its declared type, or raise _CastError."""
    if value is None:
        return None
    if kind == STRING:
        if isinstance(value, str):
            return value
    elif kind == INT:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and _INT_RE.match(value.strip()):
            return int(value)
    elif kind == FLOAT:
        number = None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
        elif isinstance(value, str) and _NUMBER_RE.match(value.strip()):
            number = float(value)
        if number is not None and math.isfinite(number):
            return number
    elif kind == BOOL:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
    elif kind == DATE:
        if isinstance(value, str) and _DATE_RE.match(value):
            try:
                return date.fromisoformat(value).isoformat()
            except ValueError:
                pass
    elif kind == TIMESTAMP:
        return _cast_timestamp(value)
    raise _CastError


def shape_rows(export: Export, raw_rows: list) -> list[dict]:
    """Deny-list, shape and type checks on one query's rows; returns typed rows."""
    expected = _names(export.columns)
    expected_set = set(expected)
    rows = []
    for index, row in enumerate(raw_rows):
        where = f"{export.file}, row {index + 1}"
        if not isinstance(row, dict):
            raise ExportError(f"shape: {where} is not an object: {row!r:.200}")
        for key in row:
            term = denied_term(str(key))
            if term:
                raise ExportError(f"deny-list: {where} has column {key!r}, which contains {term!r}")
        unexpected = sorted(set(row) - expected_set)
        if unexpected:
            raise ExportError(
                f"shape: {where} has unexpected columns {unexpected}; expected only "
                f"{expected}. A quoted column list returns one string column like this."
            )
        if row.get(export.key_column) is None:
            raise ExportError(f"shape: {where} has no {export.key_column}")
        typed = {}
        for name, kind in export.columns:
            value = row.get(name)
            try:
                typed[name] = cast_value(value, kind)
            except _CastError:
                raise ExportError(
                    f"type: {where}, column {name}: cannot cast {value!r:.100} to {kind}"
                ) from None
        rows.append(typed)
    return rows


# --- Schema read and synthetic gate --------------------------------------------


def schema_audit(exports: Sequence[Export], runner: Runner) -> dict:
    tables = sorted({e.source_table for e in exports})
    by_dataset: dict[str, list[str]] = {}
    for table in tables:
        dataset, name = table.split(".")
        by_dataset.setdefault(dataset, []).append(name)

    columns: dict[str, dict[str, str]] = {t: {} for t in tables}
    queries = []
    for dataset, names in by_dataset.items():
        sql = SCHEMA_SQL_TEMPLATE.format(
            dataset=dataset, tables=", ".join(f"'{n}'" for n in names)
        )
        queries.append(sql)
        what = f"schema read for dataset {dataset}"
        for index, row in enumerate(parse_rows(runner(sql, dry_run=False, max_rows=MAX_ROWS), what)):
            if not isinstance(row, dict) or set(row) != set(SCHEMA_KEYS):
                raise ExportError(f"shape: {what}, row {index + 1}: {row!r:.200}")
            table = f"{dataset}.{row['table_name']}"
            if table in columns:
                columns[table][str(row["column_name"])] = str(row["data_type"])

    missing_tables = [t for t in tables if not columns[t]]
    if missing_tables:
        raise ExportError(f"schema read found no columns for: {', '.join(missing_tables)}")

    flagged = [
        f"{t}.{c}" for t in tables for c in columns[t] if c.lower().endswith(SYNTHETIC_SUFFIX)
    ]
    if flagged:
        raise ExportError(
            "synthetic gate: these source tables carry a synthetic flag column, and "
            f"the export refuses any such table: {', '.join(flagged)}"
        )

    problems = []
    for export in exports:
        found = columns[export.source_table]
        for name, kind in export.source_columns:
            data_type = found.get(name)
            if data_type is None:
                problems.append(f"{export.source_table}.{name} is missing")
            elif data_type.upper() not in BQ_TYPES[kind]:
                problems.append(
                    f"{export.source_table}.{name} is {data_type}, expected "
                    f"{' or '.join(sorted(BQ_TYPES[kind]))}"
                )
    if problems:
        raise ExportError("schema check: " + "; ".join(problems))

    return {
        "rule": (
            "The export refuses any source table that has a column whose name ends in "
            f"'{SYNTHETIC_SUFFIX}', whatever its values."
        ),
        "tables_checked": tables,
        "sql": queries,
        "synthetic_flag_columns": [],
        "result": "passed",
    }


# --- Dry run -----------------------------------------------------------------

_DRY_RUN_TEXT_RE = re.compile(r"process(?:es)?\s+(\d+)\s+bytes", re.IGNORECASE)


def _find_key(data, key: str):
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


def parse_dry_run_bytes(output: str) -> int:
    """Bytes a dry-run query would process, from bq's JSON job or its text message."""
    try:
        found = _find_key(json.loads(output), "totalBytesProcessed")
        if found is not None and _INT_RE.match(str(found)):
            return int(found)
    except json.JSONDecodeError:
        pass
    match = _DRY_RUN_TEXT_RE.search(output)
    if match:
        return int(match.group(1))
    raise ExportError(f"could not read the bytes processed from bq's dry-run output: {output.strip()[:500]!r}")


def _human_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{n} B"
        size /= 1024
    return f"{n} B"


# --- Export ------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_snapshot_version() -> str:
    return datetime.now(UTC).date().isoformat() + ".1"


def _write_json_lines(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_snapshot(
    out: Path,
    acled_access_date: str,
    snapshot_version: str,
    dry_run: bool,
    runner: Runner,
    exports: Sequence[Export] = EXPORTS,
) -> None:
    check_static(exports)
    out = check_out_dir(out)
    audit = schema_audit(exports, runner)
    print(f"Synthetic gate and schema check passed for {len(audit['tables_checked'])} tables.")

    if dry_run:
        total = 0
        for export in exports:
            processed = parse_dry_run_bytes(runner(export.sql, dry_run=True, max_rows=MAX_ROWS))
            total += processed
            print(f"{export.file}: would process {processed} bytes ({_human_bytes(processed)})")
        print(f"Total: {total} bytes ({_human_bytes(total)}). Dry run: nothing written.")
        return

    results = []
    for export in exports:
        raw = parse_rows(runner(export.sql, dry_run=False, max_rows=MAX_ROWS), export.file)
        rows = shape_rows(export, raw)
        try:
            export.check(rows)
        except ExportError as exc:
            raise ExportError(f"check failed for {export.file}: {exc}") from None
        results.append((export, rows, utc_now()))
        print(f"{export.file}: {len(rows)} rows")

    tmp = Path(tempfile.mkdtemp(prefix=f".{out.name}.tmp-", dir=out.parent))
    try:
        tables = []
        for export, rows, exported_at in results:
            path = tmp / export.file
            _write_json_lines(path, rows)
            tables.append({
                "file": export.file,
                "source_table": export.source_table,
                "sql": export.sql,
                "row_count": len(rows),
                "sha256": _sha256(path),
                "exported_at": exported_at,
            })
        manifest = {
            "version": snapshot_version,
            "exported_at": utc_now(),
            "tables": tables,
            "synthetic_audit": audit,
            "finding_anchors": {
                "anchors": list(FINDING_ANCHORS),
                "weeks_before": WEEKS_BEFORE,
                "weeks_after": WEEKS_AFTER,
                "rule": WINDOW_RULE,
            },
            "attribution": attribution(acled_access_date),
        }
        (tmp / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        # Re-check just before the move, in case --out changed during the run.
        check_out_dir(out)
        if out.exists():
            out.rmdir()
        os.chmod(tmp, 0o755)
        os.rename(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    print(f"Snapshot {snapshot_version} written to {out}")


# --- CLI ---------------------------------------------------------------------


def _iso_date(text: str) -> str:
    if not _DATE_RE.match(text):
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}")
    try:
        value = date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a valid date: {text!r}") from None
    if value > datetime.now(UTC).date():
        raise argparse.ArgumentTypeError(f"date is in the future: {text}")
    return text


def _snapshot_version(text: str) -> str:
    if not re.match(r"^[0-9A-Za-z][0-9A-Za-z._-]*$", text):
        raise argparse.ArgumentTypeError(f"invalid snapshot version: {text!r}")
    return text


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a CLIO snapshot from BigQuery (run by Sam only; see ops/README.md).",
    )
    parser.add_argument("--out", required=True, type=Path,
                        help="output directory; must not exist or be empty")
    parser.add_argument("--acled-access-date", required=True, type=_iso_date,
                        help="date the ACLED export was obtained (YYYY-MM-DD)")
    parser.add_argument("--snapshot-version", type=_snapshot_version, default=None,
                        help="default: today's UTC date plus '.1'")
    parser.add_argument("--dry-run", action="store_true",
                        help="run the schema reads, dry-run the data queries, write nothing")
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    runner: Runner | None = None,
    exports: Sequence[Export] = EXPORTS,
) -> int:
    args = parse_args(argv)
    try:
        export_snapshot(
            out=args.out,
            acled_access_date=args.acled_access_date,
            snapshot_version=args.snapshot_version or default_snapshot_version(),
            dry_run=args.dry_run,
            runner=runner or run_bq,
            exports=exports,
        )
    except ExportError as exc:
        print(f"export_snapshot: STOPPED: {exc}", file=sys.stderr)
        print("export_snapshot: nothing was written to --out.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
