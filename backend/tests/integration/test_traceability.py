"""Traceability: every number an evidence endpoint serves is recomputed from the snapshot files.

The expected values come only from `data/snapshot/*.ndjson`, read with the standard library, using
the rules written in product-spec.md (section 4.2) and openapi.yaml (the three evidence endpoints).
Nothing from `app.evidence`, `app.db` or the backend's SQL is imported here. The API side is the
real app over Postgres seeded with the real snapshot and the real `content/` findings.

CFE_TRACE_SNAPSHOT_DIR points the expected side at another snapshot directory; the mutation proof
in the workflow log uses it to show the test fails when one served number differs.

Float equality: openapi.yaml documents no rounding for any evidence number, so floats are compared
with math.isclose(rel_tol=1e-9). Integers, strings, booleans, dates and nulls are compared exactly.
"""

import json
import math
import os
import re
import statistics
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import create_app
from app.seed.__main__ import run
from tests.integration.conftest import BACKEND, REAL_SNAPSHOT, alembic_config

REPO = BACKEND.parent
CONTENT_DIR = REPO / "content"
EXPECTED_DIR = Path(os.environ.get("CFE_TRACE_SNAPSHOT_DIR") or REPO / "data" / "snapshot")

SOURCES = {"acled": "acled", "ooni": "ooni", "google": "google-transparency"}
OONI_NOTE = (
    "These OONI tests check whether specific apps and sites can be reached from testers' networks."
)


def read_ndjson(name: str) -> list[dict]:
    with open(EXPECTED_DIR / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def finding_anchors() -> dict[str, date]:
    """slug -> anchor week, read from the first two lines of each content/findings file."""
    anchors = {}
    for path in sorted((CONTENT_DIR / "findings").glob("*.yaml")):
        head = path.read_text(encoding="utf-8")
        slug = re.search(r"^slug:\s*(\S+)", head, re.M).group(1)
        week = re.search(r"^week_start_date:\s*(\d{4}-\d{2}-\d{2})", head, re.M).group(1)
        anchors[slug] = date.fromisoformat(week)
    return anchors


ANCHORS = finding_anchors()


class Checker:
    """Compares expected with served values; counts every comparison per finding and source."""

    def __init__(self):
        self.counts: dict[tuple[str, str], int] = {}
        self.mismatches: list[str] = []

    def eq(self, slug: str, source: str, field: str, expected, actual):
        self.counts[(slug, source)] = self.counts.get((slug, source), 0) + 1
        if isinstance(expected, bool) or isinstance(actual, bool):
            ok = expected is actual
        elif isinstance(expected, float) or isinstance(actual, float):
            ok = (
                expected is not None
                and actual is not None
                and math.isclose(expected, actual, rel_tol=1e-9)
            )
        else:
            ok = expected == actual
        if not ok:
            self.mismatches.append(
                f"finding={slug} source={source} field={field}: "
                f"snapshot says {expected!r}, API served {actual!r}"
            )


@pytest.fixture(scope="module")
def client(test_engine):
    from alembic import command

    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(test_engine), "head")
    run(REAL_SNAPSHOT, CONTENT_DIR, engine=test_engine)
    app = create_app(test_engine.url.render_as_string(hide_password=False))
    with TestClient(app) as c:
        yield c


def served(client, slug: str, source: str) -> dict:
    r = client.get(f"/api/findings/{slug}/evidence/{SOURCES[source]}")
    assert r.status_code == 200, (slug, source, r.text)
    return r.json()["evidence"]


def no_data(chk: Checker, slug: str, source: str, card: dict):
    chk.eq(slug, source, "has_data", False, card["has_data"])
    for field in ("metric_value", "comparison", "supporting", "period_start", "period_end"):
        chk.eq(slug, source, field, None, card[field])


# ---- ACLED: openapi.yaml getAcledEvidence, product-spec.md 4.2 ----------------------------------

ACLED_WEEK_FIELDS = (
    "week_start_date", "total_events", "total_fatalities", "signal_valid",
    "protest_pressure_z", "violence_pressure_z", "suppression_z",
    "protest_active_baseline_weeks", "violence_active_baseline_weeks",
    "suppression_active_baseline_weeks", "sparse_protest_baseline_flag",
    "sparse_violence_baseline_flag", "sparse_suppression_baseline_flag",
    "zero_variance_flag", "low_event_density_flag", "high_methodology_risk_flag",
)  # fmt: skip


