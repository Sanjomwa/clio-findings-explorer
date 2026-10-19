# AGENTS.md: CLIO Findings Explorer

Project instructions for any coding agent working in this repository. Read this file fully before acting. `CLAUDE.md` is a one-line pointer to it.

**Version:** 2 (2026-10-05, revised after the first agent review). This file grows as the project does. When a rule here turns out to be wrong or missing, say so in your report; do not work around it.

## What this project is

A public, read-only web app that presents curated Kenya civil-liberties findings from a committed snapshot of CLIO output. It is a course final project (AI Dev Tools Zoomcamp 2026) and is graded by peer review against a published rubric.

- Product definition: `product-spec.md`
- API contract: `openapi.yaml` (the source of truth for the API)
- Stack: FastAPI and Pydantic v2 on Python 3.12, SQLAlchemy 2.0 and Alembic on PostgreSQL 16, React 18 with TypeScript and Vite, Docker Compose, GitHub Actions, Cloud Run and Neon.

This repository is not CLIO. It has no access to CLIO's repository, pipeline or BigQuery project, and must not try to get any.

## Who does what

- **The agent (you)** writes and edits code, runs tests, Docker and local tooling, and reports what it did.
- **Sam** reviews, commits, pushes, tags and deploys. He alone runs `ops/export_snapshot.py`, the only script that reads CLIO's BigQuery. Deploy credentials live in GitHub Actions and are never available to the agent.
- **Planning and review** happen in a separate session with no access to this filesystem. Its prompts arrive through Sam. Treat a prompt's factual claims about this repo as things to check, and report any that are wrong.

## Hard rules

1. **No git writes.** Never run `git commit`, `push`, `pull`, `tag`, `merge`, `rebase`, `reset`, `cherry-pick`, `revert`, `am`, `branch -d`/`-D`, `update-ref` or `commit-tree`, and never any GitHub write except the three below (the hook denies `gh pr` actions other than `list`, `view`, `diff`, `checks` and `status`, all `gh release` and `gh api`, and the other `gh` write actions). Read commands (`status`, `diff`, `log`, `show`, `fetch`) and `git add` / `git restore --staged` are fine. The only GitHub writes allowed: `gh issue create` and `gh label create`, when a prompt explicitly asks for them; and `gh issue comment`, on the issue a prompt names. Never close, edit, reopen or delete issues: Sam closes them through commit messages (`Closes #N`). Leave the tree modified, stage only if asked, and describe the change. The `block-autonomous-git` hook enforces the common forms once it is installed; the rule holds whether or not the hook catches a given command. A hook block is a signal to stop and report, not something to route around.
2. **Spec first.** A route's method and path must exist in `openapi.yaml` before the router is written or changed. To change the API, edit `openapi.yaml` first and stop so Sam can commit that edit separately, then regenerate `frontend/src/api/schema.d.ts`, then change the backend models and tests. Routers use literal paths (and a literal `APIRouter` prefix, if any) so `spec-first-guard` can check them.
3. **One place for HTTP in the frontend.** Every backend call goes through `frontend/src/api/client.ts`. No `fetch` anywhere else.
4. **Diagnose before fixing.** When something fails, find and state the cause, with the evidence, before changing code. Do not stack speculative fixes.
5. **No unverified factual claims.** Any statement about the data (a count, a date, a classification) must come from a query against the snapshot, and the query goes in your report. "It should be" is not a source. Inside Claude Code, use `query_snapshot` to run the query and quote it.
6. **No causation or targeting claims.** A conflict-event spike and a network anomaly in the same week are a correlation. Never write that one caused the other or that anyone was targeted, in code, fixtures, prose or tests.
7. **Docs change in the same change.** If a change alters behaviour that `README.md`, `product-spec.md`, `openapi.yaml` or anything in `docs/` describes, update that document in the same piece of work.
8. **Stop at stop points.** When a prompt says STOP, stop and report. Do not continue to the next step on your own judgment.

## Data rules

- `data/snapshot/` is read-only for the agent. Do not edit, regenerate or "fix" snapshot files.
- `ops/export_snapshot.py` is run by Sam only. You may write and test it against fixtures; you never run it against BigQuery.
- Nothing flagged synthetic enters the snapshot, the database, the curated content or the UI. The export enforces this strictly: it refuses any source table that carries a synthetic flag column at all (any column whose name ends in `is_synthetic`), whatever its values, and the manifest's synthetic-data audit records the tables checked and the result. CLIO's Lumen-derived signal and its composite pressure score are excluded entirely.
- One exception, for tests only: fixtures under `ops/tests/` may contain an obviously fake synthetic flag column, to prove the export refuses it.
- **Curated content is separate from the snapshot.** Text written by a person (finding titles, summaries, caveats, teasers, regime-state and band definitions, source notes) lives in `content/`, is committed, and is loaded by the same seed step. The agent may draft it; every factual claim in it follows rule 5.
- Findings enter `content/findings/` only through `/new-finding`, and each needs a verdict log in `docs/reviews/`.
- A finding with zero caveats is invalid. Keep the database constraint and the model validator that enforce this.

