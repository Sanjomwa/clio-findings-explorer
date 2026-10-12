from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification import pre_transition_target
from app.db.models import Finding, FindingCaveat, RegimeWeek
from app.deps import get_session, require_snapshot
from app.evidence.service import SOURCES, build_card
from app.routers.common import NO_SNAPSHOT, SlugPath, get_finding_or_404
from app.schemas import (
    Caveat,
    Citation,
    FindingDetail,
    FindingDetailResponse,
    FindingListResponse,
    FindingSummary,
    SourceRef,
    WeekClassification,
)

router = APIRouter()


@router.get("/api/findings", response_model=FindingListResponse, responses=NO_SNAPSHOT)
def list_findings(session: Annotated[Session, Depends(get_session)]):
    snapshot = require_snapshot(session)
    rows = session.execute(
        select(Finding, RegimeWeek)
        .join(
            RegimeWeek,
            (RegimeWeek.iso2 == Finding.iso2)
            & (RegimeWeek.week_start_date == Finding.week_start_date),
        )
        .order_by(Finding.position)
    )
    return FindingListResponse(
        snapshot_version=snapshot.version,
        findings=[
            FindingSummary(
                slug=f.slug,
                title=f.title,
                week_start_date=f.week_start_date,
                country_iso=f.iso2,
                regime_state=w.primary_regime,
                confidence_level=w.confidence_level,
                teaser=f.teaser,
            )
            for f, w in rows
        ],
    )


def _source_ref(source: str, attribution: dict, version: str) -> SourceRef:
    a = attribution[source]
    return SourceRef(
        source=source,
        name=a["name"],
        provenance_note=(
            f"{a['name']}. Licence: {a['licence']}. Filter: {a['filter']}. "
            f"Manipulation: {a['manipulation']}. Snapshot version {version}."
        ),
    )


@router.get("/api/findings/{slug}", response_model=FindingDetailResponse, responses=NO_SNAPSHOT)
def get_finding(slug: SlugPath, session: Annotated[Session, Depends(get_session)]):
    snapshot = require_snapshot(session)
    finding, week = get_finding_or_404(session, slug)
    caveats = session.scalars(
        select(FindingCaveat)
        .where(FindingCaveat.finding_slug == slug)
        .order_by(FindingCaveat.position)
    ).all()
    available = [
        s
        for s in SOURCES
        if build_card(
            session, s, slug, finding.week_start_date, snapshot.attribution, snapshot.version
        )["has_data"]
    ]
    return FindingDetailResponse(
        snapshot_version=snapshot.version,
        finding=FindingDetail(
            slug=finding.slug,
            title=finding.title,
            week_start_date=finding.week_start_date,
            country_iso=finding.iso2,
            regime_state=week.primary_regime,
            confidence_level=week.confidence_level,
            classification=WeekClassification(
                protest_band=week.protest_band,
                violence_band=week.violence_band,
                suppression_band=week.suppression_band,
                previous_regime=week.previous_regime,
                pre_transition_target=pre_transition_target(week.classification_reason),
            ),
            summary_md=finding.summary_md,
            caveats=[Caveat(severity=c.severity, caveat_md=c.caveat_md) for c in caveats],
            sources=[_source_ref(s, snapshot.attribution, snapshot.version) for s in SOURCES],
            citations=[Citation(**c) for c in finding.citations],
            evidence_available=available,
            published_at=finding.published_at,
        ),
    )
