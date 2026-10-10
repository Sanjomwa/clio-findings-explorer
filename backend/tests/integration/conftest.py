"""Integration tests run against the compose `db` server, in a separate database.

DATABASE_URL must point at that server (any database on it); the session creates and drops
`clio_findings_test` so the seeded dev database is never touched.
"""

import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from alembic import command
from app.seed.__main__ import run

TEST_DB = "clio_findings_test"
BACKEND = Path(__file__).resolve().parents[2]
REAL_SNAPSHOT = BACKEND.parent / "data" / "snapshot"
NO_CONTENT = BACKEND / "tests" / "fixtures" / "no-content-dir"  # deliberately does not exist
FIXTURE_CONTENT = BACKEND / "tests" / "fixtures" / "content"


def pytest_collection_modifyitems(items):
    for item in items:
        if "tests/integration/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def test_engine():
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        pytest.fail("DATABASE_URL is not set; see backend/README.md for the integration test setup")
    admin_url = make_url(raw)
    assert admin_url.database != TEST_DB
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    engine = create_engine(admin_url.set(database=TEST_DB))
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
    admin.dispose()


def alembic_config(engine) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["engine"] = engine
    return config


@pytest.fixture
def empty_engine(test_engine):
    """The test database with nothing in it (no tables, no alembic_version)."""
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    return test_engine


@pytest.fixture
def migrated_engine(empty_engine):
    command.upgrade(alembic_config(empty_engine), "head")
    return empty_engine


@pytest.fixture
def seeded_engine(migrated_engine):
    run(REAL_SNAPSHOT, NO_CONTENT, engine=migrated_engine)
    return migrated_engine
