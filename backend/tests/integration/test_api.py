"""API tests against Postgres with the real snapshot plus test-only content.

Every response body is validated against openapi.yaml with openapi-core.
"""

import json

import pytest
from fastapi.testclient import TestClient
from openapi_core import OpenAPI
from openapi_core.testing import MockRequest, MockResponse
from sqlalchemy import text

from app.main import create_app
from app.seed.__main__ import run
from tests.integration.conftest import BACKEND, REAL_SNAPSHOT, alembic_config

CONTENT = BACKEND / "tests" / "fixtures" / "content_evidence"
SPEC = OpenAPI.from_file_path(str(BACKEND.parent / "openapi.yaml"))
VERSION = "2026-10-10.1"

SLUG = {w: f"test-week-{w}" for w in
        ("2024-06-22", "2008-01-19", "2025-06-21", "2022-08-06", "2023-07-15")}  # fmt: skip


@pytest.fixture(scope="module")
def engine(test_engine):
    from alembic import command

    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(test_engine), "head")
    run(REAL_SNAPSHOT, CONTENT, engine=test_engine)
    return test_engine


@pytest.fixture(scope="module")
def client(engine):
    app = create_app(engine.url.render_as_string(hide_password=False))
    with TestClient(app) as c:
        yield c


def get(client, path: str, **params):
    """GET and validate the response body against the contract."""
    response = client.get(path, params=params)
    request = MockRequest("http://localhost:8000", "get", path.split("?")[0], args=params or None)
    # openapi-core matches the templated path from the concrete one
    SPEC.validate_response(
        request,
        MockResponse(
            response.content,
            status_code=response.status_code,
            content_type=response.headers["content-type"].split(";")[0],
        ),
    )
    return response


def card(client, week: str, source: str) -> dict:
    r = get(client, f"/api/findings/{SLUG[week]}/evidence/{source}")
    assert r.status_code == 200
    assert r.json()["snapshot_version"] == VERSION
    return r.json()["evidence"]


# ---- health, timeline, lists -------------------------------------------------------------------


def test_health_ok(client):
    r = get(client, "/api/health")
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "ok" and body["database"] == "reachable"
    assert body["snapshot_version"] == VERSION
    assert body["migration_head"] == "0004"
    assert body["row_counts"]["regime_weeks"] == 1523
    assert body["row_counts"]["acled_signal_context"] == 85
    assert body["row_counts"]["ooni_weekly_signals"] == 550
    assert body["row_counts"]["google_transparency_requests"] == 85
    assert body["row_counts"]["findings"] == 5


def test_health_503_when_database_unreachable():
    app = create_app("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none")
    with TestClient(app) as bad:
        r = get(bad, "/api/health")
    assert r.status_code == 503
    assert r.json() == {
        "status": "degraded",
        "database": "unreachable",
        "snapshot_version": None,
        "migration_head": None,
        "row_counts": {},
    }


def test_health_503_when_no_snapshot(engine):
    other = create_app(engine.url.render_as_string(hide_password=False))
    with engine.begin() as conn:
        saved = conn.execute(text("SELECT * FROM snapshot_meta")).mappings().one()
        conn.execute(text("DELETE FROM snapshot_meta"))
    try:
        with TestClient(other) as c:
            r = get(c, "/api/health")
        assert r.status_code == 503
        assert r.json()["status"] == "degraded"
        assert r.json()["database"] == "reachable"
        assert r.json()["snapshot_version"] is None
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO snapshot_meta (version, exported_at, acled_access_date, "
                    "loaded_at, manifest) VALUES (:version, :exported_at, :acled_access_date, "
                    ":loaded_at, CAST(:manifest AS jsonb))"
                ),
                {**saved, "manifest": json.dumps(saved["manifest"])},
            )


@pytest.mark.parametrize(
    "path",
    [
        "/api/timeline",
        "/api/findings",
        f"/api/findings/{SLUG['2024-06-22']}",
        f"/api/findings/{SLUG['2024-06-22']}/evidence/acled",
        f"/api/findings/{SLUG['2024-06-22']}/evidence/ooni",
        f"/api/findings/{SLUG['2024-06-22']}/evidence/google-transparency",
        "/api/methodology",
    ],
)
def test_data_endpoints_503_when_no_snapshot(engine, path):
    app = create_app(engine.url.render_as_string(hide_password=False))
    with engine.begin() as conn:
        saved = conn.execute(text("SELECT * FROM snapshot_meta")).mappings().one()
        conn.execute(text("DELETE FROM snapshot_meta"))
    try:
        with TestClient(app) as c:
            r = get(c, path)
        assert r.status_code == 503
        assert r.json() == {"detail": "No snapshot is loaded."}
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO snapshot_meta (version, exported_at, acled_access_date, "
                    "loaded_at, manifest) VALUES (:version, :exported_at, :acled_access_date, "
                    ":loaded_at, CAST(:manifest AS jsonb))"
                ),
                {**saved, "manifest": json.dumps(saved["manifest"])},
            )


