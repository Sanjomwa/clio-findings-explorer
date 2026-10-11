"""query_snapshot validation: parser only, no database."""

import pytest
import snapshot_query as sq

ACCEPTED = {
    "plain": "SELECT iso2, week_start_date FROM regime_weeks WHERE primary_regime = 'CRISIS'",
    "cte": "WITH c AS (SELECT primary_regime FROM regime_weeks) SELECT count(*) FROM c",
    "union": "SELECT iso2 FROM regime_weeks UNION SELECT iso2 FROM findings",
    "subquery": "SELECT * FROM (SELECT iso2 FROM regime_weeks) t WHERE iso2 IN (SELECT iso2 FROM findings)",
    "trailing semicolon": "SELECT 1;",
    "current_setting one arg": "SELECT current_setting('server_version')",
}

REJECTED = {
    "insert": "INSERT INTO findings (slug) VALUES ('x')",
    "update": "UPDATE findings SET title = 'x'",
    "delete": "DELETE FROM findings",
    "merge": "MERGE INTO findings f USING regime_weeks r ON false WHEN NOT MATCHED THEN DO NOTHING",
    "create": "CREATE TABLE t (a int)",
    "drop": "DROP TABLE findings",
    "alter": "ALTER TABLE findings ADD COLUMN a int",
    "truncate": "TRUNCATE findings",
    "copy": "COPY findings TO '/tmp/x'",
    "grant": "GRANT SELECT ON findings TO public",
    "two statements": "SELECT 1; SELECT 2",
    "select into": "SELECT * INTO t FROM regime_weeks",
    "for update": "SELECT * FROM findings FOR UPDATE",
    "for share": "SELECT * FROM findings FOR SHARE",
    "pg_read_file": "SELECT pg_read_file('PG_VERSION')",
    "qualified pg_read_file": "SELECT pg_catalog.pg_read_file('PG_VERSION')",
    "quoted pg_read_file": "SELECT \"pg_read_file\"('PG_VERSION')",
    "pg_sleep": "SELECT pg_sleep(10)",
    "set_config": "SELECT set_config('role', 'clio', false)",
    "lo_import": "SELECT lo_import('/etc/passwd')",
    "dblink": "SELECT * FROM dblink('x', 'select 1') AS t(a int)",
    "query_to_xml": "SELECT query_to_xml('select 1', true, true, '')",
    "current_setting two args": "SELECT current_setting('x', true)",
    "data-modifying CTE": "WITH d AS (DELETE FROM findings RETURNING *) SELECT * FROM d",
    "set role": "SET ROLE clio",
    "explain": "EXPLAIN SELECT 1",
    "unparseable": "SELEC FROM WHERE ((",
    "empty": "",
    "whitespace": "   \n ",
    "only semicolon": ";",
}


@pytest.mark.parametrize("sql", ACCEPTED.values(), ids=ACCEPTED.keys())
def test_accepted(sql):
    sq.validate(sql)


@pytest.mark.parametrize("sql", REJECTED.values(), ids=REJECTED.keys())
def test_rejected(sql):
    with pytest.raises(sq.Rejected):
        sq.validate(sql)


def test_rejection_never_touches_the_database():
    r = sq.run("DELETE FROM findings", db_url="postgresql://nobody@127.0.0.1:1/none")
    assert r["error"].startswith("Rejected before reaching the database")


def test_json_safe():
    import datetime as dt
    import decimal

    assert sq._json_safe(dt.date(2024, 6, 22)) == "2024-06-22"
    assert sq._json_safe(dt.datetime(2024, 6, 22, 1, tzinfo=dt.UTC)) == "2024-06-22T01:00:00+00:00"
    assert sq._json_safe(decimal.Decimal("1.5")) == 1.5
