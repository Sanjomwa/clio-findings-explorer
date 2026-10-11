"""query_snapshot: validate one read query with sqlglot, run it as `snapshot_reader`.

Two independent layers: the parser rejects anything that is not a single read query (fail
closed), and the database runs it in a read-only transaction under the NOLOGIN role
`snapshot_reader`, which holds SELECT on the app tables only.
"""

import datetime as dt
import decimal
import os
import uuid

import psycopg
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ROW_CAP = 200
STATEMENT_TIMEOUT = "5s"
READER_ROLE = "snapshot_reader"

# Function-call deny list (a list, not an allowlist; see mcp-server/README.md, Known gaps).
# Matched case-insensitively on the bare function name, so `pg_catalog.pg_read_file` and
# `"pg_read_file"` are caught too.
DENIED_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "query_to_xml")
DENIED_FUNCTIONS = frozenset({"set_config"})
# current_setting(name) reads a setting; current_setting(name, missing_ok) is denied.
DENIED_WHEN_TWO_ARGS = frozenset({"current_setting"})

# Nodes denied anywhere in the tree, including inside CTEs and subqueries.
DENIED_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.TruncateTable, exp.Copy, exp.Grant, exp.Revoke, exp.Command, exp.Into, exp.Lock,
    exp.Set, exp.Transaction, exp.Commit, exp.Rollback,
)  # fmt: skip

_ALLOWED_TOP = (exp.Select, exp.SetOperation)


class Rejected(ValueError):
    """The statement is refused before it reaches the database."""


def _function_name(node):
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    if isinstance(node, exp.Func):
        return node.sql_name().lower()
    return None


def validate(sql: str):
    """Return the parsed statement, or raise Rejected."""
    if not isinstance(sql, str) or not sql.strip():
        raise Rejected("empty statement")
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except SqlglotError as e:
        raise Rejected(f"could not parse the statement ({type(e).__name__}); refused") from None
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise Rejected(f"exactly one statement is allowed, got {len(statements)}")
    tree = statements[0]

    top = tree
    while isinstance(top, exp.Subquery):
        top = top.this
    if not isinstance(top, _ALLOWED_TOP):
        raise Rejected(
            f"only SELECT, a set operation of SELECTs, or WITH ... SELECT is allowed, "
            f"got {type(top).__name__}"
        )

    for node in tree.walk():
        if isinstance(node, DENIED_NODES):
            raise Rejected(f"{type(node).__name__} is not allowed anywhere in the statement")
        name = _function_name(node)
        if name is None:
            continue
        if name.startswith(DENIED_FUNCTION_PREFIXES) or name in DENIED_FUNCTIONS:
            raise Rejected(f"function {name}() is not allowed")
        if name in DENIED_WHEN_TWO_ARGS and len(node.expressions) > 1:
            raise Rejected(f"{name}() with a second argument is not allowed")
    return tree


def _json_safe(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else str(v)
    if isinstance(v, decimal.Decimal):
        return float(v) if v.is_finite() else str(v)
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()
    if isinstance(v, uuid.UUID):
        return str(v)
    return str(v)


def run(sql: str, db_url: str | None = None) -> dict:
    """Validate, then execute. Never raises; failures come back as {"error": ...}."""
    try:
        validate(sql)
    except Rejected as e:
        return {"error": f"Rejected before reaching the database: {e}"}
    db_url = db_url or os.environ.get("FINDINGS_DB_URL")
    if not db_url:
        return {"error": "FINDINGS_DB_URL is not set"}
    try:
        return _execute(sql, db_url)
    except psycopg.Error as e:
        diag = getattr(e, "diag", None)
        message = (diag.message_primary if diag and diag.message_primary else str(e)).strip()
        return {"error": f"{type(e).__name__}: {message}"}
    except Exception as e:  # never surface a stack trace to the agent
        return {"error": f"{type(e).__name__}: {str(e).strip()[:300]}"}


def _execute(sql: str, db_url: str) -> dict:
    with psycopg.connect(db_url, connect_timeout=5) as conn:
        try:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
            conn.execute(f"SET LOCAL ROLE {READER_ROLE}")
            # A server-side cursor keeps memory bounded and takes exactly one statement.
            with conn.cursor(name="query_snapshot") as cur:
                cur.execute(sql)
                columns = [d.name for d in cur.description or []]
                fetched = cur.fetchmany(ROW_CAP + 1)
        finally:
            conn.rollback()
    rows = [[_json_safe(v) for v in row] for row in fetched[:ROW_CAP]]
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "truncated": len(fetched) > ROW_CAP}  # fmt: skip
