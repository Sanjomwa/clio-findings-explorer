from datetime import date, timedelta

from app.evidence import median_or_none, week_end

SNAPSHOT_FILE = "acled_signal_context.ndjson"
HEADLINE = "Conflict events recorded in the week (all event types)"
COMPARISON_LABEL = "Median of the 12 weeks before"
WEEKS_BEFORE, WEEKS_AFTER = 12, 4

FIELDS = (
    "week_start_date", "total_events", "total_fatalities", "signal_valid",
    "protest_pressure_z", "violence_pressure_z", "suppression_z",
    "protest_active_baseline_weeks", "violence_active_baseline_weeks",
    "suppression_active_baseline_weeks", "sparse_protest_baseline_flag",
    "sparse_violence_baseline_flag", "sparse_suppression_baseline_flag",
    "zero_variance_flag", "low_event_density_flag", "high_methodology_risk_flag",
)  # fmt: skip


def window(anchor: date) -> tuple[date, date]:
    """First and last week_start_date of the anchor's 17-week window."""
    return (
        anchor - timedelta(weeks=WEEKS_BEFORE),
        anchor + timedelta(weeks=WEEKS_AFTER),
    )


def _week(row: dict) -> dict:
    return {k: row[k] for k in FIELDS}


def acled_card(
    slug: str, anchor: date, rows: list[dict], source_name: str, snapshot_version: str
) -> dict:
    """rows: acled_signal_context rows, any order; rows outside the anchor's window are ignored."""
    first, last = window(anchor)
    series = sorted((r for r in rows if first <= r["week_start_date"] <= last),
                    key=lambda r: r["week_start_date"])  # fmt: skip
    anchor_row = next((r for r in series if r["week_start_date"] == anchor), None)
    prior = [r for r in series if r["week_start_date"] < anchor]
    base = {
        "slug": slug,
        "source": "acled",
        "period_grain": "week",
        "headline_metric": HEADLINE,
        "snapshot_files": [SNAPSHOT_FILE],
    }
    where = (
        f"{source_name}, snapshot table acled_signal_context, snapshot version {snapshot_version}"
    )
    if anchor_row is None:
        return {
            **base,
            "has_data": False,
            "period_start": None,
            "period_end": None,
            "metric_value": None,
            "comparison": None,
            "supporting": None,
            "provenance_note": f"{where}. The snapshot has no row for the week starting {anchor}.",
        }
    med_events = median_or_none([r["total_events"] for r in prior])
    med_fatalities = median_or_none([r["total_fatalities"] for r in prior])
    comparison = None if med_events is None else {"label": COMPARISON_LABEL, "value": med_events}
    return {
        **base,
        "has_data": True,
        "period_start": anchor,
        "period_end": week_end(anchor),
        "metric_value": anchor_row["total_events"],
        "comparison": comparison,
        "supporting": {
            "kind": "acled",
            "classifier_input": True,
            "week": _week(anchor_row),
            "prior_12_week_median_events": med_events,
            "prior_12_week_median_fatalities": med_fatalities,
            "series": [_week(r) for r in series],
        },
        "provenance_note": (
            f"{where}. Total events for the week starting {anchor}, against the median of the "
            f"{len(prior)} weeks before it. This source is the classifier's own input, so it is "
            "not independent corroboration of the classification."
        ),
    }
