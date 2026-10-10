from datetime import date

from app.evidence import week_end
from app.schemas import OONI_NOTE

SNAPSHOT_FILE = "ooni_weekly_signals.ndjson"
HEADLINE = "Anomalous measurement rate, for the test furthest above its own 12-week baseline"


def ooni_card(
    slug: str, anchor: date, rows: list[dict], source_name: str, snapshot_version: str
) -> dict:
    """rows: ooni_weekly_signals rows; only those of the anchor week are used."""
    tests = sorted((r for r in rows if r["week_start_date"] == anchor),
                   key=lambda r: r["test_name"])  # fmt: skip
    base = {
        "slug": slug,
        "source": "ooni",
        "period_grain": "week",
        "headline_metric": HEADLINE,
        "snapshot_files": [SNAPSHOT_FILE],
    }
    where = (
        f"{source_name}, snapshot table ooni_weekly_signals, snapshot version {snapshot_version}"
    )
    if not tests:
        return {
            **base,
            "has_data": False,
            "period_start": None,
            "period_end": None,
            "metric_value": None,
            "comparison": None,
            "supporting": None,
            "provenance_note": (
                f"{where}. The snapshot has no OONI rows for the week starting {anchor}."
            ),
        }
    scored = [r for r in tests if r["anomalous_zscore_12w"] is not None]
    top = min(scored, key=lambda r: (-r["anomalous_zscore_12w"], r["test_name"]), default=None)
    common = {
        **base,
        "has_data": True,
        "period_start": anchor,
        "period_end": week_end(anchor),
    }
    supporting = {
        "kind": "ooni",
        "top_test": top["test_name"] if top else None,
        "tests": tests,
        "note": OONI_NOTE,
    }
    if top is None:
        return {
            **common,
            "metric_value": None,
            "comparison": None,
            "supporting": supporting,
            "provenance_note": (
                f"{where}. Week starting {anchor}. No baseline was available: every "
                "anomalous z-score in this week is null."
            ),
        }
    return {
        **common,
        "metric_value": top["anomalous_rate"],
        "comparison": {
            "label": f"{top['test_name']}: standard deviations from its own 12-week baseline",
            "value": top["anomalous_zscore_12w"],
        },
        "supporting": supporting,
        "provenance_note": (
            f"{where}. Week starting {anchor}; the test shown is the one with the highest "
            "anomalous z-score against its own 12-week baseline (ties broken by test name)."
        ),
    }
