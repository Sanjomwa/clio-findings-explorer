import os
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SnapshotTable
from app.deps import get_session, require_snapshot
from app.evidence.service import SOURCES
from app.routers.common import NO_SNAPSHOT
from app.schemas import MethodologyResponse, SourceNote

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_curated_definitions() -> dict:
    """Curated definitions from CONTENT_DIR/methodology.yaml; empty when the file is absent."""
    content_dir = Path(os.environ.get("CONTENT_DIR") or REPO_ROOT / "content")
    path = content_dir / "methodology.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@router.get("/api/methodology", response_model=MethodologyResponse, responses=NO_SNAPSHOT)
def get_methodology(session: Annotated[Session, Depends(get_session)]):
    snapshot = require_snapshot(session)
    curated = load_curated_definitions()
    tables = session.execute(
        select(
            SnapshotTable.file,
            SnapshotTable.source_table,
            SnapshotTable.sql,
            SnapshotTable.row_count,
            SnapshotTable.exported_at,
        ).order_by(SnapshotTable.file)
    ).mappings()
    sources = []
    for s in SOURCES:
        a = snapshot.attribution[s]
        sources.append(
            SourceNote(
                source=s,
                name=a["name"],
                note=(
                    f"Licence: {a['licence']}. Filter: {a['filter']}. "
                    f"Manipulation: {a['manipulation']}."
                ),
            )
        )
    return MethodologyResponse.model_validate(
        {
            "snapshot_version": snapshot.version,
            "families": curated.get("families", []),
            "regime_states": curated.get("regime_states", []),
            "confidence_levels": curated.get("confidence_levels", []),
            "family_bands": curated.get("family_bands", []),
            "sources": sources,
            "manifest": {
                "version": snapshot.version,
                "exported_at": snapshot.manifest["exported_at"],
                "tables": [dict(t) for t in tables],
            },
        }
    )
