from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_session, require_snapshot
from app.evidence.service import build_card
from app.routers.common import NO_SNAPSHOT, SlugPath, get_finding_or_404
from app.schemas import EvidenceCard, EvidenceCardResponse

router = APIRouter()


def _card(session: Session, source: str, slug: str) -> EvidenceCardResponse:
    snapshot = require_snapshot(session)
    finding, _ = get_finding_or_404(session, slug)
    card = build_card(
        session, source, slug, finding.week_start_date, snapshot.attribution, snapshot.version
    )
    return EvidenceCardResponse(
        snapshot_version=snapshot.version, evidence=EvidenceCard.model_validate(card)
    )


@router.get(
    "/api/findings/{slug}/evidence/acled",
    response_model=EvidenceCardResponse,
    responses=NO_SNAPSHOT,
)
def get_acled_evidence(slug: SlugPath, session: Annotated[Session, Depends(get_session)]):
    return _card(session, "acled", slug)


@router.get(
    "/api/findings/{slug}/evidence/ooni", response_model=EvidenceCardResponse, responses=NO_SNAPSHOT
)
def get_ooni_evidence(slug: SlugPath, session: Annotated[Session, Depends(get_session)]):
    return _card(session, "ooni", slug)


@router.get(
    "/api/findings/{slug}/evidence/google-transparency",
    response_model=EvidenceCardResponse,
    responses=NO_SNAPSHOT,
)
def get_google_transparency_evidence(
    slug: SlugPath, session: Annotated[Session, Depends(get_session)]
):
    return _card(session, "google_transparency", slug)
