# CLIO Findings Explorer: product spec

**Version:** 0.3 (2026-10-05, revised after a read-only check of CLIO's data: findings re-selected, success criteria added). Written before any code. The full plan, schedule and rubric mapping are in the Cowork-side project plan; this file is the product definition the code is built against.

## 1. Problem

When a government restricts civil liberties, the evidence arrives in pieces that don't line up. Conflict-event records (ACLED) describe what happened on the street. Network measurements (OONI) describe what happened to internet access. Platform transparency reports (Google) describe what content governments asked to have removed. Each has a different grain, collection method and reliability.

Someone who wants to answer "was there coordinated civil-liberties pressure in Kenya during the Finance Bill 2024 protests, and how sure can we be?" has two bad options today: correlate three raw datasets by hand, or read an advocacy summary with no traceable evidence under it.

## 2. What the product is

A public, read-only web app that presents a small set of curated findings about Kenya. Each finding is one specific week that CLIO's regime-classification engine has classified, shown with:

- the regime state (STABLE, MOBILISATION, ESCALATION, CONFLICT or CRISIS) and a confidence band
- a plain-language summary
- one evidence card per source (ACLED, OONI, Google Transparency), each served by its own API endpoint; a source with no data for that week says so
- a limitations box that cannot be dismissed, stating what the evidence does not establish

Every number on screen comes from a versioned snapshot of CLIO output that is committed to this repository. The app never queries CLIO or BigQuery at runtime.

## 3. Who it is for

- **Researchers, journalists and digital-rights practitioners** who need a traceable answer about a specific episode and want to see the evidence behind it.
- **Course peer reviewers**, who need to run the whole system with one command and no credentials.

## 4. Expected behaviour

1. A visitor lands on a **timeline** of classified weeks for Kenya, 1,523 weeks from 1997-01-11 to 2026-03-14. Weeks are coloured by regime state. Weeks that have a curated finding are highlighted.
2. Clicking a highlighted week opens the **finding** page: title, state and confidence badges, summary, the limitations box, then three evidence cards that load independently.
3. Each **evidence card** shows one headline number, the supporting detail for that source, the period the numbers cover, and a provenance note. Sources do not all report weekly: where a source reports per half-year, the card shows that longer period and says so. If a source has no data for the window (for example, the week predates the source), the card is still shown and says so plainly. The API returns it with `has_data: false`; 404 means only that the finding does not exist.
4. A **findings list** shows all curated findings with a one-line teaser each.
5. A **methodology** page explains the regime states, the confidence bands, each source's limits, and the snapshot version and export date.
6. Every page shows the snapshot version and date. The product is an archive of curated findings, and it says so. It is not a live monitor.

## 5. Content

Three findings are committed and a fourth is being selected. The choices below follow a read-only check of CLIO's Kenya output on 2026-10-05; several differ from the original plan because the data did not support what the plan assumed.

| Slug | Anchor week | What it shows | Sources with data |
|---|---|---|---|
| `finance-bill-2024` | 2024-06-22 (22 to 28 June) | A CRISIS classification with HIGH confidence in the week Parliament was stormed. The flagship. | ACLED, OONI, Google Transparency |
| `general-election-2022` | 2022-08-06 | A CRISIS classification with HIGH confidence in election week, driven by violence and suppression while protest stayed normal. What drove it is checked before the finding is written. | ACLED, Google Transparency |
| `post-election-violence-2008` | 2008-01-19 | A limits case. The classifier read INSUFFICIENT_DATA until this week and never reached CRISIS, so it shows what sparse early data cannot support. | ACLED |
| (fourth, to be selected) | a week between 2023-05-27 and 2025-06-28 | Chosen from the weeks where all three sources have data. | ACLED, OONI, Google Transparency |

CLIO's weeks start on Saturday. Each finding is anchored to one `week_start_date`; a finding about a longer episode describes the rest in its summary.

Dropped from the plan: the 2010 constitutional referendum as a "true negative". Those weeks read STABLE with INSUFFICIENT_DATA and every band UNKNOWN, which is an absence of evidence and is not presented as a correct quiet reading.

**How the sources relate.** The classification is computed from ACLED data, so the ACLED card shows the classifier's own input and is labelled that way. Only OONI and Google Transparency are independent of the classification. The product never describes the three cards as three independent confirmations.

**Coverage is uneven and the product says so.** OONI weekly signals exist only from 2023-05-27 to 2025-06-28. Google Transparency data is half-yearly from 2012, with gaps. Of Kenya's 1,523 classified weeks (1997-01-11 to 2026-03-14), 976 carry INSUFFICIENT_DATA confidence. The classifier's thresholds are labelled provisional in CLIO's own code, and the methodology page states that.

## 6. Data

- **Source:** a one-time, human-run export of CLIO's materialized BigQuery output to `data/snapshot/`, with a `MANIFEST.json` recording, for every file, the source table, the exact SQL, the row count and the export time.
- **Synthetic data is excluded.** The export refuses any source table that carries a synthetic flag column at all (a column whose name ends in `is_synthetic`), whatever its values. CLIO's Lumen-derived signal and its composite pressure score are not exported, stored or served.
- **Storage:** PostgreSQL, five tables: `regime_weeks`, `findings`, `finding_evidence`, `finding_caveats`, `snapshot_meta`.
- **Curated content** is separate from the snapshot. Titles, summaries, caveats, definitions and source notes are written by a person, live in `content/`, and are loaded by the same seed step. `data/snapshot/` holds only what CLIO exported.
- **The manifest** records the exact SQL and export time for every file, and the API serves both, so any number can be traced to the query that produced it. It also records a synthetic-data audit: the source tables checked for synthetic flag columns and the result. The export fails if any source table has one.
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

1. It does not reproduce CLIO's dashboard. A handful of curated findings and a timeline; nothing more.
2. It does not touch CLIO's live pipeline or BigQuery after the one export.
3. It does not present synthetic or placeholder data as real.
4. It does not accept writes. No accounts, no auth, no comments, no admin.
5. It does not claim real-time monitoring.
6. It does not assert causation or targeting. A conflict-event spike and a network anomaly in the same week are a correlation. Every finding's limitations box says so.
7. It does not claim institutional backing. It is one person's course project built on one person's data pipeline.

## 9. Success criteria

The project succeeds if it does three things CLIO's own README says CLIO cannot do yet: run for an outsider with no credentials, expose curated output through an API, and trace every displayed number back to its source query. Each criterion below has a check that can be run.

### 9.1 It runs and ships

- `cp .env.example .env && docker compose up --build` brings up the whole app at `http://localhost:8080` from a clean clone on a machine with only Docker installed. Checked by doing exactly that before submission.
- The timeline renders from `/api/timeline`; a highlighted week opens its finding; every evidence card loads, including cards that report no data.
- The backend's responses conform to `openapi.yaml`, checked in CI.
- Unit and integration tests are separate, documented, and run in CI; integration tests use a real Postgres loaded with the real snapshot.
- A push to `main` deploys only after CI passes, and the public URL serves the same snapshot version as the repository.

### 9.2 Evidence integrity

- **Traceability.** Every number on a finding page equals a value in `data/snapshot/`, checked by an automated test, and the page shows the query that produced it.
- **No unsupported claims.** Every factual sentence in a finding has a logged reviewer verdict. None is published with an UNSUPPORTED verdict.
- **Limits are visible.** Every finding has at least one caveat, enforced in the database and the API. A source with no data returns a card that says so. Weeks with INSUFFICIENT_DATA confidence look different on the timeline from confident STABLE weeks.
- **No causal language.** An automated check over the curated content rejects wording that asserts causation or targeting.
- **Independence is stated correctly.** The ACLED card is labelled as the classifier's input. No text calls the three cards independent confirmations.
- **At least one finding shows a limit of the method.** The 2008 finding does this.
- **Attribution.** Every card carries its source's required citation details, and the repository states the data's licence terms separately from the MIT licence on the code.
- **No synthetic data.** The export refuses any source table that carries a synthetic flag column, proven by a test.

### 9.3 A reader can use it

- Someone unfamiliar with CLIO, landing on a finding page, can within two minutes state the classification, the confidence, one thing the evidence does not show, and how to cite the finding.
- Checked with two or three people in the final week, five minutes each, results recorded in `docs/`.

### 9.4 It gives something back to CLIO

- A short note in `docs/` lists what transfers to CLIO's roadmap: the API contract shape, the manifest format and the traceability test.
- Nothing in CLIO's repository or pipeline is changed by this project.

### 9.5 Course outcome

- Submitted by the evening of 26 October 2026 with a commit ID, and the required peer reviews completed.
- A self-score against the 14 rubric criteria at the end of each build phase, with 26 of 30 as the floor.

### 9.6 What does not count as success

Traffic, the number of findings, the number of features, or parity with CLIO's dashboard. Three honest findings are better than four with one overclaimed.