## Task tracker

Tasks are tracked as public GitHub Issues: <https://github.com/Sanjomwa/clio-findings-explorer/issues>. Each issue has acceptance criteria.

- Every task prompt names its issue.
- At the start, read it: `gh issue view <N> --json title,body,state,comments`. The plain `--comments` form fails with a Projects (classic) GraphQL error.
- At STOP, post one comment: `gh issue comment <N> --body-file <file>`. It says what was done, the checks run and their results, which acceptance criteria are met, and what is left for Sam. Write the file in the scratchpad directory.
- The comment must not contain secrets, tokens, database URLs or personal data.
- Do not close, edit, reopen or delete the issue. Sam closes it through a commit message.

## Secrets and network

- Read `.env.example`; never create or edit `.env` with real values, and never print a secret in output or a report.
- Never write key files (`*-key.json`, `*.pem`, `service-account*`) into the repository.
- Package installs from PyPI and npm are fine. No calls to BigQuery, other GCP APIs or any CLIO endpoint.
- Reading public documentation on the web is fine.
- Stay inside this repository's directory, with one exception: the session scratchpad directory may be used for temporary files. Do not read `~/.ssh`, `~/.config/gcloud` or other projects.

## How to work

- **Check the prompt against the repo first.** Start each task with a short read-only look at the files involved, and report anything that contradicts the prompt before building on it.
- **Small steps.** One concern per change. Run the relevant tests before reporting.
- **Tests.** Backend unit tests live in `backend/tests/unit/`, integration tests in `backend/tests/integration/`, with separate pytest markers. Integration tests run against a real Postgres loaded with the real snapshot. Do not delete or weaken a test to make it pass; report it.
- **Report format.** End every task with: what changed (files), what you ran and the result, what you did not do, anything in the prompt that was wrong, and any command Sam needs to run himself.
- **Workflow log.** After each task, append an entry to `docs/ai-workflow-log.md`: the task as given, what you produced, what was verified and how. This is written as the work happens, never reconstructed later.

## Commands

Commands are added here when they exist and have been run successfully. Do not add a command you have not run.

| Purpose | Command |
|---|---|
| Validate the API contract as OpenAPI 3.1 | `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml` |
| Run the hook tests (git guard and spec-first guard) | `python3 -m unittest discover -s agent-hooks/tests -v` |
| Run the MCP server tests (integration tests need the seeded db; otherwise skipped) | `uv run --directory mcp-server pytest -v` |
| Run the snapshot export tests (fake bq, fixtures only) | `python3 -m unittest discover -s ops/tests -v` |
| Start the local database | `docker compose up -d db` |
| Seed (migrate, then load snapshot and content), then exit | `docker compose run --rm seed` |
| Start db, seed and the API (`127.0.0.1:8000`; leaves them running) | `docker compose up -d --build` |
| Check the API is up | `curl -s localhost:8000/api/health` |
| Apply migrations to the dev database (rebuild the image first if a migration is new) | `docker compose build seed && docker compose run --rm seed` |
| Run the backend unit tests | `uv run --directory backend pytest tests/unit -v` |
| Run the backend integration tests (db running; `DATABASE_URL` set as in `backend/README.md`) | `uv run --directory backend pytest tests/integration -v` |
| Run every test suite in one command (db running and seeded; stops on the first failure) | `scripts/test-all.sh` |
| Lint all Python (the CI lint job) | `uvx ruff@0.17.0 check backend mcp-server agent-hooks ops` |
| Lint the CI workflow | `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:1.7.7 -color` |
| Install frontend dependencies (from `frontend/`) | `npm ci` |
| Regenerate frontend API types from `openapi.yaml` (from `frontend/`) | `npm run gen:api` |
| Frontend type-check, lint, tests, build (from `frontend/`) | `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` |
| View telemetry (Grafana, anonymous viewer; dashboard "Finding-page journey"; `docker compose up -d` starts it) | open `http://127.0.0.1:3000`; see `docs/observability.md` |
| Fire the finding-page alert on purpose (stops `db`, sends failing requests; restore with `docker compose start db`; see `docs/alerting.md`) | `ops/alerting/trigger-db-down.sh` |
| Frontend dev server on `localhost:5173`, proxying `/api` to the API (from `frontend/`) | `npm run dev` |

## Repository layout (target)

```
README.md            product-spec.md      AGENTS.md           CLAUDE.md
openapi.yaml         docker-compose.yml   .env.example
frontend/            backend/             data/snapshot/      content/
.github/workflows/   docs/                security/           ops/
agent-capabilities/  agent-hooks/         mcp-server/         custom-agent/
```

Create a directory only when the task at hand needs it.
