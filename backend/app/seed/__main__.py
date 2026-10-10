"""python -m app.seed: verify the snapshot, load it and any curated content in one transaction."""

import os
import sys
from pathlib import Path

from app.db.session import make_engine
from app.seed import SeedError
from app.seed.content import load_content, sync_findings
from app.seed.snapshot import already_loaded, load_manifest, load_snapshot, verify_snapshot

REPO_ROOT = Path(__file__).resolve().parents[3]


def run(snapshot_dir: Path, content_dir: Path, engine=None) -> list[str]:
    """Seed the database. Returns the summary lines. Raises SeedError; nothing is written then."""
    manifest = load_manifest(snapshot_dir)
    verify_snapshot(snapshot_dir, manifest)  # before any database work
    docs = load_content(content_dir)  # also validated before any database work

    lines = [f"snapshot version: {manifest.version}"]
    engine = engine or make_engine()
    with engine.begin() as conn:  # one transaction: commit on success, roll back on any error
        if already_loaded(conn, manifest):
            lines.append("snapshot already loaded")
            counts = {t["file"].removesuffix(".ndjson"): t["row_count"] for t in manifest.tables}
        else:
            counts = load_snapshot(conn, snapshot_dir, manifest)
            lines.append("snapshot loaded")
        for table, count in counts.items():
            lines.append(f"  {table}: {count} rows")
        if docs is None:
            lines.append("no content/ directory: 0 findings")
        else:
            lines.append(f"findings loaded: {sync_findings(conn, docs)}")
    return lines


def main() -> int:
    snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR") or REPO_ROOT / "data" / "snapshot")
    content_dir = Path(os.environ.get("CONTENT_DIR") or REPO_ROOT / "content")
    try:
        lines = run(snapshot_dir, content_dir)
    except SeedError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
