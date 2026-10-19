"""Telemetry: spans, metrics and JSON logs, and the privacy rules of product spec 7.2 (no database).

A small app with the same route templates as the real one runs through telemetry.setup() with
in-memory exporters. Database spans need a real Postgres and are checked in tests/integration/test_telemetry_db.py.
"""

import io
import json
import logging
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import telemetry
from app.main import create_app

FAKE_DB_URL = "postgresql+psycopg://leak-user:leak-secret-pw@db.invalid:5432/leakdb"
CLIENT_IP = "203.0.113.77"
USER_AGENT = "SecretBrowser/9.9 (reader-identifying)"
QUERY_VALUE = "needle-query-value"
COOKIE_VALUE = "needle-cookie-value"
HEADERS = {
    "X-Forwarded-For": CLIENT_IP,
    "User-Agent": USER_AGENT,
    "Cookie": f"session={COOKIE_VALUE}",
}


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", FAKE_DB_URL)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    spans, metrics, stream = InMemorySpanExporter(), InMemoryMetricReader(), io.StringIO()
    logging.getLogger("httpx").setLevel(logging.WARNING)  # the test client's own request lines
    app = FastAPI()

    @app.get("/api/findings/{slug}")
    def finding(slug: str):
        logging.getLogger("cfe.test").info("loading finding")
        logging.getLogger("cfe.test").warning("db is %s", os.environ["DATABASE_URL"])
        return {"slug": slug}

    @app.get("/api/boom/{slug}")
    def boom(slug: str):
        raise RuntimeError(f"cannot connect to {os.environ['DATABASE_URL']}")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    telemetry.setup(
        app,
        span_exporters=[spans],
        metric_readers=[metrics],
        simple_processors=True,
        log_stream=stream,
    )
    yield app, spans, metrics, stream
    logging.getLogger().handlers = [
        h for h in logging.getLogger().handlers if h.get_name() != telemetry._STDOUT_HANDLER
    ]
    if telemetry.PsycopgInstrumentor().is_instrumented_by_opentelemetry:
        telemetry.PsycopgInstrumentor().uninstrument()


