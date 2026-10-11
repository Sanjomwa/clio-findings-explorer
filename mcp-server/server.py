"""findings-explorer-tools: read-only MCP server (stdio).

Tool `spec_lookup` reads openapi.yaml at the repository root on every
call. Tool `query_snapshot` runs one validated read query against the local database.
See mcp-server/README.md.
"""

from pathlib import Path

import snapshot_query
import yaml
from mcp.server.fastmcp import FastMCP

# mcp-server/server.py -> repository root, independent of the working directory.
SPEC_PATH = Path(__file__).resolve().parent.parent / "openapi.yaml"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

mcp = FastMCP("findings-explorer-tools")


def _load_spec():
    with open(SPEC_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ref_name(ref):
    return ref.rsplit("/", 1)[-1]


def _resolve(spec, node):
    """Follow a local $ref (one hop at a time) to its target, if any."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        target = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node = target
        seen += 1
    return node


def _schema_label(schema):
    if not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    for key in ("oneOf", "anyOf"):
        if key in schema:
            return " | ".join(filter(None, (_schema_label(s) for s in schema[key])))
    if schema.get("type") == "array":
        return f"array of {_schema_label(schema.get('items')) or 'unknown'}"
    return schema.get("type")


def _parameters(spec, op, path_item):
    out = []
    for p in list(path_item.get("parameters", [])) + list(op.get("parameters", [])):
        r = _resolve(spec, p)
        out.append({"name": r.get("name"), "in": r.get("in"),
                    "required": bool(r.get("required", False)),
                    "schema": _schema_label(r.get("schema"))})
    return out


def _responses(spec, op):
    out = []
    for status, resp in op.get("responses", {}).items():
        r = _resolve(spec, resp)
        schema = None
        for media in (r.get("content") or {}).values():
            schema = _schema_label(media.get("schema"))
            break
        out.append({"status": str(status), "schema": schema})
    return out


def _operations(spec):
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            if method in item:
                yield path, method, item, item[method]


def lookup(path=None, method=None):
    spec = _load_spec()
    ops = list(_operations(spec))
    version = spec.get("info", {}).get("version")
    declared = sorted({p for p, *_ in ops})

    if path is None and method is None:
        return {"version": version,
                "operations": [{"method": m.upper(), "path": p, "operationId": o.get("operationId"),
                                "summary": o.get("summary")} for p, m, _, o in ops]}

    wanted = method.lower() if method else None
    matches = [(p, m, i, o) for p, m, i, o in ops
               if (path is None or p == path) and (wanted is None or m == wanted)]
    if not matches:
        return {"version": version, "found": False,
                "message": f"No declared operation for path={path!r} method={method!r}.",
                "declared_paths": declared}
    return {"version": version, "found": True,
            "operations": [{"method": m.upper(), "path": p, "operationId": o.get("operationId"),
                            "summary": o.get("summary"),
                            "parameters": _parameters(spec, o, i),
                            "responses": _responses(spec, o)} for p, m, i, o in matches]}


@mcp.tool()
def spec_lookup(path: str | None = None, method: str | None = None) -> dict:
    """Look up the API contract in openapi.yaml (read fresh on every call).

    With no arguments: the contract version and every operation (method, path,
    operationId, summary). With `path` (exact, e.g. "/api/findings/{slug}") and
    optionally `method`: each matching operation's parameters and responses.
    An undeclared path or method returns found=false and the declared paths.
    """
    return lookup(path, method)


@mcp.tool()
def query_snapshot(sql: str) -> dict:
    """Run one read-only SQL query against the local snapshot database, to check a data claim.

    Read-only: the query runs in a READ ONLY transaction under a NOLOGIN role that can only
    SELECT, and is rolled back. Rejected before reaching the database (error returned): more
    than one statement; anything but SELECT, a set operation of SELECTs, or WITH ... SELECT;
    INSERT/UPDATE/DELETE/MERGE/CREATE/DROP/ALTER/TRUNCATE/COPY/GRANT anywhere (including in
    CTEs); SELECT ... INTO; FOR UPDATE/SHARE; calls to pg_*, lo_*, dblink*, set_config,
    query_to_xml, or current_setting with a second argument; anything the parser cannot read.
    Statement timeout 5 s. At most 200 rows are returned: `truncated` is true when there were
    more. Returns columns, rows, row_count and truncated, or {"error": ...}.

    The result is evidence for checking a claim, not the claim itself: quote the exact query
    you ran alongside any figure you take from it.
    """
    return snapshot_query.run(sql)


if __name__ == "__main__":
    mcp.run()
