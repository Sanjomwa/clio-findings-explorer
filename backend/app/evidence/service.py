"""Database side of the evidence cards: fetch the rows, hand them to the pure functions."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AcledSignalContext, GoogleTransparencyRequest, OoniWeeklySignal
from app.evidence import acled, google, ooni
from app.evidence.google import half_year

SOURCES = ("acled", "ooni", "google_transparency")


def _rows(session: Session, model, *where) -> list[dict]:
    stmt = select(*model.__table__.c).where(*where)
    return [dict(r) for r in session.execute(stmt).mappings()]


def build_card(
    session: Session, source: str, slug: str, anchor: date, attribution: dict, version: str
) -> dict[str, Any]:
    name = attribution[source]["name"]
    if source == "acled":
        first, last = acled.window(anchor)
        rows = _rows(
            session,
            AcledSignalContext,
            AcledSignalContext.week_start_date.between(first, last),
        )
        return acled.acled_card(slug, anchor, rows, name, version)
    if source == "ooni":
        rows = _rows(session, OoniWeeklySignal, OoniWeeklySignal.week_start_date == anchor)
        return ooni.ooni_card(slug, anchor, rows, name, version)
    rows = _rows(
        session,
        GoogleTransparencyRequest,
        GoogleTransparencyRequest.period_date == half_year(anchor)[2],
    )
    return google.google_card(slug, anchor, rows, name, version)