def check_acled(chk: Checker, slug: str, anchor: date, card: dict) -> bool:
    rows = {
        date.fromisoformat(r["week_start_date"]): r
        for r in read_ndjson("acled_signal_context.ndjson")
    }
    a = anchor_row = rows.get(anchor)
    if anchor_row is None:
        no_data(chk, slug, "acled", card)
        return False
    prior = [r for d, r in rows.items() if anchor - timedelta(weeks=12) <= d < anchor]
    chk.eq(slug, "acled", "period_start", anchor.isoformat(), card["period_start"])
    chk.eq(
        slug, "acled", "period_end", (anchor + timedelta(days=6)).isoformat(), card["period_end"]
    )
    chk.eq(slug, "acled", "metric_value", a["total_events"], card["metric_value"])
    sup = card["supporting"]
    if prior:
        med_e = float(statistics.median(r["total_events"] for r in prior))
        med_f = float(statistics.median(r["total_fatalities"] for r in prior))
        chk.eq(slug, "acled", "comparison.value", med_e, (card["comparison"] or {}).get("value"))
        chk.eq(
            slug, "acled", "prior_12_week_median_events", med_e, sup["prior_12_week_median_events"]
        )
        chk.eq(
            slug,
            "acled",
            "prior_12_week_median_fatalities",
            med_f,
            sup["prior_12_week_median_fatalities"],
        )
    else:
        chk.eq(slug, "acled", "comparison", None, card["comparison"])
        chk.eq(
            slug, "acled", "prior_12_week_median_events", None, sup["prior_12_week_median_events"]
        )
        chk.eq(
            slug,
            "acled",
            "prior_12_week_median_fatalities",
            None,
            sup["prior_12_week_median_fatalities"],
        )
    for field in ACLED_WEEK_FIELDS:
        chk.eq(slug, "acled", f"week.{field}", a[field], sup["week"][field])
    window = sorted(
        d for d in rows if anchor - timedelta(weeks=12) <= d <= anchor + timedelta(weeks=4)
    )
    chk.eq(slug, "acled", "series.length", len(window), len(sup["series"]))
    for d, got in zip(window, sup["series"], strict=False):
        for field in ACLED_WEEK_FIELDS:
            chk.eq(slug, "acled", f"series[{d}].{field}", rows[d][field], got[field])
    return True


# ---- OONI: openapi.yaml getOoniEvidence, product-spec.md 4.2 ------------------------------------

OONI_FIELDS = (
    "week_start_date", "test_name", "anomalous_total_scored", "anomalous_count",
    "anomalous_rate", "anomalous_baseline_rate_12w", "anomalous_zscore_12w",
    "anomalous_low_sample_flag", "anomalous_sparse_baseline_flag",
    "blocked_total_observations", "blocked_count", "blocked_rate",
    "blocked_baseline_rate_12w", "blocked_zscore_12w", "blocked_low_sample_flag",
    "blocked_sparse_baseline_flag", "feature_version",
)  # fmt: skip


