"""SQLAlchemy 2.0 models. The Alembic migration is the schema of record; these mirror it."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

REGIME_STATES = (
    "STABLE",
    "MOBILISATION",
    "CONTESTATION",
    "ESCALATION",
    "CRISIS",
    "REPRESSION",
    "CONFLICT",
)
CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA")
FAMILY_BANDS = ("NORMAL", "ELEVATED", "SEVERE", "UNKNOWN")
CAVEAT_SEVERITIES = ("limitation", "do_not_conclude")
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


def in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class RegimeWeek(Base):
    __tablename__ = "regime_weeks"
    __table_args__ = (
        CheckConstraint(
            in_list("primary_regime", REGIME_STATES), name="ck_regime_weeks_primary_regime"
        ),
        CheckConstraint(
            in_list("previous_regime", REGIME_STATES), name="ck_regime_weeks_previous_regime"
        ),
        CheckConstraint(
            in_list("confidence_level", CONFIDENCE_LEVELS), name="ck_regime_weeks_confidence_level"
        ),
        CheckConstraint(in_list("protest_band", FAMILY_BANDS), name="ck_regime_weeks_protest_band"),
        CheckConstraint(
            in_list("violence_band", FAMILY_BANDS), name="ck_regime_weeks_violence_band"
        ),
        CheckConstraint(
            in_list("suppression_band", FAMILY_BANDS), name="ck_regime_weeks_suppression_band"
        ),
    )

    iso2: Mapped[str] = mapped_column(Text, primary_key=True)
    week_start_date: Mapped[date] = mapped_column(Date, primary_key=True)
    country: Mapped[str] = mapped_column(Text)
    primary_regime: Mapped[str] = mapped_column(Text)
    confidence_level: Mapped[str] = mapped_column(Text)
    previous_regime: Mapped[str] = mapped_column(Text)
    transition_detected: Mapped[bool] = mapped_column(Boolean)
    transition_type: Mapped[str] = mapped_column(Text)
    regime_duration_weeks: Mapped[int] = mapped_column(Integer)
    weeks_in_current_regime: Mapped[int] = mapped_column(Integer)
    regime_held_by_exit_persistence: Mapped[bool] = mapped_column(Boolean)
    fallback_used: Mapped[bool] = mapped_column(Boolean)
    methodology_caveat_required: Mapped[bool] = mapped_column(Boolean)
    protest_band: Mapped[str] = mapped_column(Text)
    violence_band: Mapped[str] = mapped_column(Text)
    suppression_band: Mapped[str] = mapped_column(Text)
    velocity_band: Mapped[str | None] = mapped_column(Text)
    conversion_band: Mapped[str | None] = mapped_column(Text)
    classification_reason: Mapped[str] = mapped_column(Text)
    regime_methodology_version: Mapped[str] = mapped_column(Text)
    feature_version: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AcledSignalContext(Base):
    __tablename__ = "acled_signal_context"

    week_start_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_events: Mapped[int] = mapped_column(Integer)
    total_fatalities: Mapped[int] = mapped_column(Integer)
    signal_valid: Mapped[bool] = mapped_column(Boolean)
    protest_pressure_z: Mapped[float | None] = mapped_column(Double)
    violence_pressure_z: Mapped[float | None] = mapped_column(Double)
    suppression_z: Mapped[float | None] = mapped_column(Double)
    protest_active_baseline_weeks: Mapped[int] = mapped_column(Integer)
    violence_active_baseline_weeks: Mapped[int] = mapped_column(Integer)
    suppression_active_baseline_weeks: Mapped[int] = mapped_column(Integer)
    sparse_protest_baseline_flag: Mapped[bool] = mapped_column(Boolean)
    sparse_violence_baseline_flag: Mapped[bool] = mapped_column(Boolean)
    sparse_suppression_baseline_flag: Mapped[bool] = mapped_column(Boolean)
    zero_variance_flag: Mapped[bool] = mapped_column(Boolean)
    low_event_density_flag: Mapped[bool] = mapped_column(Boolean)
    high_methodology_risk_flag: Mapped[bool] = mapped_column(Boolean)


class OoniWeeklySignal(Base):
    __tablename__ = "ooni_weekly_signals"

    week_start_date: Mapped[date] = mapped_column(Date, primary_key=True)
    test_name: Mapped[str] = mapped_column(Text, primary_key=True)
    anomalous_total_scored: Mapped[int | None] = mapped_column(Integer)
    anomalous_count: Mapped[int | None] = mapped_column(Integer)
    anomalous_rate: Mapped[float | None] = mapped_column(Double)
    anomalous_baseline_rate_12w: Mapped[float | None] = mapped_column(Double)
    anomalous_zscore_12w: Mapped[float | None] = mapped_column(Double)
    anomalous_low_sample_flag: Mapped[bool] = mapped_column(Boolean)
    anomalous_sparse_baseline_flag: Mapped[bool] = mapped_column(Boolean)
    blocked_total_observations: Mapped[int] = mapped_column(Integer)
    blocked_count: Mapped[int] = mapped_column(Integer)
    blocked_rate: Mapped[float] = mapped_column(Double)
    blocked_baseline_rate_12w: Mapped[float | None] = mapped_column(Double)
    blocked_zscore_12w: Mapped[float | None] = mapped_column(Double)
    blocked_low_sample_flag: Mapped[bool] = mapped_column(Boolean)
    blocked_sparse_baseline_flag: Mapped[bool] = mapped_column(Boolean)
    feature_version: Mapped[str] = mapped_column(Text)


class GoogleTransparencyRequest(Base):
    __tablename__ = "google_transparency_requests"

    period_date: Mapped[date] = mapped_column(Date, primary_key=True)
    requestor: Mapped[str] = mapped_column(Text, primary_key=True)
    product: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(Text, primary_key=True)
    time_period: Mapped[str] = mapped_column(Text)
    number_of_requests: Mapped[int] = mapped_column(Integer)
    items_requested_removal: Mapped[int] = mapped_column(Integer)
    items_removed_legal: Mapped[int] = mapped_column(Integer)
    items_removed_policy: Mapped[int] = mapped_column(Integer)


class SnapshotMeta(Base):
    """Exactly one row: the loaded snapshot."""

    __tablename__ = "snapshot_meta"
    __table_args__ = (Index("uq_snapshot_meta_single_row", text("(true)"), unique=True),)

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acled_access_date: Mapped[date] = mapped_column(Date)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    manifest: Mapped[dict] = mapped_column(JSONB)


class SnapshotTable(Base):
    __tablename__ = "snapshot_tables"

    file: Mapped[str] = mapped_column(Text, primary_key=True)
    source_table: Mapped[str] = mapped_column(Text)
    sql: Mapped[str] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint(f"slug ~ '{SLUG_PATTERN}'", name="ck_findings_slug_pattern"),
        ForeignKeyConstraint(
            ["iso2", "week_start_date"],
            ["regime_weeks.iso2", "regime_weeks.week_start_date"],
            name="fk_findings_regime_week",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    iso2: Mapped[str] = mapped_column(Text)
    week_start_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(Text)
    teaser: Mapped[str] = mapped_column(Text)
    summary_md: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    position: Mapped[int] = mapped_column(Integer, unique=True)
    citations: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class FindingCaveat(Base):
    __tablename__ = "finding_caveats"
    __table_args__ = (
        UniqueConstraint("finding_slug", "position", name="uq_finding_caveats_slug_position"),
        CheckConstraint(in_list("severity", CAVEAT_SEVERITIES), name="ck_finding_caveats_severity"),
        CheckConstraint("btrim(caveat_md) <> ''", name="ck_finding_caveats_caveat_md_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    finding_slug: Mapped[str] = mapped_column(Text, ForeignKey("findings.slug", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(Text)
    caveat_md: Mapped[str] = mapped_column(Text)
