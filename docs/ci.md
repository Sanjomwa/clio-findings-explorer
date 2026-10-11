# Continuous integration

One workflow, `.github/workflows/ci.yml`, runs every test suite and check in the repository. It runs on push to `main`, on every pull request and on manual dispatch. It needs **no secrets**: the Postgres service and the compose stack use the local-only placeholder values from `.env.example` (`clio` / `clio-local-only` / `clio_findings`) on a throwaway runner. There is no deploy job; deployment is Phase 3 (`deploy.yml`).

Settings: `permissions: contents: read`; one concurrency group per ref with `cancel-in-progress`; a `timeout-minutes` on every job. Actions are pinned to a full commit SHA with the version in a comment. Jobs run in parallel and each sets up its own environment (`astral-sh/setup-uv`, Python 3.12, uv cache on).

## Jobs

| Job | Runs | Why | Reproduce locally |
|---|---|---|---|
| `lint` | `uvx ruff@0.17.0 check backend mcp-server agent-hooks ops` | One style and bug-pattern gate for all Python. | same command |
| `contract` | `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml` | `openapi.yaml` is the source of truth; it must be valid OpenAPI 3.1. | same command |
| `hooks-and-ops` | hook tests (`agent-hooks/tests`) and snapshot export tests (`ops/tests`), stdlib unittest, with PyYAML supplied by `uv run --with pyyaml` | The git guard and spec-first guard protect the repo rules; the export tests prove the export refuses synthetic data. | `python3 -m unittest discover -s agent-hooks/tests -v` and `... -s ops/tests -v` |
| `backend-unit` | `pytest tests/unit` with `pytest-cov` | Logic that needs no database. | `uv run --directory backend pytest tests/unit -v` |
| `integration` | Postgres 16 service, `alembic upgrade head`, `python -m app.seed`, backend integration tests, then the MCP server tests (unit and integration) | Real database, real snapshot; every API response is validated against `openapi.yaml`; the MCP `query_snapshot` tool is tested as the read-only `snapshot_reader` role. | start a throwaway Postgres, export `DATABASE_URL`, `FINDINGS_DB_URL`, `SNAPSHOT_DIR`, then run the same commands (see `backend/README.md`) |
| `compose-smoke` | `cp .env.example .env`, `docker compose up -d --build`, wait for `backend` healthy (up to 3 minutes), then check `/api/health` (`snapshot_version` equals the snapshot manifest's `version`) and that `/api/timeline` has 1523 weeks; logs on failure; `docker compose down -v` at the end | The stack as a user starts it actually works. | the same steps against your running stack. Never run `down -v` locally: it deletes your database volume. In CI the runner is throwaway, so it is right there. |

## Things worth knowing

- **Coverage is reported, not enforced.** `backend-unit` and `integration` print a `pytest-cov` table; nothing fails on a threshold.
- **The contract test is the openapi-core response validation.** The backend integration tests validate every response against `openapi.yaml` with `openapi-core`, which satisfies the plan's "Schemathesis, else a hand-written contract test" rule. Schemathesis is deferred to Phase 3 hardening, if time allows.
- **MCP integration tests must not skip.** They skip silently when the database is unreachable, which would look green. The MCP step runs `pytest -v -rs`, tees the output, and fails if it contains `SKIPPED`. (Checked locally: pointing `FINDINGS_DB_URL` at a dead port produces 9 `SKIPPED` lines.)
- **Lint decision (Phase 1d).** Only `backend/` had a ruff config; the other directories were linted with ruff's own, much wider, defaults. A root `ruff.toml` now gives all four directories the backend's selection (`E, F, I, UP, B`), line length 100 and `py312`; `backend/pyproject.toml`'s `[tool.ruff]` is kept (it is now duplicated, and takes precedence for `backend/`). CI pins ruff to 0.17.0, the version in `backend/uv.lock`. `ruff check --fix` (safe fixes only) was applied to `ops/`. The remaining 21 findings were more than 15, so they are per-file ignores in `ruff.toml`, each with a comment: E501 in `agent-hooks/*.py` and `ops/*.py`, B904 in `agent-hooks/spec_first_guard.py` (fail-closed hook), B905 in the two `ops` files that use `zip()`.
- **Workflow lint.** `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:1.7.7 -color`. The first real run on GitHub happens after the first push.
