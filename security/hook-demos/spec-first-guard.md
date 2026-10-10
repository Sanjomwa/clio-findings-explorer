# Demo: spec-first-guard blocks a router for an undeclared route, and the MCP server answers spec lookups

**Date:** 2026-10-10, about 12:31 EAT (+03:00)
**Agent:** Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`)
**Hook:** [`agent-hooks/spec_first_guard.py`](../../agent-hooks/spec_first_guard.py), registered in [`.claude/settings.json`](../../.claude/settings.json) as a PreToolUse hook on `Write|Edit|MultiEdit`
**MCP server:** `findings-explorer-tools` ([`mcp-server/`](../../mcp-server/), registered in [`.mcp.json`](../../.mcp.json)), tool `spec_lookup`
**Rule enforced:** AGENTS.md hard rule 2 (spec first)

## Setup

The tree held the Part A changes, uncommitted. `backend/` did not exist. `claude mcp list` reported:

```
findings-explorer-tools: uv run --directory ${CLAUDE_PROJECT_DIR}/mcp-server python server.py - ✔ Connected
```

## 1. `spec_lookup` through MCP

### No arguments

```json
{
  "version": "0.3.0",
  "operations": [
    {"method": "GET", "path": "/api/health", "operationId": "getHealth", "summary": "Liveness and readiness"},
    {"method": "GET", "path": "/api/timeline", "operationId": "getTimeline", "summary": "Weekly regime series for the timeline strip"},
    {"method": "GET", "path": "/api/findings", "operationId": "listFindings", "summary": "List curated findings"},
    {"method": "GET", "path": "/api/findings/{slug}", "operationId": "getFinding", "summary": "One finding in full"},
    {"method": "GET", "path": "/api/findings/{slug}/evidence/acled", "operationId": "getAcledEvidence", "summary": "ACLED conflict-event evidence card"},
    {"method": "GET", "path": "/api/findings/{slug}/evidence/ooni", "operationId": "getOoniEvidence", "summary": "OONI internet-measurement evidence card"},
    {"method": "GET", "path": "/api/findings/{slug}/evidence/google-transparency", "operationId": "getGoogleTransparencyEvidence", "summary": "Google Transparency Report evidence card"},
    {"method": "GET", "path": "/api/methodology", "operationId": "getMethodology", "summary": "Classification scheme, source notes and snapshot manifest"}
  ]
}
```

(Pretty-printed with one operation per line for this write-up; the content is as returned.)

### `path="/api/findings/{slug}"`

```json
{
  "version": "0.3.0",
  "found": true,
  "operations": [
    {
      "method": "GET",
      "path": "/api/findings/{slug}",
      "operationId": "getFinding",
      "summary": "One finding in full",
      "parameters": [
        {"name": "slug", "in": "path", "required": true, "schema": "string"}
      ],
      "responses": [
        {"status": "200", "schema": "FindingDetailResponse"},
        {"status": "404", "schema": "Error"},
        {"status": "422", "schema": "ValidationError"}
      ]
    }
  ]
}
```

## 2. The agent tries to write a router for an undeclared route

Write tool call: create `backend/app/routers/demo_undeclared.py` with a FastAPI `APIRouter` declaring only `GET /api/undeclared`.

Result returned to the agent (the file was not written):

```
PreToolUse:Write hook error: [python3 "${CLAUDE_PROJECT_DIR}/agent-hooks/spec_first_guard.py"]: spec-first-guard: BLOCKED. These routes are not declared in openapi.yaml:
  GET /api/undeclared
AGENTS.md hard rule 2: edit openapi.yaml first, then STOP so Sam can commit that edit separately. Do not write the router until the operation is in the committed spec.
```

Afterwards, `ls backend/app/routers/demo_undeclared.py backend` reported both paths as "No such file or directory". The agent did not route around the block.

## 3. Allowed counterpart

The same file, declaring only `GET /api/health` (declared in `openapi.yaml`), was written with:

```
File created successfully at: .../backend/app/routers/demo_undeclared.py
```

The demo file and the directories the demo created (`backend/app/routers`, `backend/app`, `backend`) were then removed. `ls backend` reported "No such file or directory" and `git status --short` showed no `backend/` entry.

## What this shows and does not show

- It shows the registered hook is loaded in a live session, blocks a `Write` of a router with an undeclared method and path before the file exists, and allows a router whose route is in `openapi.yaml`.
- It shows the MCP server is connected and `spec_lookup` reads the contract (version 0.3.0) through the MCP protocol.
- Only the `Write` tool was exercised live. `Edit` and `MultiEdit`, other decorator forms and the known gaps are covered by the unit tests in `agent-hooks/tests/` and listed in [`agent-hooks/README.md`](../../agent-hooks/README.md).
