"""Database spans for a real request, and that the connection details stay out of them."""

import io

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text

from app import telemetry
from app.main import create_app
from app.seed.__main__ import run
from tests.integration.conftest import BACKEND, REAL_SNAPSHOT, alembic_config

CONTENT = BACKEND / "tests" / "fixtures" / "content_evidence"
ROUTES = (
    "/api/findings/test-week-2024-06-22",
    "/api/findings/test-week-2024-06-22/evidence/acled",
    "/api/findings?limit=5",
)


@pytest.fixture
def traced_client(test_engine, monkeypatch):
    from alembic import command

    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(test_engine), "head")
    run(REAL_SNAPSHOT, CONTENT, engine=test_engine)
    url = test_engine.url.render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", url)
    app = create_app(url)
    spans, stream = InMemorySpanExporter(), io.StringIO()
    telemetry.setup(app, span_exporters=[spans], simple_processors=True, log_stream=stream)
    yield TestClient(app), spans, stream, test_engine
    telemetry.PsycopgInstrumentor().uninstrument()


def test_a_request_has_one_trace_with_database_spans(traced_client):
    client, spans, _, _ = traced_client
    assert client.get(ROUTES[0]).status_code == 200
    finished = spans.get_finished_spans()
    server = [s for s in finished if s.kind.name == "SERVER"]
    assert len(server) == 1
    assert server[0].attributes["http.route"] == "/api/findings/{slug}"
    db = [s for s in finished if s.attributes.get("db.system") == "postgresql"]
    assert db, [s.name for s in finished]
    assert {s.context.trace_id for s in finished} == {server[0].context.trace_id}


def test_database_spans_carry_no_credentials_or_address(traced_client):
    client, spans, stream, engine = traced_client
    for route in ROUTES:
        assert client.get(route).status_code == 200
    password = engine.url.password
    blob = "\n".join(s.to_json() for s in spans.get_finished_spans()) + stream.getvalue()
    assert password not in blob
    assert engine.url.host not in blob
    for span in spans.get_finished_spans():
        for key in span.attributes:
            assert not telemetry._forbidden(key), key