def test_timeline_default_ke(client):
    r = get(client, "/api/timeline")
    body = r.json()
    assert r.status_code == 200
    assert body["country"] == "KE" and body["snapshot_version"] == VERSION
    assert len(body["weeks"]) == 1523
    dates = [w["week_start_date"] for w in body["weeks"]]
    assert dates == sorted(dates)
    by_date = {w["week_start_date"]: w for w in body["weeks"]}
    assert by_date["2024-06-22"]["finding_slug"] == SLUG["2024-06-22"]
    assert sum(1 for w in body["weeks"] if w["finding_slug"]) == 5


def test_timeline_state_filter(client):
    r = get(client, "/api/timeline", state="CRISIS")
    weeks = r.json()["weeks"]
    assert len(weeks) == 27
    assert {w["regime_state"] for w in weeks} == {"CRISIS"}


def test_timeline_from_after_to_is_empty(client):
    r = get(client, "/api/timeline", **{"from": "2024-01-01", "to": "2023-01-01"})
    assert r.status_code == 200 and r.json()["weeks"] == []


def test_timeline_from_to_inclusive(client):
    r = get(client, "/api/timeline", **{"from": "2024-06-22", "to": "2024-06-22"})
    assert [w["week_start_date"] for w in r.json()["weeks"]] == ["2024-06-22"]


def test_timeline_unknown_country_is_empty(client):
    r = get(client, "/api/timeline", country="ZZ")
    assert r.status_code == 200
    assert r.json()["country"] == "ZZ" and r.json()["weeks"] == []


@pytest.mark.parametrize(
    "params", [{"country": "ke"}, {"state": "NOPE"}, {"from": "not-a-date"}, {"to": "2024-13-01"}]
)
def test_timeline_malformed_parameter_is_422(client, params):
    assert get(client, "/api/timeline", **params).status_code == 422


def test_findings_list_ordered_by_position(client):
    r = get(client, "/api/findings")
    findings = r.json()["findings"]
    assert r.status_code == 200
    assert [f["slug"] for f in findings] == [
        SLUG[w] for w in ("2024-06-22", "2025-06-21", "2023-07-15", "2022-08-06", "2008-01-19")
    ]
    assert findings[0]["week_start_date"] == "2024-06-22"


# ---- finding detail ----------------------------------------------------------------------------


@pytest.mark.parametrize("week", list(SLUG))
def test_finding_detail(client, week):
    r = get(client, f"/api/findings/{SLUG[week]}")
    assert r.status_code == 200
    finding = r.json()["finding"]
    assert finding["caveats"]
    assert "classification_reason" not in finding
    assert "classification_reason" not in finding["classification"]
    assert finding["week_start_date"] == week
    assert [s["source"] for s in finding["sources"]] == ["acled", "ooni", "google_transparency"]
    assert all("url" not in s for s in finding["sources"])
    assert isinstance(finding["citations"], list)


def test_finding_detail_has_teaser_position_and_key_phrase(client):
    first = get(client, f"/api/findings/{SLUG['2024-06-22']}").json()["finding"]
    assert first["teaser"] == "Test-only text; not curated content."
    assert first["position"] == 1
    assert first["key_phrase"] == "Test-only text"
    other = get(client, f"/api/findings/{SLUG['2008-01-19']}").json()["finding"]
    assert other["position"] == 5 and other["key_phrase"] is None


def test_ooni_card_returns_the_new_note(client):
    note = card(client, "2024-06-22", "ooni")["supporting"]["note"]
    assert note == (
        "These OONI tests check whether specific apps and sites can be reached from "
        "testers' networks."
    )


EXPECTED_CITATIONS = {
    "2024-06-22": [
        ("Test-only claim one.", "https://example.org/test-only/one"),
        ("Test-only claim two.", "https://example.org/test-only/two"),
    ],
    "2023-07-15": [("Test-only claim for this week.", "https://example.org/test-only/three")],
    "2025-06-21": [],
    "2022-08-06": [],
    "2008-01-19": [],
}


@pytest.mark.parametrize("week", list(SLUG))
def test_finding_detail_citations_in_stored_order(client, week):
    finding = get(client, f"/api/findings/{SLUG[week]}").json()["finding"]
    assert [(c["claim"], c["url"]) for c in finding["citations"]] == EXPECTED_CITATIONS[week]
    assert all(set(c) == {"claim", "citation", "url"} for c in finding["citations"])
    assert all("test-only" in c["citation"] for c in finding["citations"])


