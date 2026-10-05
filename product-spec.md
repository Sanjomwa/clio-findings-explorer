# CLIO Findings Explorer: product spec

**Version:** 0.2 (2026-10-05, revised after the first agent review). Written before any code. The full plan, schedule and rubric mapping are in the Cowork-side project plan; this file is the product definition the code is built against.

## 1. Problem

When a government restricts civil liberties, the evidence arrives in pieces that don't line up. Conflict-event records (ACLED) describe what happened on the street. Network measurements (OONI) describe what happened to internet access. Platform transparency reports (Google) describe what content governments asked to have removed. Each has a different grain, collection method and reliability.

Someone who wants to answer "was there coordinated civil-liberties pressure in Kenya during the Finance Bill 2024 protests, and how sure can we be?" has two bad options today: correlate three raw datasets by hand, or read an advocacy summary with no traceable evidence under it.

## 2. What the product is

A public, read-only web app that presents a small set of curated findings about Kenya. Each finding is one specific week that CLIO's regime-classification engine has classified, shown with:

- the regime state (STABLE, MOBILISATION, ESCALATION or CRISIS) and a confidence band
- a plain-language summary
- three evidence cards, one per source, each served by its own API endpoint
- a limitations box that cannot be dismissed, stating what the evidence does not establish

Every number on screen comes from a versioned snapshot of CLIO output that is committed to this repository. The app never queries CLIO or BigQuery at runtime.

## 3. Who it is for

- **Researchers, journalists and digital-rights practitioners** who need a traceable answer about a specific episode and want to see the evidence behind it.
- **Course peer reviewers**, who need to run the whole system with one command and no credentials.

## 4. Expected behaviour

1. A visitor lands on a **timeline** of classified weeks for Kenya (the plan expects 1997 to 2026; the real range is read from the snapshot and stated here once confirmed). Weeks are coloured by regime state. Weeks that have a curated finding are highlighted.
2. Clicking a highlighted week opens the **finding** page: title, state and confidence badges, summary, the limitations box, then three evidence cards that load independently.
3. Each **evidence card** shows one headline number, the supporting detail for that source, the period the numbers cover, and a provenance note. Sources do not all report weekly: where a source reports per half-year, the card shows that longer period and says so. If a source has no data for the window (for example, the week predates the source), the card is still shown and says so plainly. The API returns it with `has_data: false`; 404 means only that the finding does not exist.
4. A **findings list** shows all curated findings with a one-line teaser each.
5. A **methodology** page explains the regime states, the confidence bands, each source's limits, and the snapshot version and export date.
6. Every page shows the snapshot version and date. The product is an archive of curated findings, and it says so. It is not a live monitor.

## 5. Content

Four findings are targeted; three is the floor if the schedule slips. The README and this spec will state the real number.

| Slug | Week | What it shows |
|---|---|---|
| `finance-bill-2024` | week of 2024-06-22 | A CRISIS transition in the week Parliament was stormed. The flagship. |
| `post-election-violence-2008` | Jan to Feb 2008 | Detection of Kenya's most severe modern episode. |
| `general-election-2022` | Aug 2022 | A contested outcome where the classification stayed bounded. |
| `constitutional-referendum-2010` | 2010 | A true negative: a high-salience national vote classified STABLE. |

The dates and classifications above are the plan's expectations, and three of the four are not yet a single week. Each finding will be pinned to one `week_start_date` once the snapshot is exported and CLIO's week-start day is known. A finding about a longer episode names the one week it is anchored to and describes the rest in its summary.

## 6. Data

- **Source:** a one-time, human-run export of CLIO's materialized BigQuery output to `data/snapshot/`, with a `MANIFEST.json` recording, for every file, the source table, the exact SQL, the row count and the export time.
- **Synthetic data is excluded.** The export fails if any column flagged synthetic would be included. CLIO's Lumen-derived signal and its composite pressure score are not exported, stored or served.
- **Storage:** PostgreSQL, five tables: `regime_weeks`, `findings`, `finding_evidence`, `finding_caveats`, `snapshot_meta`.
- **Curated content** is separate from the snapshot. Titles, summaries, caveats, definitions and source notes are written by a person, live in `content/`, and are loaded by the same seed step. `data/snapshot/` holds only what CLIO exported.
- **The manifest** records the exact SQL and export time for every file, and the API serves both, so any number can be traced to the query that produced it. It also records a synthetic-data audit listing any column whose `*_is_synthetic` flag was true in any row; the export fails if such a column would be included.
- **A finding with no caveat cannot exist.** This is enforced in the database and in the API models.

## 7. System

| Part | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| API contract | `openapi.yaml` (OpenAPI 3.1), hand-authored, edited before the code that depends on it |
| Database | PostgreSQL 16 |
| Frontend | React 18, TypeScript, Vite; all HTTP through `frontend/src/api/client.ts`; types generated from `openapi.yaml` |
| Run | Docker Compose: `db`, `seed`, `backend`, `frontend`. One command, no credentials |
| CI/CD | GitHub Actions: tests, then deploy only when tests pass |
| Deployment | Google Cloud Run (backend, frontend) and Neon Postgres |

The API has eight read-only endpoints under `/api`: health, timeline, findings list, finding detail, three evidence endpoints, and methodology. `openapi.yaml` is the authority on their shape.

## 8. Non-goals

1. It does not reproduce CLIO's dashboard. Four findings and a timeline; nothing more.
2. It does not touch CLIO's live pipeline or BigQuery after the one export.
3. It does not present synthetic or placeholder data as real.
4. It does not accept writes. No accounts, no auth, no comments, no admin.
5. It does not claim real-time monitoring.
6. It does not assert causation or targeting. A conflict-event spike and a network anomaly in the same week are a correlation. Every finding's limitations box says so.
7. It does not claim institutional backing. It is one person's course project built on one person's data pipeline.

## 9. Acceptance criteria

- `cp .env.example .env && docker compose up --build` brings up the whole app at `http://localhost:8080` on a machine with only Docker installed.
- The timeline renders from `/api/timeline`; a highlighted week opens its finding; all three evidence cards load.
- Every finding page shows a non-empty limitations box and the snapshot version.
- Every number shown can be traced to a row in `data/snapshot/` through the manifest.
- The backend's responses conform to `openapi.yaml`, checked in CI.
- Unit and integration tests are separate, documented, and run in CI; integration tests use a real Postgres with the real snapshot.
- A push to `main` deploys only after CI passes, and the public URL serves the same snapshot version as the repository.
