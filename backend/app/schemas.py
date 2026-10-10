"""Pydantic v2 response models mirroring the schemas in openapi.yaml (v0.4.0)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

RegimeState = Literal[
    "STABLE", "MOBILISATION", "CONTESTATION", "ESCALATION", "CRISIS", "REPRESSION", "CONFLICT"
]
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA"]
FamilyBand = Literal["NORMAL", "ELEVATED", "SEVERE", "UNKNOWN"]
EvidenceSource = Literal["acled", "ooni", "google_transparency"]
CaveatSeverity = Literal["limitation", "do_not_conclude"]

OONI_NOTE = (
    "These OONI tests detect blocking of specific apps and sites. A general "
    "network shutdown produces no measurements, so it cannot show up as an "
    "anomaly here."
)


class Error(BaseModel):
    detail: str


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["reachable", "unreachable"]
    snapshot_version: str | None
    migration_head: str | None
    row_counts: dict[str, int]


class TimelineWeek(BaseModel):
    week_start_date: date
    country_iso: str
    regime_state: RegimeState
    confidence_level: ConfidenceLevel
    finding_slug: str | None


class TimelineResponse(BaseModel):
    snapshot_version: str
    country: str
    weeks: list[TimelineWeek]


class FindingSummary(BaseModel):
    slug: str
    title: str
    week_start_date: date
    country_iso: str
    regime_state: RegimeState
    confidence_level: ConfidenceLevel
    teaser: str


class FindingListResponse(BaseModel):
    snapshot_version: str
    findings: list[FindingSummary]


class Caveat(BaseModel):
    severity: CaveatSeverity
    caveat_md: str


class SourceRef(BaseModel):
    source: EvidenceSource
    name: str
    provenance_note: str


class WeekClassification(BaseModel):
    protest_band: FamilyBand
    violence_band: FamilyBand
    suppression_band: FamilyBand
    previous_regime: RegimeState
    pre_transition_target: RegimeState | None


class FindingDetail(BaseModel):
    slug: str
    title: str
    week_start_date: date
    country_iso: str
    regime_state: RegimeState
    confidence_level: ConfidenceLevel
    classification: WeekClassification
    summary_md: str
    caveats: list[Caveat]
    sources: list[SourceRef]
    evidence_available: list[EvidenceSource]
    published_at: datetime


class FindingDetailResponse(BaseModel):
    snapshot_version: str
    finding: FindingDetail


class EvidenceComparison(BaseModel):
    label: str
    value: float


class AcledSignalWeek(BaseModel):
    week_start_date: date
    total_events: int
    total_fatalities: int
    signal_valid: bool
    protest_pressure_z: float | None
    violence_pressure_z: float | None
    suppression_z: float | None
    protest_active_baseline_weeks: int
    violence_active_baseline_weeks: int
    suppression_active_baseline_weeks: int
    sparse_protest_baseline_flag: bool
    sparse_violence_baseline_flag: bool
    sparse_suppression_baseline_flag: bool
    zero_variance_flag: bool
    low_event_density_flag: bool
    high_methodology_risk_flag: bool


class AcledSupporting(BaseModel):
    kind: Literal["acled"] = "acled"
    classifier_input: Literal[True] = True
    week: AcledSignalWeek
    prior_12_week_median_events: float | None
    prior_12_week_median_fatalities: float | None
    series: list[AcledSignalWeek]


class OoniTestWeek(BaseModel):
    week_start_date: date
    test_name: str
    anomalous_total_scored: int | None
    anomalous_count: int | None
    anomalous_rate: float | None
    anomalous_baseline_rate_12w: float | None
    anomalous_zscore_12w: float | None
    anomalous_low_sample_flag: bool
    anomalous_sparse_baseline_flag: bool
    blocked_total_observations: int
    blocked_count: int
    blocked_rate: float
    blocked_baseline_rate_12w: float | None
    blocked_zscore_12w: float | None
    blocked_low_sample_flag: bool
    blocked_sparse_baseline_flag: bool
    feature_version: str


class OoniSupporting(BaseModel):
    kind: Literal["ooni"] = "ooni"
    top_test: str | None
    tests: list[OoniTestWeek]
    note: Literal[
        "These OONI tests detect blocking of specific apps and sites. A general "
        "network shutdown produces no measurements, so it cannot show up as an "
        "anomaly here."
    ] = OONI_NOTE


class GoogleTransparencyRow(BaseModel):
    requestor: str
    product: str
    reason: str
    number_of_requests: int
    items_requested_removal: int
    items_removed_legal: int
    items_removed_policy: int


class GoogleTotals(BaseModel):
    number_of_requests: int
    items_requested_removal: int
    items_removed_legal: int
    items_removed_policy: int


class GoogleTransparencySupporting(BaseModel):
    kind: Literal["google_transparency"] = "google_transparency"
    time_period: str
    totals: GoogleTotals
    rows: list[GoogleTransparencyRow]


class EvidenceCard(BaseModel):
    slug: str
    source: EvidenceSource
    has_data: bool
    period_start: date | None
    period_end: date | None
    period_grain: Literal["week", "month", "half_year", "other"]
    headline_metric: str
    metric_value: float | int | str | None
    comparison: EvidenceComparison | None
    provenance_note: str
    snapshot_files: list[str]
    supporting: AcledSupporting | OoniSupporting | GoogleTransparencySupporting | None


class EvidenceCardResponse(BaseModel):
    snapshot_version: str
    evidence: EvidenceCard


class RegimeStateDefinition(BaseModel):
    state: RegimeState
    definition: str


class ConfidenceLevelDefinition(BaseModel):
    level: ConfidenceLevel
    definition: str


class FamilyBandDefinition(BaseModel):
    band: FamilyBand
    definition: str


class SourceNote(BaseModel):
    source: EvidenceSource
    name: str
    note: str


class SnapshotTable(BaseModel):
    file: str
    source_table: str
    sql: str
    row_count: int
    exported_at: datetime


class SnapshotManifest(BaseModel):
    version: str
    exported_at: datetime
    tables: list[SnapshotTable]


class MethodologyResponse(BaseModel):
    snapshot_version: str
    regime_states: list[RegimeStateDefinition]
    confidence_levels: list[ConfidenceLevelDefinition]
    family_bands: list[FamilyBandDefinition]
    sources: list[SourceNote]
    manifest: SnapshotManifest
