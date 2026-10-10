from typing import Annotated

from fastapi import HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Finding, RegimeWeek
from app.schemas import Error

NO_SNAPSHOT = {503: {"model": Error, "description": "No snapshot is loaded."}}

SlugPath = Annotated[str, Path(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)]


def get_finding_or_404(session: Session, slug: str) -> tuple[Finding, RegimeWeek]:
    row = session.execute(
        select(Finding, RegimeWeek)
        .join(
            RegimeWeek,
            (RegimeWeek.iso2 == Finding.iso2)
            & (RegimeWeek.week_start_date == Finding.week_start_date),
        )
        .where(Finding.slug == slug)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No finding with slug '{slug}'.")
    return row[0], row[1]
