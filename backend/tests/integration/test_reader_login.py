"""The API works when its database login can only read.

The deployed backend connects as `cfe_api_reader`: a LOGIN role that is a member of the NOLOGIN
`snapshot_reader` role (migration 0002), so it holds SELECT on the public tables and nothing else.
These tests create such a login locally and check that every API route answers exactly as it does
for the owner, and that the login cannot write.

The password is a local-only test constant, like the other local values in this repository.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from app.main import create_app
from app.seed.__main__ import run
from tests.integration.conftest import BACKEND, REAL_SNAPSHOT, alembic_config

CONTENT = BACKEND / "tests" / "fixtures" / "content_evidence"
READER = "cfe_test_api_reader"
READER_PASSWORD = "reader-test-local-only"  # noqa: S105 (local test constant, not a credential)
TABLES = (
    "regime_weeks",
    "acled_signal_context",
    "ooni_weekly_signals",
    "google_transparency_requests",
    "findings",
    "finding_caveats",
    "snapshot_meta",
    "snapshot_tables",
)


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
def reader_engine(engine):
    """An engine that logs in as the read-only login; the role is dropped afterwards."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP ROLE IF EXISTS {READER}"))
        conn.execute(text(f"CREATE ROLE {READER} LOGIN PASSWORD '{READER_PASSWORD}'"))
        conn.execute(text(f"GRANT snapshot_reader TO {READER}"))
    url = engine.url.set(username=READER, password=READER_PASSWORD)
    reader = create_engine(url)
    yield reader
    reader.dispose()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"DROP ROLE IF EXISTS {READER}"))


@pytest.fixture(scope="module")
def owner_client(engine):
    app = create_app(engine.url.render_as_string(hide_password=False))
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def reader_client(reader_engine):
    app = create_app(reader_engine.url.render_as_string(hide_password=False))
    with TestClient(app) as c:
        yield c


def _slugs(client) -> list[str]:
    return [f["slug"] for f in client.get("/api/findings").json()["findings"]]


def _paths(client) -> list[tuple[str, dict]]:
    paths: list[tuple[str, dict]] = [
        ("/api/health", {}),
        ("/api/findings", {}),
        ("/api/timeline", {}),
        ("/api/timeline", {"state": "CRISIS"}),
        ("/api/timeline", {"from": "2024-06-22", "to": "2024-06-22"}),
        ("/api/timeline", {"country": "ZZ"}),
        ("/api/methodology", {}),
    ]
    for slug in _slugs(client):
        paths.append((f"/api/findings/{slug}", {}))
        for source in ("acled", "ooni", "google-transparency"):
            paths.append((f"/api/findings/{slug}/evidence/{source}", {}))
    return paths


def test_reader_can_log_in_and_is_not_privileged(reader_engine):
    with reader_engine.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar_one() == READER
        flags = conn.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
    assert tuple(flags) == (False, False, False, False)


def test_every_route_answers_the_same_for_the_reader(owner_client, reader_client):
    paths = _paths(owner_client)
    assert len(_slugs(owner_client)) == 5
    assert len(paths) == 7 + 5 * 4
    for path, params in paths:
        expected = owner_client.get(path, params=params)
        actual = reader_client.get(path, params=params)
        assert actual.status_code == expected.status_code == 200, (path, params)
        assert actual.json() == expected.json(), (path, params)


def test_reader_health_reports_ok(reader_client):
    body = reader_client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] == "reachable"


def _counts(engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()  # noqa: S608 (constants)
            for t in TABLES
        }


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO findings (slug) VALUES ('reader-test')",
        "UPDATE findings SET title = 'changed'",
        "DELETE FROM findings",
        "DELETE FROM regime_weeks",
        "CREATE TABLE reader_test (id int)",
    ],
    ids=["insert", "update", "delete-findings", "delete-regime-weeks", "create-table"],
)
def test_reader_cannot_write(engine, reader_engine, statement):
    before = _counts(engine)
    with reader_engine.connect() as conn:
        with pytest.raises(ProgrammingError) as caught:
            conn.execute(text(statement))
        conn.rollback()
    assert "permission denied" in str(caught.value).lower()
    assert _counts(engine) == before
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('public.reader_test')")).scalar_one()
    assert exists is None
