# findings-explorer-tools (MCP server)

A small, read-only [MCP](https://modelcontextprotocol.io) server over stdio, so a coding agent can look up the API contract instead of guessing it. Python 3.12, the `mcp` SDK (pinned `<2`, because mcp 2.x renamed `FastMCP`), and PyYAML. It writes no files and makes no network calls.

## Tool

`spec_lookup(path: str | None = None, method: str | None = None)` reads `openapi.yaml` at the repository root on every call (no cache). The root is found from `server.py`'s own location, not the working directory.

- **No arguments:** `info.version` and every operation: method, path, `operationId`, summary.
- **`path` (exact, e.g. `/api/findings/{slug}`), optionally `method`:** each matching operation with its parameters (name, `in`, required, schema type or `$ref` name) and responses (status code, schema `$ref` name).
- **Undeclared path or method:** `found: false`, a message, and the declared paths. It does not raise.

The server does not build `query_snapshot`; that tool needs the database and comes in Phase 1c.

## Registration

[`.mcp.json`](../.mcp.json) at the repository root (project scope):

```json
{
  "mcpServers": {
    "findings-explorer-tools": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PROJECT_DIR:-.}/mcp-server", "python", "server.py"]
    }
  }
}
```

Claude Code expands `${VAR:-default}` in `command` and `args`, but `CLAUDE_PROJECT_DIR` is set only in the spawned server's environment, not in Claude Code's own, so in `.mcp.json` the `:-.` default applies and the path is relative to the directory Claude Code was started in. Start sessions at the repository root. Claude Code asks for approval before using a project-scoped server; `claude mcp reset-project-choices` resets that.

## Tests

```
uv run --directory mcp-server pytest -v
```

The tests call the tool function directly against the real `openapi.yaml`: eight operations, version `0.3.0`, path and method filters, undeclared path and method, and that exactly one tool is registered. They need the contract to stay at 0.3.0 and eight operations; update them with any contract change.
