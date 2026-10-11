# Agent permissions

**Version:** 2 (2026-10-10). What a coding agent may and may not do in this repository. `AGENTS.md` holds the full rules; this page summarises the boundaries in one place. If the two disagree, `AGENTS.md` wins and this page is corrected.

## Filesystem scope

The agent works only inside this repository's directory, plus its own session scratchpad for temporary files. It does not read `~/.ssh`, `~/.config/gcloud` or other projects. `data/snapshot/` is read-only for the agent.

## Git

The agent never runs `git commit`, `push`, `pull`, `tag`, `merge`, `rebase`, `reset`, `cherry-pick`, `revert`, `am`, `branch -d`/`-D`, `update-ref` or `commit-tree`, and never `gh pr create`, `gh pr merge` or `gh release create`. Read commands (`status`, `diff`, `log`, `show`, `fetch`) and `git add` / `git restore --staged` are allowed. The `block-autonomous-git` hook ([agent-hooks/README.md](../agent-hooks/README.md)) enforces the common forms; the rule holds whether or not the hook catches a given command. Sam commits, pushes, tags and deploys.

## API contract

A route's method and path must be in `openapi.yaml` before the router is written. The `spec-first-guard` hook ([agent-hooks/README.md](../agent-hooks/README.md)) blocks any `Write`, `Edit` or `MultiEdit` of a `.py` file under `backend/app/routers/` that declares a route not in the spec, and fails closed on anything it cannot check. The rule holds whether or not the hook catches a given change.

## MCP server

The project MCP server `findings-explorer-tools` ([mcp-server/README.md](../mcp-server/README.md)) has two tools, both read-only. `spec_lookup` reads `openapi.yaml` and nothing else. `query_snapshot` runs one parser-checked read query against the local snapshot database: a `READ ONLY` transaction, a 5 s timeout, a 200-row cap, and `SET LOCAL ROLE snapshot_reader`, a no-login role with `SELECT` only (the local database user is a superuser, so the role, not the transaction, is what blocks server-file functions). Neither tool writes files. Claude Code asks Sam to approve a project-scoped server before first use.

## Network

Package installs from PyPI and npm are allowed, as is reading public documentation. The agent makes no calls to BigQuery, other GCP APIs or any CLIO endpoint, and has no deploy credentials.

## Data

The agent never edits, regenerates or "fixes" snapshot files, and never runs `ops/export_snapshot.py` against BigQuery; Sam alone runs it. Nothing flagged synthetic enters the snapshot, the database, the curated content or the UI; the only exception is an obviously fake synthetic column in fixtures under `ops/tests/`. Every factual claim about the data comes from a query against the snapshot, and the query is reported.

## Secrets

The agent reads `.env.example` but never creates or edits `.env` with real values, and never prints a secret. It never writes key files (`*-key.json`, `*.pem`, `service-account*`) into the repository; `.gitignore` also excludes them.

## Escalation

When a hook blocks a command, a rule seems wrong, or a prompt contradicts the repository, the agent stops and reports to Sam instead of finding another route. When a prompt says STOP, the agent stops. Failures are diagnosed and the cause stated before any fix.

## Provenance

Every task ends with a report (files changed, commands run and their results, what was not done, what in the prompt was wrong) and an entry in [ai-workflow-log.md](ai-workflow-log.md), written as the work happens. A command enters the `AGENTS.md` Commands table only after it has been run successfully.
