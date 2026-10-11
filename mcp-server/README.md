# findings-explorer-tools (MCP server)

Two tools in a small, read-only [MCP](https://modelcontextprotocol.io) server over stdio, so a coding agent can look up the API contract instead of guessing it. Python 3.12, the `mcp` SDK (pinned `<2`, because mcp 2.x renamed `FastMCP`), PyYAML, `psycopg` and `sqlglot`. It writes no files; its only network access is the local Postgres in `query_snapshot`.

## Tool

`spec_lookup(path: str | None = None, method: str | None = None)` reads `openapi.yaml` at the repository root on every call (no cache). The root is found from `server.py`'s own location, not the working directory.

- **No arguments:** `info.version` and every operation: method, path, `operationId`, summary.
- **`path` (exact, e.g. `/api/findings/{slug}`), optionally `method`:** each matching operation with its parameters (name, `in`, required, schema type or `$ref` name) and responses (status code, schema `$ref` name).
- **Undeclared path or method:** `found: false`, a message, and the declared paths. It does not raise.

### `query_snapshot(sql: str)`

Runs one read query against the local seeded database, so an agent can check a data claim instead of asserting it. The result is evidence: quote the exact query with any figure taken from it.

1. **Parse** with `sqlglot` (Postgres dialect). Rejected without touching the database: more than one statement; a top level that is not `SELECT`, a set operation of `SELECT`s, or `WITH ... SELECT`; INSERT, UPDATE, DELETE, MERGE, CREATE, DROP, ALTER, TRUNCATE, COPY, GRANT (and REVOKE, SET, transaction commands, anything parsed as a raw command) anywhere in the tree, including inside CTEs; `SELECT ... INTO`; `FOR UPDATE` / `FOR SHARE`; calls to functions named `pg_*`, `lo_*`, `dblink*`, `query_to_xml*`, `set_config`, or `current_setting` with a second argument (constants `DENIED_*` in `snapshot_query.py`). Text `sqlglot` cannot parse is rejected (fail closed).
2. **Run** over `FINDINGS_DB_URL` in one transaction: `SET TRANSACTION READ ONLY`, `SET LOCAL statement_timeout = '5s'`, `SET LOCAL ROLE snapshot_reader`, then the query through a server-side cursor (one statement only, bounded memory), then roll back.
3. **Return** `columns`, `rows` (dates and timestamps as ISO strings, `Decimal` as float), `row_count` (at most 200) and `truncated` (true when more than 200 rows matched). Any database error comes back as `{"error": ...}`, never a stack trace.

**The role.** The local `clio` user is a superuser in the official Postgres image, so a read-only transaction alone would still allow `pg_read_file`. Migration `0002_snapshot_reader_role` creates `snapshot_reader` (`NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT`) with `USAGE` on schema `public` and `SELECT` on its tables, including `alembic_version` (a revision id only), plus default privileges for later tables. Apply it with `docker compose run --rm seed`. Roles are cluster-wide: the downgrade revokes the grants and drops the role only if no other database on the server still uses it.

**Known gaps.**
- The function deny list is a list, not an allowlist: a dangerous function with a name outside the prefixes is not caught by the parser (the role and the read-only transaction still apply).
- The parser is `sqlglot`'s, not Postgres's; the two can disagree about odd syntax. The server-side cursor makes Postgres itself refuse multiple statements, which narrows this.
- The role protects only because `SET LOCAL ROLE` runs before the query; it is in `_execute`, and a test checks the query runs as `snapshot_reader`.
- `snapshot_reader` can still read `pg_catalog` and `information_schema` (Postgres default), and a heavy read within 5 s is allowed.
- Needs the compose `db` up and seeded; without it the tool returns an `error`.

## Registration

[`.mcp.json`](../.mcp.json) at the repository root (project scope):

```json
{
  "mcpServers": {
    "findings-explorer-tools": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PROJECT_DIR:-.}/mcp-server", "python", "server.py"],
      "env": {
        "FINDINGS_DB_URL": "${FINDINGS_DB_URL:-postgresql://clio:clio-local-only@127.0.0.1:55432/clio_findings}"
      }
    }
  }
}
```

Claude Code expands `${VAR:-default}` in `command` and `args`, but `CLAUDE_PROJECT_DIR` is set only in the spawned server's environment, not in Claude Code's own, so in `.mcp.json` the `:-.` default applies and the path is relative to the directory Claude Code was started in. Start sessions at the repository root. The `env` block uses the same expansion. Source, Claude Code docs, "Environment variable expansion in `.mcp.json`": "Environment variables can be expanded in: `command`: the server executable path; `args`: command-line arguments; `env`: environment variables passed to the server; `url`; `headers`", with syntax `${VAR}` and `${VAR:-default}`. The default is the local placeholder from `.env.example`, not a secret. Claude Code asks for approval before using a project-scoped server; `claude mcp reset-project-choices` resets that.

## Tests

```
uv run --directory mcp-server pytest -v
```

`spec_lookup` tests call the tool directly against the real `openapi.yaml` (eight operations, version `0.4.1`, filters, undeclared path and method) and check that exactly two tools are registered. `test_query_snapshot_unit.py` checks the parser (no database). `test_query_snapshot_integration.py` (marker `integration`) needs the compose `db` seeded and migrated to `0002`, and is skipped with a reason when the database is unreachable. Update the `spec_lookup` tests with any contract change.
