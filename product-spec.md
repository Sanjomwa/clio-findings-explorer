# CLIO Findings Explorer: product spec

**Version:** 0.5 (2026-10-17: environments, observability, alerting and the on-call agent added, and §9 rewritten, after the course rubric was revised on 16 October). Earlier: 0.4 (2026-10-10, after snapshot 2026-10-10.1: five anchor weeks set, display rules for classifications added). Written before any code. The full plan, schedule and rubric mapping are in the Cowork-side project plan; this file is the product definition the code is built against.

## 1. Problem

When a government restricts civil liberties, the evidence arrives in pieces that don't line up. Conflict-event records (ACLED) describe what happened on the street. Network measurements (OONI) describe what happened to internet access. Platform transparency reports (Google) describe what content governments asked to have removed. Each has a different grain, collection method and reliability.

Someone who wants to answer "was there coordinated civil-liberties pressure in Kenya during the Finance Bill 2024 protests, and how sure can we be?" has two bad options today: correlate three raw datasets by hand, or read an advocacy summary with no traceable evidence under it.

## 2. What the product is

A public, read-only web app that presents a small set of curated findings about Kenya. Each finding is one specific week that CLIO's regime-classification engine has classified, shown with:

- the regime state and the confidence level. CLIO defines seven states (STABLE, MOBILISATION, CONTESTATION, ESCALATION, CRISIS, REPRESSION, CONFLICT); five occur in the Kenya snapshot.
- a plain-language summary
- one evidence card per source (ACLED, OONI, Google Transparency), each served by its own API endpoint; a source with no data for that week says so
- a limitations box that cannot be dismissed, stating what the evidence does not establish

Every number on screen comes from a versioned snapshot of CLIO output that is committed to this repository. The app never queries CLIO or BigQuery at runtime.

## 3. Who it is for

- **Researchers, journalists and digital-rights practitioners** who need a traceable answer about a specific episode and want to see the evidence behind it.
- **Course peer reviewers**, who need to run the whole system with one command and no credentials.

## 4. Expected behaviour

