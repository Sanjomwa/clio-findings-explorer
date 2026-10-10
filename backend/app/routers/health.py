from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    AcledSignalContext,
    Finding,
    FindingCaveat,
    GoogleTransparencyRequest,
    OoniWeeklySignal,
    RegimeWeek,
    SnapshotMeta,
)
from app.deps import get_engine
from app.schemas import Health

router = APIRouter()

COUNTED = (
    RegimeWeek,
    AcledSignalContext,
    OoniWeeklySignal,
    GoogleTransparencyRequest,
    Finding,
    FindingCaveat,
)


def _degraded(database: str, **fields) -> JSONResponse:
    body = Health(
        status="degraded",
        database=database,
        snapshot_version=fields.get("snapshot_version"),
        migration_head=fields.get("migration_head"),
        row_counts=fields.get("row_counts", {}),
    )
    return JSONResponse(status_code=503, content=body.model_dump(mode="json"))


@router.get("/api/health", response_model=Health, responses={503: {"model": Health}})
def get_health(request: Request):
    try:
        with Session(get_engine(request)) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(text("SELECT 1"))
            return _health(session)
    except OperationalError:
        return _degraded("unreachable")
    except SQLAlchemyError:  # reachable, but not migrated or otherwise unusable
        return _degraded("reachable")


def _health(session: Session):
    head = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    version = session.execute(select(SnapshotMeta.version)).scalar()
    counts = {
        m.__tablename__: session.execute(select(func.count()).select_from(m)).scalar_one()
        for m in COUNTED
    }
    if version is None:
        return _degraded("reachable", migration_head=head, row_counts=counts)
    return Health(
        status="ok",
        database="reachable",
        snapshot_version=version,
        migration_head=head,
        row_counts=counts,
    )
