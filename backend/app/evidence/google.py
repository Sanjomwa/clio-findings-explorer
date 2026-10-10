from datetime import date

SNAPSHOT_FILE = "google_transparency_requests.ndjson"
HEADLINE = "Removal requests in Google's government-requests report for Kenya, this half-year"
FIRST_COVERED = date(2012, 7, 1)  # snapshot data begins with July to December 2012
COUNT_FIELDS = (
    "number_of_requests",
    "items_requested_removal",
    "items_removed_legal",
    "items_removed_policy",
)


def half_year(anchor: date) -> tuple[date, date, date]:
    """(period_start, period_end, period_date) of the half-year containing `anchor`."""
    if anchor.month <= 6:
        return date(anchor.year, 1, 1), date(anchor.year, 6, 30), date(anchor.year, 6, 1)
    return date(anchor.year, 7, 1), date(anchor.year, 12, 31), date(anchor.year, 12, 1)


def google_card(
    slug: str, anchor: date, rows: list[dict], source_name: str, snapshot_version: str
) -> dict:
    """rows: google_transparency_requests rows; only the anchor's half-year is used."""
    start, end, period_date = half_year(anchor)
    chosen = sorted((r for r in rows if r["period_date"] == period_date),
                    key=lambda r: (r["requestor"], r["product"], r["reason"]))  # fmt: skip
    base = {
        "slug": slug,
        "source": "google_transparency",
        "period_grain": "half_year",
        "headline_metric": HEADLINE,
        "comparison": None,
        "snapshot_files": [SNAPSHOT_FILE],
    }
    where = (
        f"{source_name}, snapshot table google_transparency_requests, "
        f"snapshot version {snapshot_version}"
    )
    if not chosen:
        note = f"{where}. The snapshot has no rows for the half-year {start} to {end}."
        if start < FIRST_COVERED:
            note += " The snapshot's Google data begins with July to December 2012."
        return {
            **base,
            "has_data": False,
            "period_start": None,
            "period_end": None,
            "metric_value": None,
            "supporting": None,
            "provenance_note": note,
        }
    totals = {f: sum(r[f] for r in chosen) for f in COUNT_FIELDS}
    time_period = chosen[0]["time_period"]
    return {
        **base,
        "has_data": True,
        "period_start": start,
        "period_end": end,
        "metric_value": totals["number_of_requests"],
        "supporting": {
            "kind": "google_transparency",
            "time_period": time_period,
            "totals": totals,
            "rows": [
                {k: r[k] for k in ("requestor", "product", "reason", *COUNT_FIELDS)} for r in chosen
            ],
        },
        "provenance_note": (
            f"{where}. Half-year {start} to {end} ({time_period}); this is a half-year "
            "figure, not a figure for the finding's week."
        ),
    }
