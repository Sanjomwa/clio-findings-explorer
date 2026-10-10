"""Verify, cast and load data/snapshot/ into Postgres."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Connection,
    Date,
    DateTime,
    Double,
    Integer,
    Text,
    delete,
    func,
    insert,
    select,
)
from sqlalchemy.orm import DeclarativeBase

from app.db.models import (
    AcledSignalContext,
    Finding,
    GoogleTransparencyRequest,
    OoniWeeklySignal,
    RegimeWeek,
    SnapshotMeta,
    SnapshotTable,
)
from app.seed import SeedError

MANIFEST_NAME = "MANIFEST.json"

# manifest file name -> model. The table name is the file name minus ".ndjson".
FILE_MODELS: dict[str, type[DeclarativeBase]] = {
    "regime_weeks.ndjson": RegimeWeek,
    "acled_signal_context.ndjson": AcledSignalContext,
    "ooni_weekly_signals.ndjson": OoniWeeklySignal,
    "google_transparency_requests.ndjson": GoogleTransparencyRequest,
}


@dataclass(frozen=True)
class Manifest:
    data: dict[str, Any]

    @property
    def version(self) -> str:
        return self.data["version"]

    @property
    def tables(self) -> list[dict[str, Any]]:
        return self.data["tables"]


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return parsed


def load_manifest(snapshot_dir: Path) -> Manifest:
    path = snapshot_dir / MANIFEST_NAME
    if not path.is_file():
        raise SeedError(f"{path} not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("version", "exported_at", "tables", "attribution"):
            data[key]
        data["attribution"]["acled"]["access_date"]
        for table in data["tables"]:
            for key in ("file", "source_table", "sql", "row_count", "sha256", "exported_at"):
                table[key]
    except (ValueError, KeyError, TypeError) as exc:
        raise SeedError(f"{path} is not a valid manifest: {exc!r}") from exc
    return Manifest(data)


def verify_snapshot(snapshot_dir: Path, manifest: Manifest) -> None:
    """Check files against the manifest. Reads only; raises SeedError listing every problem."""
    problems: list[str] = []
    listed = {t["file"] for t in manifest.tables}
    for name in sorted(listed - FILE_MODELS.keys()):
        problems.append(f"{name}: listed in the manifest but the seed has no table for it")
    for table in manifest.tables:
        path = snapshot_dir / table["file"]
        if not path.is_file():
            problems.append(f"{table['file']}: listed in the manifest but missing")
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != table["sha256"]:
            problems.append(
                f"{table['file']}: sha256 {digest} does not match manifest {table['sha256']}"
            )
        lines = sum(1 for line in raw.split(b"\n") if line.strip())
        if lines != table["row_count"]:
            problems.append(
                f"{table['file']}: {lines} lines, manifest row_count is {table['row_count']}"
            )
    for entry in sorted(snapshot_dir.iterdir()):
        if entry.name != MANIFEST_NAME and entry.name not in listed:
            problems.append(
                f"{entry.name}: present in the snapshot directory but not in the manifest"
            )
    if problems:
        raise SeedError("snapshot verification failed:\n  " + "\n  ".join(problems))


def cast_row(model: type[DeclarativeBase], row: dict[str, Any]) -> dict[str, Any]:
    """Cast one NDJSON row to Python types; unknown or missing keys are errors."""
    columns = {c.name: c for c in model.__table__.columns}
    if set(row) != set(columns):
        raise SeedError(
            f"{model.__tablename__}: row keys differ from columns "
            f"(extra {sorted(set(row) - set(columns))}, missing {sorted(set(columns) - set(row))})"
        )
    out: dict[str, Any] = {}
    for name, column in columns.items():
        value = row[name]
        if value is None:
            if not column.nullable:
                raise SeedError(f"{model.__tablename__}.{name}: null in a NOT NULL column")
            out[name] = None
            continue
        kind = column.type
        try:
            if isinstance(kind, Date):
                out[name] = date.fromisoformat(value)
            elif isinstance(kind, DateTime):
                out[name] = parse_timestamp(value)
            elif isinstance(kind, Boolean):
                if not isinstance(value, bool):
                    raise ValueError("expected a JSON boolean")
                out[name] = value
            elif isinstance(kind, Integer):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError("expected a JSON integer")
                out[name] = value
            elif isinstance(kind, Double):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("expected a JSON number")
                out[name] = float(value)
            elif isinstance(kind, Text):
                if not isinstance(value, str):
                    raise ValueError("expected a string")
                out[name] = value
            else:
                raise ValueError(f"no cast for column type {kind!r}")
        except (TypeError, ValueError) as exc:
            raise SeedError(f"{model.__tablename__}.{name}: bad value {value!r} ({exc})") from exc
    return out


def read_rows(snapshot_dir: Path, file: str) -> list[dict[str, Any]]:
    model = FILE_MODELS[file]
    rows = []
    with (snapshot_dir / file).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    rows.append(cast_row(model, json.loads(line)))
                except json.JSONDecodeError as exc:
                    raise SeedError(f"{file}:{number}: invalid JSON ({exc})") from exc
    return rows


def already_loaded(conn: Connection, manifest: Manifest) -> bool:
    version = conn.execute(select(SnapshotMeta.version)).scalar_one_or_none()
    if version != manifest.version:
        return False
    stored = dict(conn.execute(select(SnapshotTable.file, SnapshotTable.sha256)).all())
    return stored == {t["file"]: t["sha256"] for t in manifest.tables}


def load_snapshot(conn: Connection, snapshot_dir: Path, manifest: Manifest) -> dict[str, int]:
    """Reload the snapshot inside the caller's transaction. Returns rows per table."""
    data = {t["file"]: read_rows(snapshot_dir, t["file"]) for t in manifest.tables}

    # Findings point at regime weeks; refuse a reload that would orphan one.
    kept = {(r["iso2"], r["week_start_date"]) for r in data["regime_weeks.ndjson"]}
    orphans = [
        f"{slug} ({iso2} {week})"
        for slug, iso2, week in conn.execute(
            select(Finding.slug, Finding.iso2, Finding.week_start_date)
        )
        if (iso2, week) not in kept
    ]
    if orphans:
        raise SeedError(
            "snapshot reload would remove regime weeks that findings reference: "
            + ", ".join(orphans)
        )

    conn.execute(delete(SnapshotTable))
    conn.execute(delete(SnapshotMeta))
    for model in FILE_MODELS.values():
        conn.execute(delete(model))

    for file, model in FILE_MODELS.items():
        if data.get(file):
            conn.execute(insert(model), data[file])
    conn.execute(
        insert(SnapshotMeta).values(
            version=manifest.version,
            exported_at=parse_timestamp(manifest.data["exported_at"]),
            acled_access_date=date.fromisoformat(
                manifest.data["attribution"]["acled"]["access_date"]
            ),
            manifest=manifest.data,
        )
    )
    conn.execute(
        insert(SnapshotTable),
        [
            {
                "file": t["file"],
                "source_table": t["source_table"],
                "sql": t["sql"],
                "row_count": t["row_count"],
                "sha256": t["sha256"],
                "exported_at": parse_timestamp(t["exported_at"]),
            }
            for t in manifest.tables
        ],
    )

    counts: dict[str, int] = {}
    for table in manifest.tables:
        model = FILE_MODELS[table["file"]]
        actual = conn.execute(select(func.count()).select_from(model)).scalar_one()
        if actual != table["row_count"]:
            raise SeedError(
                f"{model.__tablename__}: {actual} rows after load, "
                f"manifest says {table['row_count']}"
            )
        counts[model.__tablename__] = actual
    return counts
