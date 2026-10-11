"""query_snapshot against the compose db (seeded). Skipped when it is unreachable."""

import os

import psycopg
import pytest
import snapshot_query as sq

DB_URL = os.environ.get(
    "FINDINGS_DB_URL", "postgresql://clio:clio-local-only@127.0.0.1:55432/clio_findings"
)


def _reachable():
    try:
        with psycopg.connect(DB_URL, connect_timeout=2) as c:
            c.execute("SELECT 1 FROM regime_weeks LIMIT 1")
        return None
    except Exception as e:
        return f"compose db not reachable or not seeded at FINDINGS_DB_URL ({type(e).__name__})"


_reason = _reachable()
pytestmark = [pytest.mark.integration, pytest.mark.skipif(_reason is not None, reason=_reason or "")]


def run(sql):
    return sq.run(sql, DB_URL)


def test_count():
    r = run("SELECT count(*) FROM regime_weeks")
    assert r == {"columns": ["count"], "rows": [[1523]], "row_count": 1, "truncated": False}


def test_row_cap():
    r = run("SELECT * FROM regime_weeks")
    assert r["row_count"] == 200 and len(r["rows"]) == 200 and r["truncated"] is True


def test_dates_are_iso_strings():
    r = run("SELECT week_start_date, computed_at FROM regime_weeks LIMIT 1")
    assert isinstance(r["rows"][0][0], str) and "T" in r["rows"][0][1]


def test_timeout_returns_error_not_hang():
    r = run("SELECT count(*) FROM regime_weeks a, regime_weeks b, regime_weeks c, regime_weeks d")
    assert "error" in r and "timeout" in r["error"].lower()


def test_findings_readable_as_reader():
    r = run("SELECT count(*) FROM findings")
    assert "error" not in r and r["rows"][0][0] >= 0


def test_runs_as_snapshot_reader():
    assert run("SELECT current_user")["rows"] == [["snapshot_reader"]]


def test_database_error_is_returned():
    r = run("SELECT * FROM no_such_table")
    assert "error" in r and "no_such_table" in r["error"] and "Traceback" not in r["error"]


def test_database_refuses_multiple_statements_even_if_parser_were_bypassed():
    with pytest.raises(psycopg.Error):
        sq._execute("SELECT 1; SELECT 2", DB_URL)


def test_database_layer_blocks_file_read_and_writes_without_the_parser():
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        sq._execute("SELECT pg_read_file('PG_VERSION')", DB_URL)
    with pytest.raises(psycopg.Error):
        sq._execute("INSERT INTO snapshot_meta SELECT * FROM snapshot_meta", DB_URL)
