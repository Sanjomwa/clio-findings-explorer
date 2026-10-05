# Agent permissions

**Version:** 1 (2026-10-05). What a coding agent may and may not do in this repository. `AGENTS.md` holds the full rules; this page summarises the boundaries in one place. If the two disagree, `AGENTS.md` wins and this page is corrected.

## Filesystem scope

The agent works only inside this repository's directory, plus its own session scratchpad for temporary files. It does not read `~/.ssh`, `~/.config/gcloud` or other projects. `data/snapshot/` is read-only for the agent.

## Git

The agent never runs `git commit`, `push`, `pull`, `tag`, `merge`, `rebase`, `reset`, `cherry-pick`, `revert`, `am`, `branch -d`/`-D`, `update-ref` or `commit-tree`, and never `gh pr create`, `gh pr merge` or `gh release create`. Read commands (`status`, `diff`, `log`, `show`, `fetch`) and `git add` / `git restore --staged` are allowed. The `block-autonomous-git` hook ([agent-hooks/README.md](../agent-hooks/README.md)) enforces the common forms; the rule holds whether or not the hook catches a given command. Sam commits, pushes, tags and deploys.

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
