from datetime import date, timedelta

import pytest

from app.classification import pre_transition_target
from app.evidence import median_or_none
from app.evidence.acled import FIELDS, acled_card
from app.evidence.google import google_card, half_year
from app.evidence.ooni import ooni_card

V = "9999-01-01.1"


def test_median_odd_even_empty():
    assert median_or_none([3, 1, 2]) == 2.0
    assert median_or_none([1, 2, 3, 10]) == 2.5
    assert median_or_none([]) is None


def acled_row(week: date, events: int, fatalities: int = 0) -> dict:
    row = {k: 0 for k in FIELDS}
    row |= {
        "week_start_date": week,
        "total_events": events,
        "total_fatalities": fatalities,
        "signal_valid": True,
        "protest_pressure_z": None,
        "violence_pressure_z": None,
        "suppression_z": None,
    }
    row |= {k: False for k in FIELDS if k.endswith("_flag")}
    return row


def test_acled_series_is_17_weeks_oldest_first_and_median_of_prior_12():
    anchor = date(2024, 6, 22)
    # Rows deliberately shuffled and including weeks outside the window.
    weeks = [anchor + timedelta(weeks=i) for i in range(-14, 7)]
    rows = [acled_row(w, events=i + 1, fatalities=i) for i, w in enumerate(weeks)]
    rows.reverse()
    card = acled_card("s", anchor, rows, "ACLED", V)
    series = card["supporting"]["series"]
    assert len(series) == 17
    assert series[0]["week_start_date"] == anchor - timedelta(weeks=12)
    assert series[-1]["week_start_date"] == anchor + timedelta(weeks=4)
    assert [s["week_start_date"] for s in series] == sorted(s["week_start_date"] for s in series)
    prior_events = [
        r["total_events"]
        for r in rows
        if anchor - timedelta(weeks=12) <= r["week_start_date"] < anchor
    ]
    assert len(prior_events) == 12
    assert card["comparison"]["value"] == (sorted(prior_events)[5] + sorted(prior_events)[6]) / 2
    assert card["metric_value"] == next(
        r["total_events"] for r in rows if r["week_start_date"] == anchor
    )
    assert card["period_end"] == anchor + timedelta(days=6)
    assert card["supporting"]["classifier_input"] is True


def test_acled_no_anchor_row_has_no_data():
    card = acled_card("s", date(2024, 6, 22), [acled_row(date(2024, 6, 15), 3)], "ACLED", V)
    assert card["has_data"] is False
    assert card["metric_value"] is None and card["supporting"] is None
    assert card["period_start"] is None


def ooni_row(week: date, test: str, z, rate=0.1) -> dict:
    return {
        "week_start_date": week, "test_name": test, "anomalous_rate": rate,
        "anomalous_zscore_12w": z,
    }  # fmt: skip


WEEK = date(2024, 6, 22)


def test_ooni_top_test_is_highest_z():
    rows = [ooni_row(WEEK, "a", 0.5, 0.1), ooni_row(WEEK, "b", 2.0, 0.2), ooni_row(WEEK, "c", None)]
    card = ooni_card("s", WEEK, rows, "OONI", V)
    assert card["supporting"]["top_test"] == "b"
    assert card["metric_value"] == 0.2
    assert card["comparison"] == {
        "label": "b: standard deviations from its own 12-week baseline",
        "value": 2.0,
    }


def test_ooni_tie_breaks_alphabetically():
    rows = [ooni_row(WEEK, "whatsapp", 1.0), ooni_row(WEEK, "signal", 1.0)]
    card = ooni_card("s", WEEK, rows, "OONI", V)
    assert card["supporting"]["top_test"] == "signal"
    assert [t["test_name"] for t in card["supporting"]["tests"]] == ["signal", "whatsapp"]


def test_ooni_all_null_z_scores():
    card = ooni_card("s", WEEK, [ooni_row(WEEK, "a", None), ooni_row(WEEK, "b", None)], "OONI", V)
    assert card["has_data"] is True
    assert card["metric_value"] is None and card["comparison"] is None
    assert card["supporting"]["top_test"] is None
    assert "No baseline was available" in card["provenance_note"]


def test_ooni_no_rows_for_week():
    card = ooni_card("s", WEEK, [ooni_row(date(2024, 6, 15), "a", 1.0)], "OONI", V)
    assert card["has_data"] is False
    assert card["supporting"] is None and card["period_start"] is None


def google_row(period_date: date, n: int, requestor="Judicial", product="Web Search", reason="x"):
    return {
        "period_date": period_date, "time_period": "label", "requestor": requestor,
        "product": product, "reason": reason, "number_of_requests": n,
        "items_requested_removal": n, "items_removed_legal": 0, "items_removed_policy": 1,
    }  # fmt: skip


@pytest.mark.parametrize(
    ("anchor", "start", "end", "period_date"),
    [
        (date(2024, 1, 6), date(2024, 1, 1), date(2024, 6, 30), date(2024, 6, 1)),
        (date(2024, 6, 29), date(2024, 1, 1), date(2024, 6, 30), date(2024, 6, 1)),
        (date(2024, 7, 6), date(2024, 7, 1), date(2024, 12, 31), date(2024, 12, 1)),
        (date(2024, 12, 28), date(2024, 7, 1), date(2024, 12, 31), date(2024, 12, 1)),
    ],
)
def test_google_half_year_mapping(anchor, start, end, period_date):
    assert half_year(anchor) == (start, end, period_date)


def test_google_sums_and_sorts_rows():
    rows = [
        google_row(date(2024, 6, 1), 4, "B"),
        google_row(date(2024, 6, 1), 5, "A"),
        google_row(date(2024, 12, 1), 100, "A"),
    ]
    card = google_card("s", date(2024, 6, 22), rows, "Google", V)
    assert card["metric_value"] == 9
    assert card["comparison"] is None
    assert [r["requestor"] for r in card["supporting"]["rows"]] == ["A", "B"]
    assert card["supporting"]["totals"]["number_of_requests"] == 9
    assert (card["period_start"], card["period_end"]) == (date(2024, 1, 1), date(2024, 6, 30))


def test_google_period_with_no_rows_never_claims_zero():
    card = google_card("s", date(2022, 8, 6), [google_row(date(2024, 6, 1), 1)], "Google", V)
    assert card["has_data"] is False and card["metric_value"] is None
    assert "no rows" in card["provenance_note"]
    assert "begins with" not in card["provenance_note"]
    assert "zero" not in card["provenance_note"].lower()


def test_google_before_july_2012_note():
    card = google_card("s", date(2008, 1, 19), [], "Google", V)
    assert card["has_data"] is False
    assert "begins with July to December 2012" in card["provenance_note"]


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("x pre_transition:CRISIS y", "CRISIS"),
        ("something else", None),
        ("pre_transition:NOT_A_STATE", None),
        ("", None),
    ],
)
def test_pre_transition_parser(reason, expected):
    assert pre_transition_target(reason) == expected


def test_acled_no_earlier_weeks_gives_null_medians_and_comparison():
    anchor = date(2024, 6, 22)
    rows = [acled_row(anchor, 10, 2), acled_row(anchor + timedelta(weeks=1), 12, 3)]
    card = acled_card("s", anchor, rows, "ACLED", V)
    assert card["has_data"] is True
    assert card["metric_value"] == 10
    assert card["comparison"] is None
    assert card["supporting"]["prior_12_week_median_events"] is None
    assert card["supporting"]["prior_12_week_median_fatalities"] is None
    assert len(card["supporting"]["series"]) == 2