def test_snapshot_reader_can_select_findings_citations(engine):
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ WRITE"))
        conn.execute(text("SET LOCAL ROLE snapshot_reader"))
        rows = conn.execute(
            text("SELECT slug, citations FROM findings ORDER BY position")
        ).all()
        conn.rollback()
    assert len(rows) == 5
    assert len(rows[0].citations) == 2


def test_finding_detail_evidence_available(client):
    def available(week):
        return get(client, f"/api/findings/{SLUG[week]}").json()["finding"]["evidence_available"]

    assert available("2024-06-22") == ["acled", "ooni", "google_transparency"]
    assert available("2008-01-19") == ["acled"]
    assert available("2022-08-06") == ["acled", "google_transparency"]


def test_finding_detail_matches_regime_week(client, engine):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT primary_regime, confidence_level, previous_regime, protest_band, "
                "classification_reason FROM regime_weeks WHERE week_start_date = '2024-06-22'"
            )
        ).one()
    finding = get(client, f"/api/findings/{SLUG['2024-06-22']}").json()["finding"]
    assert finding["regime_state"] == row.primary_regime
    assert finding["confidence_level"] == row.confidence_level
    assert finding["classification"]["previous_regime"] == row.previous_regime
    assert finding["classification"]["protest_band"] == row.protest_band
    marker = "pre_transition:"
    expected = (
        row.classification_reason.split(marker)[1].split()[0].rstrip(";,)")
        if marker in row.classification_reason
        else None
    )
    assert finding["classification"]["pre_transition_target"] == expected


@pytest.mark.parametrize(
    "suffix", ["", "/evidence/acled", "/evidence/ooni", "/evidence/google-transparency"]
)
def test_unknown_slug_is_404(client, suffix):
    r = get(client, f"/api/findings/no-such-finding{suffix}")
    assert r.status_code == 404
    assert isinstance(r.json()["detail"], str)


@pytest.mark.parametrize(
    "suffix", ["", "/evidence/acled", "/evidence/ooni", "/evidence/google-transparency"]
)
def test_bad_slug_is_422(client, suffix):
    r = get(client, f"/api/findings/Bad_Slug{suffix}")
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)


def test_overlong_slug_is_422(client):
    assert get(client, "/api/findings/" + "a" * 81).status_code == 422


# ---- evidence cards: real values ---------------------------------------------------------------


def test_acled_2024_06_22(client):
    c = card(client, "2024-06-22", "acled")
    assert c["has_data"] is True and c["source"] == "acled" and c["period_grain"] == "week"
    assert c["metric_value"] == 167
    assert c["comparison"] == {"label": "Median of the 12 weeks before", "value": 55}
    assert (c["period_start"], c["period_end"]) == ("2024-06-22", "2024-06-28")
    assert c["snapshot_files"] == ["acled_signal_context.ndjson"]
    s = c["supporting"]
    assert len(s["series"]) == 17
    assert s["series"][0]["week_start_date"] == "2024-03-30"
    assert s["series"][-1]["week_start_date"] == "2024-07-20"
    assert s["prior_12_week_median_fatalities"] == 11.5
    assert s["prior_12_week_median_events"] == 55
    assert s["week"]["total_events"] == 167


def test_acled_2008_and_2025(client):
    c = card(client, "2008-01-19", "acled")
    assert c["metric_value"] == 66 and c["comparison"]["value"] == 16.5
    c = card(client, "2025-06-21", "acled")
    assert c["metric_value"] == 115 and c["comparison"]["value"] == 61.5


def test_ooni_2024_06_22(client):
    c = card(client, "2024-06-22", "ooni")
    assert c["has_data"] is True and c["source"] == "ooni"
    assert c["supporting"]["top_test"] == "signal"
    assert c["metric_value"] == pytest.approx(0.030060, abs=5e-7)
    assert c["comparison"]["value"] == pytest.approx(1.237074, abs=5e-7)
    assert c["comparison"]["label"] == "signal: standard deviations from its own 12-week baseline"
    tests = [t["test_name"] for t in c["supporting"]["tests"]]
    assert tests == sorted(tests)


def test_ooni_2025_and_2023(client):
    c = card(client, "2025-06-21", "ooni")
    assert c["supporting"]["top_test"] == "telegram"
    assert c["metric_value"] == pytest.approx(0.068441, abs=5e-7)
    assert c["comparison"]["value"] == pytest.approx(10.174744, abs=5e-7)
    c = card(client, "2023-07-15", "ooni")
    assert c["supporting"]["top_test"] == "whatsapp"
    assert c["comparison"]["value"] == pytest.approx(0.015936, abs=5e-7)


