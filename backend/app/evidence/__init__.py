"""Evidence-card logic: pure functions from snapshot rows to a card dict (no database access)."""

from datetime import date, timedelta
from statistics import median


def median_or_none(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def week_end(anchor: date) -> date:
    return anchor + timedelta(days=6)