1. A visitor lands on a **timeline** of classified weeks for Kenya, 1,523 weeks from 1997-01-11 to 2026-03-14, drawn as a ledger: one row per year, one cell per week. Weeks are coloured by regime state, and weeks with INSUFFICIENT_DATA confidence are pale. Weeks that have a curated finding are outlined and named beside the ledger. Hovering a week shows its dates, state and confidence; the bands are shown on the finding page.
2. Clicking a highlighted week opens the **finding** page: a record header (week dates, snapshot version, the finding's position), the state and confidence labels, the title, the teaser as a short lead with an optional key phrase highlighted, the summary with the limitations box beside it, then three evidence cards that load independently. The key phrase is an exact substring of the teaser, so it adds no claim of its own. The finding page also shows the week's three family bands (protest, violence, suppression), shown as they are. It also lists the public sources for the finding's real-world event statements; these are separate from the data-source attribution on the evidence cards.
3. Each **evidence card** shows one headline number, the supporting detail for that source, the period the numbers cover, and a provenance note. Sources do not all report weekly: where a source reports per half-year, the card shows that longer period and says so. If a source has no data for the window (for example, the week predates the source), the card is still shown and says so plainly. The API returns it with `has_data: false`; 404 means only that the finding does not exist.
4. A **findings list** shows all curated findings with a one-line teaser each.
5. A **methodology** page explains how CLIO classifies a week: what each pressure family counts (including that suppression is offline events and not internet restrictions), the regime states, the confidence levels and the family bands. It says the definitions come from CLIO's production code and links to it.
6. An **about** page says what the project is and why it exists, how a finding is made (the fixed snapshot, the drafted week, the claim-by-claim review, publication with its limits), and describes the three sources: what each measures, its coverage in the snapshot, and its terms of use. It also says what the project is not.
7. Every page shows the snapshot version and date. The product is an archive of curated findings, and it says so. It is not a live monitor.
8. The site has a light and a dark theme. A first visit follows the device setting; after that the reader's choice is kept.

### 4.1 How classifications are described

CLIO's reason codes are not shown as descriptions of the bands. In particular, `STABLE:ALL_NORMAL` means only that the week was STABLE with usable data; its bands can still be raised. The app shows the bands themselves and uses this wording:

- STABLE weeks with usable data: "STABLE: no regime rule was met this week. Bands can still be raised; a first raised week is held at STABLE until a second consecutive one follows."
- Weeks with a pre-transition flag, added to the above: "Raised: would have entered <TARGET> if the next week also qualified."
- STABLE weeks with INSUFFICIENT_DATA confidence: "STABLE (insufficient data)".
- No STABLE week is described as "all signals normal".

### 4.2 What each evidence card leads with

**ACLED.** The card leads with the number of conflict events recorded in the anchor week, all event types, set against the median of the 12 weeks before. It covers the anchor week (Saturday to Friday). It has no data only if the snapshot has no row for that week. ACLED is the classifier's own input, so the card says it is not independent corroboration.

**OONI.** The card leads with the anomalous measurement rate of the one test whose anomaly rate has the highest z-score against its own 12-week baseline that week, and shows that z-score. Ties go to the test name that comes first alphabetically. If no test has a baseline, the card shows no number and says so. It covers the anchor week, and has no data when the week has no OONI rows; OONI weekly signals cover only 2023-05-27 to 2025-06-28. The card never calls a value normal or significant. It carries a fixed note: these tests check whether specific apps and sites can be reached from testers' networks.

**Google Transparency.** The card leads with the total removal requests in Google's government-requests report for Kenya for the half-year that contains the anchor week (January to June, or July to December), with no comparison figure. The period is half a year, not a week, and the card says so. It has no data when the snapshot has no rows for that half-year. It then says the snapshot has no rows for that period, never that there were zero requests; for periods before July 2012 it adds that the snapshot's Google data begins with July to December 2012.

## 5. Content

Five anchor weeks are set. Three findings is the floor if the schedule slips; the README states the real number. The choices below follow a read-only check of CLIO's Kenya output on 2026-10-05 and the exported snapshot 2026-10-10.1; several differ from the original plan because the data did not support what the plan assumed.

| Slug | Anchor week | What it shows | Sources with data |
|---|---|---|---|
| `finance-bill-2024` | 2024-06-22 (22 to 28 June) | A CRISIS classification with HIGH confidence in the week Parliament was stormed. The flagship. | ACLED, OONI, Google Transparency |
| `general-election-2022` | 2022-08-06 | A CRISIS classification with HIGH confidence in election week, driven by violence and suppression while protest stayed normal. What drove it is checked before the finding is written. | ACLED, Google Transparency |
| `post-election-violence-2008` | 2008-01-19 | A limits case. The classifier read STABLE (insufficient data) until this week, including the busiest ACLED week of the period, because one family's baseline was too thin to score, and in CLIO's current code that withholds all three scores. It never reached CRISIS. | ACLED |
| `july-2023` (working slug) | 2023-07-15 | A CRISIS classification with HIGH confidence, with all three sources holding data. The event behind it is confirmed before the finding is written. | ACLED, OONI, Google Transparency |
| `june-july-2025` (working slug) | 2025-06-21 | A second limits case. The classifier read STABLE with HIGH confidence in a week of 115 events and 43 fatalities, and again on 2025-07-05 (141 events, 62 fatalities). It shows a pattern of pressure that CLIO's current rules do not classify. | ACLED, OONI, Google Transparency |

**Approved notes for weeks next to anchors**, for use in Phase 2 content:

- 2024-06-15: "Protest raised and suppression severe; held at STABLE as a first qualifying week. The next week was classified CRISIS."
- 2023-07-08: "Protest severe and suppression raised; held at STABLE as a first qualifying week before 2023-07-15."
- 2025-07-05: "Suppression severe; held at STABLE because the week before did not qualify, and the week after returned to normal, so REPRESSION was never assigned."

A further caveat for the 2025 finding, about how CLIO's current rules treat riot events, is pending Sam's wording and is not written yet.

CLIO's weeks start on Saturday. Each finding is anchored to one `week_start_date`; a finding about a longer episode describes the rest in its summary.

Dropped from the plan: the 2010 constitutional referendum as a "true negative". Those weeks read STABLE with INSUFFICIENT_DATA and every band UNKNOWN, which is an absence of evidence and is not presented as a correct quiet reading.

**How the sources relate.** The classification is computed from ACLED data, so the ACLED card shows the classifier's own input and is labelled that way. Only OONI and Google Transparency are independent of the classification. The product never describes the three cards as three independent confirmations.

**Coverage is uneven and the product says so.** OONI weekly signals exist only from 2023-05-27 to 2025-06-28. Google Transparency data is half-yearly from 2012, with gaps. Of Kenya's 1,523 classified weeks (1997-01-11 to 2026-03-14), 976 carry INSUFFICIENT_DATA confidence. The classifier's thresholds are labelled provisional in CLIO's own code, and the methodology page states that.

## 6. Data

- **Source:** a one-time, human-run export of CLIO's materialized BigQuery output to `data/snapshot/`, with a `MANIFEST.json` recording, for every file, the source table, the exact SQL, the row count and the export time.
- **Synthetic data is excluded.** The export refuses any source table that carries a synthetic flag column at all (a column whose name ends in `is_synthetic`), whatever its values. CLIO's Lumen-derived signal and its composite pressure score are not exported, stored or served.
- **Storage:** PostgreSQL. Snapshot tables mirror the exported files (`regime_weeks`, `acled_signal_context`, `ooni_weekly_signals`, `google_transparency_requests`), with `snapshot_meta` and `snapshot_tables` holding the manifest. Curated content lives in `findings` and `finding_caveats`. Evidence cards are computed at request time from the snapshot tables; there is no separate evidence table.
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
| CI | GitHub Actions: lint, contract validation, unit and integration tests, frontend checks, compose smoke test |
| CD | GitHub Actions deploy workflow: automatic to dev after CI passes, manual "Promote to production" (§7.1) |
| Deployment | Google Cloud Run `europe-west1` (frontend and backend services per environment) and Neon Postgres on AWS `eu-central-1` (one branch per environment) |
| Telemetry | OpenTelemetry traces and metrics, structured JSON logs; Grafana LGTM container in `docker compose` (§7.2) |
| Alerting | Grafana alert rule provisioned from the repository, webhook contact point (§7.3) |
| On-call | Responder agent run against the local compose stack (§7.4) |
| Task tracker | GitHub Issues (§7.5) |

The API has eight read-only endpoints under `/api`: health, timeline, findings list, finding detail, three evidence endpoints, and methodology. `openapi.yaml` is the authority on their shape.

### 7.1 Environments and delivery

- **Two environments, dev and production.** Each has a frontend service and a backend service on Google Cloud Run in `europe-west1`, and its own Neon Postgres branch (AWS `eu-central-1`) seeded from the committed snapshot by a migration-and-seed job.
- **Dev.** Every push to `main` that passes CI is deployed to dev automatically, with no manual step. A push whose CI fails deploys nothing.
- **Production.** Production changes only through a manual "Promote to production" workflow. It deploys the same commit's images that dev already ran; it does not rebuild. A GitHub environment requiring Sam's approval protects it.
- **Smoke test.** Each deploy ends with a request to `/api/health` through that environment's frontend URL. It must return the snapshot version in the repository.
- **Scale.** Services scale to zero, with at most one instance each.
- **Rollback.** Route traffic back to the previous Cloud Run revision.
- **Secrets and authentication.** Database URLs live in Secret Manager. GitHub authenticates to Google with Workload Identity Federation; no key files exist in the repository, the images or the workflow logs.

### 7.2 Observability

- **The key user journey** is opening a finding page: the finding request, the findings list, the timeline range and the three evidence requests.
- **Traces.** The backend emits OpenTelemetry traces: one per request, with database spans.
- **Metrics.** Request count, error count and latency, per route template (`/api/findings/{slug}`, never the concrete URL).
- **Logs.** Structured JSON logs, each line carrying `trace_id` and `span_id`, so a log line can be found from its trace and the reverse.
- **Locally,** a Grafana LGTM container in `docker compose` collects all three signals, viewable at `http://localhost:3000`, with a dashboard for the journey provisioned from the repository.
- **On Cloud Run,** the same structured logs go to Cloud Logging, with the trace ID in Cloud Logging's trace field. The full trace and metrics UI is the local one; the deployed environments do not have it.
- **Never in telemetry:** client IP addresses, user agents, query strings or request bodies, cookies, database URLs, secrets, or anything identifying a reader. A test checks this.

### 7.3 Alerting

- **The rule.** A Grafana alert rule, provisioned from the repository, fires when, over a 5-minute window with at least 10 requests, more than 5% of `/api/findings/*` requests return 5xx, **or** their p95 latency exceeds 2 seconds.
- **The numbers are starting thresholds,** chosen for a low-traffic archive. The minimum of 10 requests keeps one failed request on a quiet window from alerting.
- **Notification.** It notifies a webhook contact point that the on-call agent listens on.
- **Triggering it on purpose.** The documented way is to stop the database container (or inject a fault in dev mode) while requesting a finding page repeatedly; the alert must fire within the window. It must not fire during a normal `docker compose up` session.

### 7.4 On-call agent

- **Trigger.** It wakes on the alert's webhook.
- **Evidence.** It collects health, recent logs and the failing requests' traces.
- **Fix.** It states a diagnosis, then applies at most one fix from an allow-list: restart a compose service, or apply a code or config fix in the working tree.
- **Allow-list narrowing (21 Oct 2026).** The first version enables service actions only (`docker compose start` or `restart` of `db`, `backend` or `frontend`), because the demo fault needs a service action; code and config fixes are a later extension.
- **Verification.** A fix counts only if the tests pass **and** a replay of the failing request succeeds **and** the alert clears. Otherwise it reverts its own change and escalates.
- **Record.** It always writes an incident report (what fired, evidence, diagnosis, action, verification) to `docs/incidents/`. When it escalates, it opens a GitHub issue labelled `incident`.
- **Never:** git writes, `docker compose down -v`, touching volumes or secrets, or acting on production.
- **Scope.** It runs against the local compose stack, so reviewers can run the demo.
- **Pattern.** It reuses the responder pattern from Sam's Module 4 homework (Order Tracker).

### 7.5 Task tracker

Tasks are GitHub Issues at <https://github.com/Sanjomwa/clio-findings-explorer/issues>, each with acceptance criteria. Coding agents read their issue first and post a progress comment when they finish ([AGENTS.md](AGENTS.md), "Task tracker"). Sam closes issues through commit messages.

## 8. Non-goals

1. It does not reproduce CLIO's dashboard. Five curated findings at most, and a timeline; nothing more.
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
- Dev: a push to `main` deploys to dev automatically only after CI passes; a failed CI deploys nothing.
- Production: it changes only through the manual "Promote to production" workflow, which deploys the images dev already ran, behind a GitHub environment that needs Sam's approval.
- Each environment's public frontend URL serves the same snapshot version as the repository, checked by the deploy's smoke test of `/api/health`.

### 9.2 Evidence integrity

- **Traceability.** Every number on a finding page equals a value in `data/snapshot/`, checked by an automated test, and the page shows the query that produced it.
- **No unsupported claims.** Every factual sentence in a finding has a logged reviewer verdict. None is published with an UNSUPPORTED verdict.
- **Limits are visible.** Every finding has at least one caveat, enforced in the database and the API. A source with no data returns a card that says so. Weeks with INSUFFICIENT_DATA confidence look different on the timeline from confident STABLE weeks.
- **No causal language.** An automated check over the curated content rejects wording that asserts causation or targeting.
- **Independence is stated correctly.** The ACLED card is labelled as the classifier's input. No text calls the three cards independent confirmations.
- **At least one finding shows a limit of the method.** The 2008 and 2025 findings do this.
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
- A self-score against the course's 12 criteria (24 points), aiming for the maximum. The course's pass mark is 10 points, and three peer reviews of other projects are required.

| Criterion (points) | Where the project meets it |
|---|---|
| Problem description (2) | README: the problem, the system and its expected behaviour; §1 and §4 here |
| Product specification (2) | This file, with acceptance criteria in §9, and the public GitHub Issues tracker (§7.5), where each task has acceptance criteria and agents comment on their issue |
| Agent team specification (2) | `docs/agent-team.md` (issue #8): roles, process and limits; `docs/permissions.md` and the hooks |
| Context management (2) | `AGENTS.md` linking the modular docs (issue #9) |
| Application (2) | Frontend, backend and Postgres, running locally with one command (§9.1) |
| Testing (2) | Unit and integration tests, separate and documented, run in CI (§9.1) |
| Containerization (2) | `docker compose up --build` runs db, seed, backend and frontend (§9.1) |
| Deployment (2) | Cloud Run and Neon, dev and production, public URLs (§7.1) |
| CI/CD (3) | CI tests, automatic deploy to dev, manual deploy to production, rollback (§7.1) |
| Observability (2) | Traces, metrics and structured logs sharing a trace ID for the finding-page journey, no reader data, viewable in Grafana (§7.2) |
| Alerting on user impact (1) | The finding-page alert rule (§7.3) |
| On-call agent (2) | The responder agent that wakes on the alert and fixes the fault (§7.4) |

The deployment, delivery, observability, alerting and on-call rows are specified here and not yet built; each has an open issue.

### 9.6 What does not count as success

Traffic, the number of findings, the number of features, or parity with CLIO's dashboard. Three honest findings are better than five with one overclaimed.
