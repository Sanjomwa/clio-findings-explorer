"""The finding-page alert as provisioned matches product spec 7.3 (no Docker, no Grafana).

The spec's numbers are repeated here on purpose: changing one in ops/grafana/provisioning/alerting/
without changing the spec and this test fails the build.
"""

import re
from pathlib import Path

import pytest
import yaml

ALERTING = Path(__file__).resolve().parents[3] / "ops" / "grafana" / "provisioning" / "alerting"

ERROR_SHARE = 0.05
P95_SECONDS = 2
MIN_REQUESTS = 10
WINDOW = "5m"


def load(name):
    return yaml.safe_load((ALERTING / name).read_text())


@pytest.fixture(scope="module")
def rule():
    groups = load("rules.yaml")["groups"]
    assert len(groups) == 1 and len(groups[0]["rules"]) == 1
    return groups[0]["rules"][0]


@pytest.fixture(scope="module")
def models(rule):
    return {d["refId"]: d["model"] for d in rule["data"]}


def test_math_expression_has_the_spec_thresholds(models):
    expr = models["IMPACT"]["expression"]
    assert f"$TOTAL >= {MIN_REQUESTS}" in expr
    assert f"$ERRORS / $TOTAL > {ERROR_SHARE}" in expr
    assert f"$P95 > {P95_SECONDS}" in expr
    assert "&&" in expr and "||" in expr


def test_every_query_uses_the_five_minute_window(models):
    for ref in ("A", "B", "C"):
        assert re.search(rf"\[{WINDOW}\]", models[ref]["expr"]), ref
        assert models[ref]["instant"] is True


def test_queries_use_the_metric_and_labels_telemetry_produces(models):
    for ref in ("A", "B", "C"):
        assert "http_server_request_duration_seconds" in models[ref]["expr"]
        assert "http_route=" in models[ref]["expr"]
    assert "_count" in models["A"]["expr"] and "_count" in models["B"]["expr"]
    assert "_bucket" in models["C"]["expr"] and "histogram_quantile(0.95" in models["C"]["expr"]
    assert 'http_response_status_code=~"5.."' in models["B"]["expr"]
    assert "http_response_status_code" not in models["A"]["expr"]


def test_route_matcher_covers_the_journey_and_nothing_else(models):
    matcher = re.search(r'http_route=~"([^"]+)"', models["A"]["expr"]).group(1)
    pattern = re.compile(f"^(?:{matcher})$")  # PromQL regex matchers are fully anchored
    for route in (
        "/api/findings",
        "/api/findings/{slug}",
        "/api/findings/{slug}/evidence/acled",
        "/api/findings/{slug}/evidence/ooni",
        "/api/findings/{slug}/evidence/google",
    ):
        assert pattern.match(route), route
    for route in ("/api/health", "/api/timeline", "/api/methodology", "/api/findingsx"):
        assert not pattern.match(route), route
    for ref in ("B", "C"):
        assert f'http_route=~"{matcher}"' in models[ref]["expr"]


def test_no_data_is_ok_and_errors_are_errors(rule):
    assert rule["noDataState"] == "OK"
    assert rule["execErrState"] == "Error"


def test_fires_quickly(rule):
    assert rule["condition"] == "FIRE"
    assert rule["for"] in ("0s", "30s", "1m")
    assert load("rules.yaml")["groups"][0]["interval"] == "30s"


def test_labels_and_annotations(rule):
    assert rule["labels"] == {"severity": "page", "journey": "finding-page"}
    assert rule["annotations"]["summary"]
    assert "docs/alerting.md" in rule["annotations"]["description"]


def test_contact_point_is_the_on_call_webhook():
    points = {p["name"]: p for p in load("contact-points.yaml")["contactPoints"]}
    receiver = points["on-call-agent"]["receivers"][0]
    assert receiver["type"] == "webhook"
    assert receiver["settings"]["url"] == "${ONCALL_WEBHOOK_URL}"


def test_policy_routes_page_alerts_to_the_webhook():
    policy = load("policies.yaml")["policies"][0]
    routes = [r for r in policy["routes"] if r["receiver"] == "on-call-agent"]
    assert len(routes) == 1
    assert ["severity", "=", "page"] in routes[0]["object_matchers"]
    assert routes[0]["group_wait"] == "10s"
    assert policy["receiver"] in {p["name"] for p in load("contact-points.yaml")["contactPoints"]}


def test_compose_passes_the_webhook_url_with_its_default():
    compose = yaml.safe_load((ALERTING.parents[3] / "docker-compose.yml").read_text())
    env = compose["services"]["lgtm"]["environment"]
    assert env["ONCALL_WEBHOOK_URL"] == "${ONCALL_WEBHOOK_URL:-http://oncall:8090/alert}"
