"""Request dependencies: a read-only database session and the loaded snapshot's metadata."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import SnapshotMeta


def get_engine(request: Request):
    app = request.app
    if getattr(app.state, "engine", None) is None:
        from app.db.session import make_api_engine

        app.state.engine = make_api_engine(app.state.database_url)
    return app.state.engine


def get_session(request: Request) -> Iterator[Session]:
    """One read-only transaction per request."""
    with Session(get_engine(request)) as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session


@dataclass(frozen=True)
class Snapshot:
    version: str
    manifest: dict[str, Any]

    @property
    def attribution(self) -> dict[str, Any]:
        return self.manifest["attribution"]


def load_snapshot_meta(session: Session) -> Snapshot | None:
    row = session.execute(select(SnapshotMeta.version, SnapshotMeta.manifest)).first()
    return Snapshot(row.version, row.manifest) if row else None


def require_snapshot(session: Session) -> Snapshot:
    snapshot = load_snapshot_meta(session)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No snapshot is loaded.")
    return snapshot