def _log_lines(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _metric_attribute_sets(reader):
    data = reader.get_metrics_data()
    out = []
    for rm in data.resource_metrics if data else []:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                out.extend((metric.name, dict(p.attributes)) for p in metric.data.data_points)
    return out


def _everything_text(spans, metrics, stream) -> str:
    parts = [stream.getvalue()]
    for span in spans.get_finished_spans():
        parts.append(span.to_json())
    parts.append(json.dumps(_metric_attribute_sets(metrics), default=str))
    return "\n".join(parts)


def test_server_span_route_attribute_is_the_template(harness):
    app, spans, metrics, _ = harness
    TestClient(app).get("/api/findings/some-slug-123")
    server = [s for s in spans.get_finished_spans() if s.kind.name == "SERVER"]
    assert len(server) == 1
    assert server[0].attributes["http.route"] == "/api/findings/{slug}"
    assert "some-slug-123" not in server[0].to_json()
    assert telemetry.PsycopgInstrumentor().is_instrumented_by_opentelemetry
    routes = {
        a.get("http.route")
        for name, a in _metric_attribute_sets(metrics)
        if name == "http.server.request.duration"
    }
    assert routes == {"/api/findings/{slug}"}


def test_error_requests_are_counted_with_status_and_template(harness):
    app, _, metrics, _ = harness
    TestClient(app, raise_server_exceptions=False).get("/api/boom/x")
    points = [
        a for name, a in _metric_attribute_sets(metrics) if name == "http.server.request.duration"
    ]
    assert points == [
        {
            "http.request.method": "GET",
            "http.route": "/api/boom/{slug}",
            "http.response.status_code": 500,
        }
    ]


def test_nothing_identifying_reaches_spans_metrics_or_logs(harness):
    app, spans, metrics, stream = harness
    client = TestClient(app, raise_server_exceptions=False)
    client.get(f"/api/findings/a?q={QUERY_VALUE}&utm=1", headers=HEADERS)
    client.get(f"/api/boom/b?q={QUERY_VALUE}", headers=HEADERS)
    client.get("/api/not-a-route?q=" + QUERY_VALUE, headers=HEADERS)

    everything = _everything_text(spans, metrics, stream)
    for value in (CLIENT_IP, USER_AGENT, QUERY_VALUE, COOKIE_VALUE, "leak-secret-pw", "leak-user"):
        assert value not in everything, value
    assert "db.invalid" not in everything
    assert FAKE_DB_URL not in everything
    assert telemetry.REDACTED in stream.getvalue()  # the URL was logged, then redacted

    for span in spans.get_finished_spans():
        for key in span.attributes:
            assert not telemetry._forbidden(key), key
        for event in span.events:
            for key in event.attributes:
                assert not telemetry._forbidden(key), key
    for _, attributes in _metric_attribute_sets(metrics):
        assert set(attributes) <= telemetry.METRIC_ATTRIBUTE_KEYS
    for line in _log_lines(stream):
        assert set(line) <= {
            "timestamp", "severity", "message", "logger", "trace_id", "span_id",
            "method", "route", "status", "duration_ms",
        }  # fmt: skip


def test_unmatched_path_has_no_route_attribute_and_no_concrete_path(harness):
    app, spans, metrics, stream = harness
    TestClient(app).get("/api/secret-looking-path")
    assert "secret-looking-path" not in _everything_text(spans, metrics, stream)
    access = [line for line in _log_lines(stream) if line["logger"] == "cfe.access"]
    assert access[0]["route"] == "unmatched" and access[0]["status"] == 404


def test_every_log_line_is_json_with_matching_trace_and_span_ids(harness):
    app, spans, _, stream = harness
    TestClient(app).get("/api/findings/x")
    lines = _log_lines(stream)
    assert {line["logger"] for line in lines} >= {"cfe.test", "cfe.access"}
    server = next(s for s in spans.get_finished_spans() if s.kind.name == "SERVER")
    for line in lines:
        assert {"timestamp", "severity", "message", "logger", "trace_id", "span_id"} <= set(line)
        assert line["trace_id"] == format(server.context.trace_id, "032x")
        assert line["span_id"] and len(line["span_id"]) == 16
    # The handler's own line runs in the server span; the access line is written inside it too.
    assert all(
        line["span_id"] == format(server.context.span_id, "016x") for line in lines
    )
    access = next(line for line in lines if line["logger"] == "cfe.access")
    assert (access["method"], access["route"], access["status"]) == (
        "GET",
        "/api/findings/{slug}",
        200,
    )
    assert isinstance(access["duration_ms"], float)


def test_healthcheck_is_not_traced_or_logged(harness):
    app, spans, metrics, stream = harness
    TestClient(app).get("/api/health")
    assert spans.get_finished_spans() == ()
    assert _metric_attribute_sets(metrics) == []
    assert stream.getvalue() == ""


def test_cloud_logging_trace_fields(harness, monkeypatch):
    app, spans, _, stream = harness
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
    TestClient(app).get("/api/findings/x")
    server = next(s for s in spans.get_finished_spans() if s.kind.name == "SERVER")
    trace_id = format(server.context.trace_id, "032x")
    for line in _log_lines(stream):
        assert line["logging.googleapis.com/trace"] == f"projects/my-project/traces/{trace_id}"
        assert line["logging.googleapis.com/spanId"] == line["span_id"]


def test_cloud_logging_fields_absent_without_project(harness):
    app, _, _, stream = harness
    TestClient(app).get("/api/findings/x")
    assert all("logging.googleapis.com/trace" not in line for line in _log_lines(stream))


def test_incoming_traceparent_is_continued(harness):
    app, spans, _, _ = harness
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    TestClient(app).get(
        "/api/findings/x", headers={"traceparent": f"00-{trace_id}-b7ad6b7169203331-01"}
    )
    server = next(s for s in spans.get_finished_spans() if s.kind.name == "SERVER")
    assert format(server.context.trace_id, "032x") == trace_id


@pytest.mark.parametrize("endpoint", [None, "", "  "], ids=["unset", "empty", "blank"])
def test_no_exporter_without_otlp_endpoint(monkeypatch, endpoint):
    if endpoint is None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    else:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
    captured = {}
    real_setup = telemetry.setup

    def spy(app, **kwargs):
        captured.update(kwargs)
        real_setup(app, **kwargs)

    monkeypatch.setattr(telemetry, "setup", spy)
    app = create_app(database_url="postgresql+psycopg://u:p@nowhere.invalid/db")
    assert captured == {"span_exporters": [], "metric_readers": [], "log_exporters": []}
    assert app.state.telemetry["tracer_provider"]._active_span_processor._span_processors == ()
    assert app.state.telemetry["logger_provider"] is None
    assert not any(h.get_name() == telemetry._OTLP_HANDLER for h in logging.getLogger().handlers)


def test_otlp_exporters_are_created_when_endpoint_is_set(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    app = create_app(database_url="postgresql+psycopg://u:p@nowhere.invalid/db")
    processors = app.state.telemetry["tracer_provider"]._active_span_processor._span_processors
    assert len(processors) == 1
    assert isinstance(processors[0].span_exporter, telemetry.ScrubbingSpanExporter)
    assert app.state.telemetry["logger_provider"] is not None
    app.state.telemetry["tracer_provider"].shutdown()
    app.state.telemetry["meter_provider"].shutdown()
    app.state.telemetry["logger_provider"].shutdown()
