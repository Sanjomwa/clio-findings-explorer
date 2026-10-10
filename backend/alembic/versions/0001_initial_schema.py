"""Initial schema: snapshot tables, snapshot metadata, findings and caveats.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

REGIMES = "('STABLE','MOBILISATION','CONTESTATION','ESCALATION','CRISIS','REPRESSION','CONFLICT')"
CONFIDENCE = "('HIGH','MEDIUM','LOW','INSUFFICIENT_DATA')"
BANDS = "('NORMAL','ELEVATED','SEVERE','UNKNOWN')"


def _col(name, type_, nullable=False, **kw):
    return sa.Column(name, type_, nullable=nullable, **kw)


T, D, TS, B, INT, F = (
    sa.Text(),
    sa.Date(),
    sa.DateTime(timezone=True),
    sa.Boolean(),
    sa.Integer(),
    sa.Double(),
)


def upgrade() -> None:
    op.create_table(
        "regime_weeks",
        _col("iso2", T),
        _col("week_start_date", D),
        _col("country", T),
        _col("primary_regime", T),
        _col("confidence_level", T),
        _col("previous_regime", T),
        _col("transition_detected", B),
        _col("transition_type", T),
        _col("regime_duration_weeks", INT),
        _col("weeks_in_current_regime", INT),
        _col("regime_held_by_exit_persistence", B),
        _col("fallback_used", B),
        _col("methodology_caveat_required", B),
        _col("protest_band", T),
        _col("violence_band", T),
        _col("suppression_band", T),
        _col("velocity_band", T, nullable=True),
        _col("conversion_band", T, nullable=True),
        _col("classification_reason", T),
        _col("regime_methodology_version", T),
        _col("feature_version", T),
        _col("computed_at", TS),
        sa.PrimaryKeyConstraint("iso2", "week_start_date"),
        sa.CheckConstraint(f"primary_regime IN {REGIMES}", name="ck_regime_weeks_primary_regime"),
        sa.CheckConstraint(f"previous_regime IN {REGIMES}", name="ck_regime_weeks_previous_regime"),
        sa.CheckConstraint(
            f"confidence_level IN {CONFIDENCE}", name="ck_regime_weeks_confidence_level"
        ),
        sa.CheckConstraint(f"protest_band IN {BANDS}", name="ck_regime_weeks_protest_band"),
        sa.CheckConstraint(f"violence_band IN {BANDS}", name="ck_regime_weeks_violence_band"),
        sa.CheckConstraint(f"suppression_band IN {BANDS}", name="ck_regime_weeks_suppression_band"),
    )

    op.create_table(
        "acled_signal_context",
        _col("week_start_date", D),
        _col("total_events", INT),
        _col("total_fatalities", INT),
        _col("signal_valid", B),
        _col("protest_pressure_z", F, nullable=True),
        _col("violence_pressure_z", F, nullable=True),
        _col("suppression_z", F, nullable=True),
        _col("protest_active_baseline_weeks", INT),
        _col("violence_active_baseline_weeks", INT),
        _col("suppression_active_baseline_weeks", INT),
        _col("sparse_protest_baseline_flag", B),
        _col("sparse_violence_baseline_flag", B),
        _col("sparse_suppression_baseline_flag", B),
        _col("zero_variance_flag", B),
        _col("low_event_density_flag", B),
        _col("high_methodology_risk_flag", B),
        sa.PrimaryKeyConstraint("week_start_date"),
    )

    op.create_table(
        "ooni_weekly_signals",
        _col("week_start_date", D),
        _col("test_name", T),
        _col("anomalous_total_scored", INT, nullable=True),
        _col("anomalous_count", INT, nullable=True),
        _col("anomalous_rate", F, nullable=True),
        _col("anomalous_baseline_rate_12w", F, nullable=True),
        _col("anomalous_zscore_12w", F, nullable=True),
        _col("anomalous_low_sample_flag", B),
        _col("anomalous_sparse_baseline_flag", B),
        _col("blocked_total_observations", INT),
        _col("blocked_count", INT),
        _col("blocked_rate", F),
        _col("blocked_baseline_rate_12w", F, nullable=True),
        _col("blocked_zscore_12w", F, nullable=True),
        _col("blocked_low_sample_flag", B),
        _col("blocked_sparse_baseline_flag", B),
        _col("feature_version", T),
        sa.PrimaryKeyConstraint("week_start_date", "test_name"),
    )

    op.create_table(
        "google_transparency_requests",
        _col("period_date", D),
        _col("requestor", T),
        _col("product", T),
        _col("reason", T),
        _col("time_period", T),
        _col("number_of_requests", INT),
        _col("items_requested_removal", INT),
        _col("items_removed_legal", INT),
        _col("items_removed_policy", INT),
        sa.PrimaryKeyConstraint("period_date", "requestor", "product", "reason"),
    )

    op.create_table(
        "snapshot_meta",
        _col("version", T),
        _col("exported_at", TS),
        _col("acled_access_date", D),
        _col("loaded_at", TS, server_default=sa.text("now()")),
        _col("manifest", postgresql.JSONB()),
        sa.PrimaryKeyConstraint("version"),
    )
    # "Exactly one row": every row maps to the same constant, so a second row violates the index.
    op.execute("CREATE UNIQUE INDEX uq_snapshot_meta_single_row ON snapshot_meta ((true))")

    op.create_table(
        "snapshot_tables",
        _col("file", T),
        _col("source_table", T),
        _col("sql", T),
        _col("row_count", INT),
        _col("sha256", T),
        _col("exported_at", TS),
        sa.PrimaryKeyConstraint("file"),
    )

    op.create_table(
        "findings",
        _col("slug", T),
        _col("iso2", T),
        _col("week_start_date", D),
        _col("title", T),
        _col("teaser", T),
        _col("summary_md", T),
        _col("published_at", TS),
        _col("position", INT),
        sa.PrimaryKeyConstraint("slug"),
        sa.UniqueConstraint("position", name="uq_findings_position"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_findings_slug_pattern"),
        # Deferred so the seed can reload snapshot rows inside one transaction; the seed
        # pre-checks and gives a clear message when a referenced week would vanish.
        sa.ForeignKeyConstraint(
            ["iso2", "week_start_date"],
            ["regime_weeks.iso2", "regime_weeks.week_start_date"],
            name="fk_findings_regime_week",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    op.create_table(
        "finding_caveats",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        _col("finding_slug", T),
        _col("position", INT),
        _col("severity", T),
        _col("caveat_md", T),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["finding_slug"], ["findings.slug"], name="fk_finding_caveats_slug", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("finding_slug", "position", name="uq_finding_caveats_slug_position"),
        sa.CheckConstraint(
            "severity IN ('limitation','do_not_conclude')", name="ck_finding_caveats_severity"
        ),
        sa.CheckConstraint("btrim(caveat_md) <> ''", name="ck_finding_caveats_caveat_md_not_blank"),
    )

    # A finding with no caveat cannot exist. Checked at commit, so a finding and its first
    # caveat can be inserted in either order inside one transaction.
    op.execute(
        """
        CREATE FUNCTION enforce_finding_has_caveat() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            affected text;
        BEGIN
            IF TG_TABLE_NAME = 'findings' THEN
                affected := NEW.slug;
            ELSE
                -- DELETE, or UPDATE of finding_slug: the finding named by OLD lost a caveat.
                affected := OLD.finding_slug;
            END IF;
            IF EXISTS (SELECT 1 FROM findings WHERE slug = affected)
               AND NOT EXISTS (SELECT 1 FROM finding_caveats WHERE finding_slug = affected) THEN
                RAISE EXCEPTION 'finding % must have at least one caveat', affected
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_findings_require_caveat
        AFTER INSERT ON findings
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_finding_has_caveat()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_caveats_keep_finding_valid
        AFTER DELETE OR UPDATE OF finding_slug ON finding_caveats
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_finding_has_caveat()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_caveats_keep_finding_valid ON finding_caveats")
    op.execute("DROP TRIGGER IF EXISTS trg_findings_require_caveat ON findings")
    op.execute("DROP FUNCTION IF EXISTS enforce_finding_has_caveat()")
    op.drop_table("finding_caveats")
    op.drop_table("findings")
    op.drop_table("snapshot_tables")
    op.execute("DROP INDEX IF EXISTS uq_snapshot_meta_single_row")
    op.drop_table("snapshot_meta")
    op.drop_table("google_transparency_requests")
    op.drop_table("ooni_weekly_signals")
    op.drop_table("acled_signal_context")
    op.drop_table("regime_weeks")
