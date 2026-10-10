# backend

The Postgres 16 schema (SQLAlchemy 2.0 models, Alembic migrations), the seed step that loads
`data/snapshot/` and, when it exists, `content/`, and the read-only FastAPI app that serves the eight
`/api` operations of `openapi.yaml` (v0.4.1).

## Layout

```
pyproject.toml  uv.lock  .python-version  Dockerfile  alembic.ini
alembic/versions/0001_initial_schema.py   the schema of record, including the caveat trigger
app/db/        base.py, models.py (typed models mirroring the migration), session.py
app/main.py    create_app(); routers carry full literal paths (no include_router prefix)
app/routers/   health, timeline, findings, evidence, methodology (+ common helpers)
app/schemas.py Pydantic v2 response models mirroring the contract's schemas
app/evidence/  acled.py, ooni.py, google.py: pure functions, rows in, card dict out; service.py fetches rows
app/deps.py    read-only session per request (SET TRANSACTION READ ONLY), snapshot metadata
app/seed/      snapshot.py (verify, cast, load), content.py (YAML validation, sync), __main__.py
tests/unit/         no database
tests/integration/  needs the compose db service
tests/fixtures/     tiny snapshot and one content file; the real data/snapshot/ is never modified
```

`DATABASE_URL` (`postgresql+psycopg://...`) comes from the environment; no credentials are in code.

## Schema notes

- Snapshot tables have the same names and columns as the NDJSON files; natural keys are the primary keys.
- Regime and band enums are `CHECK` constraints (not Postgres ENUM types), so they are easy to change.
- `snapshot_meta` holds exactly one row (unique index on a constant). `snapshot_tables` has one row per manifest table.
- "A finding with no caveat cannot exist" is a `DEFERRABLE INITIALLY DEFERRED` constraint trigger, checked at commit.
- `findings` -> `regime_weeks` is a composite FK declared `DEFERRABLE INITIALLY DEFERRED` so the seed can
  reload snapshot rows in one transaction; the seed checks first and fails with a clear message if a reload
  would orphan a finding.

## Run

From the repo root, with `.env` copied from `.env.example`:

```bash
docker compose up -d db                  # Postgres on 127.0.0.1:55432
docker compose run --rm seed             # alembic upgrade head, then python -m app.seed, then exit
docker compose -f docker-compose.yml -f docker-compose.content.yml run --rm seed   # once content/ exists
```

Seed behaviour: verifies every manifest file (sha256, line count, no unlisted files) before touching the
database, then loads in one transaction. A second run prints `snapshot already loaded`. Without `content/`
it prints `no content/ directory: 0 findings`. Content files in `content/findings/<slug>.yaml` are validated
strictly (see `app/seed/content.py`).

## Run the API

In compose (db, then seed, then backend; API on `127.0.0.1:8000`):

```bash
docker compose up -d --build
curl -s localhost:8000/api/health
```

Locally (db running and seeded, `DATABASE_URL` set as below):

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

`CONTENT_DIR` (default `<repo>/content`) is read for `methodology.yaml`
(`regime_states`, `confidence_levels`, `family_bands`: lists of `{state|level|band, definition}`).
If the file is absent those arrays are empty; definitions are never invented. Evidence cards are computed
per request from the snapshot tables, as each evidence operation's description in `openapi.yaml` states.
Error bodies: 404 `{"detail": "..."}` for an unknown slug, FastAPI's default body for 422, and `/api/health`
returns 503 with the `Health` body when the database is unreachable or no snapshot is loaded; the other
seven operations return 503 with `{"detail": "..."}` when no snapshot is loaded.

## Migrations and seed from the host

```bash
cd backend
set -a; . ../.env; set +a
export DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:55432/$POSTGRES_DB"
uv run alembic upgrade head
uv run python -m app.seed               # SNAPSHOT_DIR / CONTENT_DIR override the default paths
uv run alembic downgrade base
```

## Tests

```bash
cd backend
uv run pytest tests/unit -v                                   # no database
# integration: needs `docker compose up -d db` and DATABASE_URL as above
uv run pytest tests/integration -v
```

Integration tests create and drop a separate database, `clio_findings_test`, on the same server, so the
seeded dev database is not touched. `tests/integration/test_api.py` seeds the real snapshot plus the
test-only findings in `tests/fixtures/content_evidence/` and validates every response (200, 404, 422, 503)
against `openapi.yaml` with `openapi-core`. Unit tests for the evidence functions are in
`tests/unit/test_evidence.py`. `uv run ruff check .` runs the linter.
