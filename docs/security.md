# Security: defence in depth

CLIO Findings Explorer is a public, read-only site. This page lists each security layer, what it stops, and where the evidence is: a file, a test or a live check. It does not claim the site is "secure"; it says what each layer stops and what it does not. To report a vulnerability, see [SECURITY.md](../SECURITY.md).

## What there is to protect

The site holds no user accounts, no personal data and no payments. What matters is:

1. **Integrity of the evidence.** A finding page must show exactly what the committed snapshot and the reviewed content say. Tampered numbers would do more harm than downtime.
2. **Availability**, within a small free-tier budget.
3. **Cost.** A traffic spike or a mistake must not run up a bill.
4. **The repository and its pipeline.** AI agents work in the repository, and a deploy can reach production.

## The layers

### Data and API

| Layer | What it stops | Where it lives and how it is proven |
|---|---|---|
| Strict input validation | Injection payloads reaching a query: slugs must match `^[a-z0-9]+(-[a-z0-9]+)*$` (at most 80 characters), countries are two capital letters, dates are typed | `backend/app/routers/common.py` (slug), `backend/app/routers/timeline.py` (country, dates). Integration tests send `' OR 1=1--`, `; DROP TABLE findings;--`, `%27` and 5,000-character strings to every parameter: 422 or 404, never 500, row counts unchanged (`backend/tests/integration/test_api.py`) |
| Trimmed validation errors (#36) | Rejected input echoed back in a response | A 422 body is `{"detail": [{"loc", "msg", "type"}]}`, with no `input` or `ctx` (`backend/app/main.py`, `openapi.yaml` `ValidationError`); tested, and checked by the smoke test after every deploy ([ci-cd.md](ci-cd.md#what-the-smoke-test-checks)) |
| Bound parameters only | SQL built from strings | SQLAlchemy `select(...)`; ruff rule `S608` (string-built SQL) is on for all Python in `ruff.toml` and the `lint` job fails on it ([ci.md](ci.md)). The exceptions are the export script's SQL built from constant column tuples (per-line `noqa`) and one seed test (per-file ignore) |
| Read-only transactions | Writes through the API, even if a query were subverted | Every request runs `SET TRANSACTION READ ONLY` (`backend/app/deps.py`; the health route does the same in `backend/app/routers/health.py`) |
| Read-only database login (#35) | Writes and DDL at the connection level, independent of the code | The deployed backends connect as `cfe_api_reader`, which only inherits `snapshot_reader` (`SELECT` on public tables). `backend/tests/integration/test_reader_login.py` proves every route answers the same as for the owner and that INSERT, UPDATE, DELETE and CREATE TABLE are refused. Checked live on dev and production with `pg_stat_activity` ([deploy.md](deploy.md#check-the-backend-uses-the-read-only-login)) |
| Owner credentials only where writing is needed | A leaked API credential becoming a write credential | Seed and migration jobs keep the owner URL; the backend never sees it (`.github/workflows/deploy.yml`, [deploy.md](deploy.md)) |
| Snapshot integrity | Altered or synthetic data entering the database | The seed checks each file's sha256 and line count against `MANIFEST.json` and refuses a snapshot directory with unlisted files (`backend/app/seed/snapshot.py`). The export, which only Sam runs, refuses any source table with a column ending in `is_synthetic`, whatever its values (`ops/export_snapshot.py`, tested in `ops/tests/test_export_snapshot.py`), and the manifest records that audit |
| Evidence traceability | A number on a page drifting from the data | `backend/tests/integration/test_traceability.py` recomputes every evidence-card number from the snapshot files |
| Contract validation | Responses leaking fields or changing shape | Every response is validated against `openapi.yaml` with openapi-core in the integration tests (`backend/tests/integration/test_api.py`) |
| MCP query tool guards | An agent's ad-hoc query writing, or reading server files | One statement, parsed with `sqlglot` and accepted only as a `SELECT`; run read-only with a 5 s statement timeout, a 200-row cap and `SET LOCAL ROLE snapshot_reader` (`mcp-server/README.md`, `mcp-server/snapshot_query.py`) |

### Browser and edge

| Layer | What it stops | Where it lives and how it is proven |
|---|---|---|
| Browser security headers (#36) | Script injection, clickjacking, MIME sniffing, referrer leaks, unused browser features | `frontend/nginx/security-headers.conf`, on every response (`always`, and included in every location): a strict `Content-Security-Policy` (`default-src 'self'`, the one inline theme script allowed by its sha256 hash, `object-src 'none'`, `base-uri 'none'`, `form-action 'self'`, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. `ops/tests/test_security_headers.py` fails CI if the inline script changes without its hash; the smoke test checks headers after every deploy. On 8 Nov every route was loaded in a browser on dev and production, in both themes: 0 CSP violations |
| API rate limit (#36) | A flood making the site slow or tripping the spend cap | nginx: one global bucket for `/api/`, 30 requests/s with a burst of 60, `429` beyond that (`frontend/nginx/default.conf.template`, [frontend/README.md](../frontend/README.md)). A page load makes at most 6 API calls. Rejections are not logged, because nginx would write the client address with them |
| HTTPS only | Plain-HTTP downgrade | The whole `.app` top-level domain is on browsers' HSTS preload list, so `*.run.app` is HTTPS-only. The nginx config sets no `Strict-Transport-Security` header, and a test checks that |
| Privacy in logs and telemetry | Collecting visitors' data | The nginx access log has no client IP and no query string; the backend's logs, traces and metrics are scrubbed of client addresses, user agents, query strings and database URLs, tested ([observability.md](observability.md)). Cloud Run's own platform logs still record caller addresses, which cannot be switched off |

### Pipeline and repository

| Layer | What it stops | Where it lives and how it is proven |
|---|---|---|
| Required checks on `main` | An unreviewed or red change reaching `main` | Ruleset "Protect main": pull request required; 11 required checks (8 CI jobs, 3 CodeQL scans); deletions and force pushes blocked; no bypass list; 0 approvals, so the checks are the gate ([ci-cd.md](ci-cd.md#gates)) |
| Code scanning (#34) | Known vulnerability patterns in Python, TypeScript and the workflows | CodeQL on every pull request, on `main` and weekly; the check fails at High or higher (a repository setting, [ci.md](ci.md#codeql)) |
| Dependency checks | Known-vulnerable libraries | `pip-audit` (hash-locked) and `npm audit --audit-level=high` fail CI; Dependabot alerts on (0 open on 9 Nov), security updates off by choice; weekly Dependabot version updates, majors by hand ([ci.md](ci.md#dependabot)) |
| Secret scanning | A credential committed by mistake | GitHub secret scanning with push protection |
| Pinned, minimal CI | A compromised action tag, over-broad tokens | Every action pinned to a full commit SHA; `contents: read` by default ([ci-cd.md](ci-cd.md#supply-chain)) |
| Keyless deploys | Long-lived cloud keys leaking | Workload Identity Federation, restricted to this repository; no key files; database URLs only in Secret Manager ([deploy.md](deploy.md)) |
| Gated production | An unreviewed change reaching production | Dev deploys only after green CI on `main`; production needs Sam's approval, deploys images dev already ran, by full SHA, and never rebuilds ([ci-cd.md](ci-cd.md)) |
| Agent guardrails (#29, #38) | An AI agent committing, pushing, merging or changing the API off-spec | Two layers for git and `gh` writes: the `block-autonomous-git` hook (fails closed, including on any shell expansion where the subcommand or program belongs) and Claude Code `permissions.deny` rules in `.claude/settings.json`. `spec-first-guard` blocks routes not in `openapi.yaml`. The evidence reviewer is read-only by tool allow-list ([permissions.md](permissions.md), [agent-hooks/README.md](../agent-hooks/README.md)) |
| On-call agent limits | An automated responder doing damage or burning model budget | Service actions only, read-only tools, at most 2 model calls per incident, hourly and daily call budgets, a cooldown, a `PAUSE` kill switch, escalation to a GitHub issue ([on-call.md](on-call.md)) |
| Cost caps | A spike or mistake running up a bill | Cloud Run max 1 instance per service (`--max-instances 1` in `.github/workflows/deploy.yml`); a 4 USD/month spend cap on Cloud Run and a 5 USD alert budget (set in Google Cloud, not in this repository); the Neon free plan cannot bill; Artifact Registry keeps the 10 newest versions of each image (`ops/deploy/gcp-setup.sh`) |

## Live checks

- **8 Nov 2026, dev and production:** `pg_stat_activity` shows the backend connected as `cfe_api_reader`.
- **8 Nov 2026, dev and production after #36:** all six security headers on pages and `/api/`; the inline script's hash matches the CSP; 18 page views per environment (9 routes, both themes) with 0 CSP violations.
- **9 Nov 2026, production:** `/api/findings/' OR 1=1--` returns 422 with only `loc`, `msg` and `type` (no echo of the input); an unknown slug returns 404; health is `ok`; no 500 and no stack trace. The `Server` header shows only `Google Frontend`.
- **9 Nov 2026, git guard after #38:** 27 bypass forms blocked (for example `git $'commit'`, `git $X`, `git $(echo commit)`, `G=git; $G commit`) and 28 everyday commands still allowed.

## Known gaps

1. **The backend URL is public as well as the frontend.** By design (a read-only API), but a direct call to the backend skips everything at the nginx layer: the security headers do not matter there (JSON, no pages), but the **rate limit does not apply**. The instance cap and the spend cap still bound cost. Planned next: make the backend reachable only through the frontend.
2. **The rate limit is global, not per client.** One heavy client can use the whole bucket, and a flood makes the API answer 429 to everyone while it lasts. A per-client limit needs a client address the client cannot forge, and that has not been shown for Cloud Run.
3. **Agent guardrails are text checks.** Neither layer sees commands run by another interpreter (`bash -c`, `eval`), inside scripts, through git aliases or from a substitution in the program slot (`$(which git) commit`). AGENTS.md hard rule 1 holds whether or not a layer catches a command; Sam alone commits, pushes and merges.
4. **Not done:** a penetration test, CSP violation reporting, and uptime alerting on a stopped backend (see the README's Limitations).

## What this does not claim

These layers reduce specific risks; they do not make the site "secure" in general. The strongest guarantees are the ones that do not depend on code being correct: the read-only login, the read-only transaction, the gated production deploy and the spend cap.