def check_ooni(chk: Checker, slug: str, anchor: date, card: dict) -> bool:
    tests = sorted(
        (
            r
            for r in read_ndjson("ooni_weekly_signals.ndjson")
            if r["week_start_date"] == anchor.isoformat()
        ),
        key=lambda r: r["test_name"],
    )
    if not tests:
        no_data(chk, slug, "ooni", card)
        return False
    chk.eq(slug, "ooni", "period_start", anchor.isoformat(), card["period_start"])
    chk.eq(slug, "ooni", "period_end", (anchor + timedelta(days=6)).isoformat(), card["period_end"])
    scored = [r for r in tests if r["anomalous_zscore_12w"] is not None]
    # highest anomalous z-score; ties go to the alphabetically first test name (spec 4.2)
    top = (
        min(scored, key=lambda r: (-r["anomalous_zscore_12w"], r["test_name"])) if scored else None
    )
    sup = card["supporting"]
    chk.eq(slug, "ooni", "supporting.top_test", top["test_name"] if top else None, sup["top_test"])
    chk.eq(slug, "ooni", "supporting.note", OONI_NOTE, sup["note"])
    if top:
        chk.eq(slug, "ooni", "metric_value", top["anomalous_rate"], card["metric_value"])
        chk.eq(
            slug,
            "ooni",
            "comparison.value",
            top["anomalous_zscore_12w"],
            card["comparison"]["value"],
        )
        chk.eq(
            slug, "ooni", "comparison.label",
            f"{top['test_name']}: standard deviations from its own 12-week baseline",
            card["comparison"]["label"],
        )  # fmt: skip
    else:
        chk.eq(slug, "ooni", "metric_value", None, card["metric_value"])
        chk.eq(slug, "ooni", "comparison", None, card["comparison"])
    chk.eq(slug, "ooni", "tests.length", len(tests), len(sup["tests"]))
    for want, got in zip(tests, sup["tests"], strict=False):
        for field in OONI_FIELDS:
            chk.eq(slug, "ooni", f"tests[{want['test_name']}].{field}", want[field], got[field])
    return True


# ---- Google Transparency: openapi.yaml getGoogleTransparencyEvidence, product-spec.md 4.2 -------

GOOGLE_COUNTS = (
    "number_of_requests",
    "items_requested_removal",
    "items_removed_legal",
    "items_removed_policy",
)


def check_google(chk: Checker, slug: str, anchor: date, card: dict) -> bool:
    if anchor.month <= 6:
        start, end, period_date = (
            date(anchor.year, 1, 1),
            date(anchor.year, 6, 30),
            date(anchor.year, 6, 1),
        )
    else:
        start, end, period_date = (
            date(anchor.year, 7, 1),
            date(anchor.year, 12, 31),
            date(anchor.year, 12, 1),
        )
    rows = sorted(
        (
            r
            for r in read_ndjson("google_transparency_requests.ndjson")
            if r["period_date"] == period_date.isoformat()
        ),
        key=lambda r: (r["requestor"], r["product"], r["reason"]),
    )
    if not rows:
        no_data(chk, slug, "google", card)
        return False
    chk.eq(slug, "google", "period_start", start.isoformat(), card["period_start"])
    chk.eq(slug, "google", "period_end", end.isoformat(), card["period_end"])
    chk.eq(slug, "google", "comparison", None, card["comparison"])
    totals = {f: sum(r[f] for r in rows) for f in GOOGLE_COUNTS}
    chk.eq(slug, "google", "metric_value", totals["number_of_requests"], card["metric_value"])
    sup = card["supporting"]
    chk.eq(slug, "google", "supporting.time_period", rows[0]["time_period"], sup["time_period"])
    for f in GOOGLE_COUNTS:
        chk.eq(slug, "google", f"totals.{f}", totals[f], sup["totals"][f])
    chk.eq(slug, "google", "rows.length", len(rows), len(sup["rows"]))
    for i, (want, got) in enumerate(zip(rows, sup["rows"], strict=False)):
        for field in ("requestor", "product", "reason", *GOOGLE_COUNTS):
            chk.eq(slug, "google", f"rows[{i}].{field}", want[field], got[field])
    return True


CHECKS = {"acled": check_acled, "ooni": check_ooni, "google": check_google}


def test_every_evidence_number_equals_the_snapshot(client):
    assert len(ANCHORS) == 5, f"expected five findings in content/findings, found {sorted(ANCHORS)}"
    chk = Checker()
    with_data: list[tuple[str, str]] = []
    for slug, anchor in sorted(ANCHORS.items()):
        for source, fn in CHECKS.items():
            if fn(chk, slug, anchor, served(client, slug, source)):
                with_data.append((slug, source))
    assert not chk.mismatches, "served numbers differ from the snapshot:\n" + "\n".join(
        chk.mismatches
    )
    for key in with_data:
        assert chk.counts[key] > 0, f"no numbers were checked for {key}"
    assert with_data, "no card had data; the test checked nothing"
    print("\nnumbers checked per (finding, source):")
    for (slug, source), n in sorted(chk.counts.items()):
        print(f"  {slug:32s} {source:7s} {n}")
    print(f"  total {sum(chk.counts.values())}")