def test_ooni_no_data_weeks(client):
    for week in ("2008-01-19", "2022-08-06"):
        c = card(client, week, "ooni")
        assert c["has_data"] is False
        assert c["metric_value"] is None and c["comparison"] is None
        assert c["supporting"] is None
        assert c["period_start"] is None and c["period_end"] is None


def test_google_values(client):
    c = card(client, "2024-06-22", "google-transparency")
    assert c["source"] == "google_transparency" and c["period_grain"] == "half_year"
    assert c["metric_value"] == 9 and c["comparison"] is None
    assert c["supporting"]["time_period"] == "January - June 2024"
    assert (c["period_start"], c["period_end"]) == ("2024-01-01", "2024-06-30")
    assert c["snapshot_files"] == ["google_transparency_requests.ndjson"]
    assert c["supporting"]["totals"]["number_of_requests"] == 9
    c = card(client, "2025-06-21", "google-transparency")
    assert c["metric_value"] == 16 and c["supporting"]["time_period"] == "January - June 2025"
    c = card(client, "2022-08-06", "google-transparency")
    assert c["metric_value"] == 5 and c["supporting"]["time_period"] == "July - December 2022"
    c = card(client, "2023-07-15", "google-transparency")
    assert c["metric_value"] == 5 and c["supporting"]["time_period"] == "July - December 2023"


def test_google_2008_has_no_data(client):
    c = card(client, "2008-01-19", "google-transparency")
    assert c["has_data"] is False and c["metric_value"] is None
    assert "begins with July to December 2012" in c["provenance_note"]


def test_provenance_notes_name_source_table_and_version(client):
    for week, source, table in (
        ("2024-06-22", "acled", "acled_signal_context"),
        ("2024-06-22", "ooni", "ooni_weekly_signals"),
        ("2024-06-22", "google-transparency", "google_transparency_requests"),
    ):
        note = card(client, week, source)["provenance_note"]
        assert table in note and VERSION in note


# ---- methodology -------------------------------------------------------------------------------


def test_methodology_without_curated_file(client, monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path))
    r = get(client, "/api/methodology")
    body = r.json()
    assert r.status_code == 200
    assert body["families"] == []
    assert body["regime_states"] == [] and body["confidence_levels"] == []
    assert body["family_bands"] == []
    assert [s["source"] for s in body["sources"]] == ["acled", "ooni", "google_transparency"]
    assert body["manifest"]["version"] == VERSION
    assert len(body["manifest"]["tables"]) == 4
    assert {t["row_count"] for t in body["manifest"]["tables"]} == {1523, 85, 550}


def test_methodology_reads_curated_file(client, monkeypatch, tmp_path):
    (tmp_path / "methodology.yaml").write_text(
        "families:\n  - {family: protest, definition: test-only}\n"
        "regime_states:\n  - {state: STABLE, definition: test-only}\n"
        "confidence_levels:\n  - {level: HIGH, definition: test-only}\n"
        "family_bands:\n  - {band: NORMAL, definition: test-only}\n"
    )
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path))
    body = get(client, "/api/methodology").json()
    assert body["families"] == [{"family": "protest", "definition": "test-only"}]
    assert body["regime_states"] == [{"state": "STABLE", "definition": "test-only"}]
    assert body["family_bands"] == [{"band": "NORMAL", "definition": "test-only"}]


def test_methodology_real_content_is_complete(client, monkeypatch):
    import typing

    from app import schemas

    monkeypatch.setenv("CONTENT_DIR", str(BACKEND.parent / "content"))
    r = get(client, "/api/methodology")
    body = r.json()
    assert r.status_code == 200
    assert [len(body[k]) for k in ("families", "regime_states", "confidence_levels", "family_bands")] == [3, 7, 4, 4]
    for key, field, enum in (
        ("families", "family", schemas.PressureFamily),
        ("regime_states", "state", schemas.RegimeState),
        ("confidence_levels", "level", schemas.ConfidenceLevel),
        ("family_bands", "band", schemas.FamilyBand),
    ):
        names = [item[field] for item in body[key]]
        assert sorted(names) == sorted(typing.get_args(enum)), key  # exactly one each
        assert all(item["definition"].strip() for item in body[key])


def test_requests_run_in_read_only_transactions(client, engine):
    # The session dependency issues SET TRANSACTION READ ONLY; prove a write would be refused.
    from sqlalchemy.orm import Session

    with Session(engine) as s:
        s.execute(text("SET TRANSACTION READ ONLY"))
        with pytest.raises(Exception, match="read-only"):
            s.execute(text("DELETE FROM findings"))
