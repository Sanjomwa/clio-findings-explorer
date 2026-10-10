from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Finding, RegimeWeek
from app.deps import get_session, require_snapshot
from app.routers.common import NO_SNAPSHOT
from app.schemas import RegimeState, TimelineResponse, TimelineWeek

router = APIRouter()


@router.get("/api/timeline", response_model=TimelineResponse, responses=NO_SNAPSHOT)
def get_timeline(
    session: Annotated[Session, Depends(get_session)],
    country: Annotated[str, Query(pattern="^[A-Z]{2}$")] = "KE",
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    state: RegimeState | None = None,
):
    snapshot = require_snapshot(session)
    stmt = select(RegimeWeek).where(RegimeWeek.iso2 == country).order_by(RegimeWeek.week_start_date)
    if from_ is not None:
        stmt = stmt.where(RegimeWeek.week_start_date >= from_)
    if to is not None:
        stmt = stmt.where(RegimeWeek.week_start_date <= to)
    if state is not None:
        stmt = stmt.where(RegimeWeek.primary_regime == state)
    slugs: dict[date, str] = {}
    for slug, week in session.execute(
        select(Finding.slug, Finding.week_start_date)
        .where(Finding.iso2 == country)
        .order_by(Finding.position.desc())
    ):
        slugs[week] = slug  # lowest position wins
    weeks = [
        TimelineWeek(
            week_start_date=w.week_start_date,
            country_iso=w.iso2,
            regime_state=w.primary_regime,
            confidence_level=w.confidence_level,
            finding_slug=slugs.get(w.week_start_date),
        )
        for w in session.scalars(stmt)
    ]
    return TimelineResponse(snapshot_version=snapshot.version, country=country, weeks=weeks)
