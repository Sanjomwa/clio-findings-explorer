# CLIO Findings Explorer

CLIO Findings Explorer is a public archive that helps journalists, researchers and civil-society readers check what CLIO's data shows about civil-liberties pressure in Kenya in specific weeks, and what it does not. It presents five curated findings from a committed snapshot of CLIO output, each with its regime state, a plain-language summary, evidence from ACLED, OONI and the Google Transparency Report, and a limits box.

This is the final project for AI Dev Tools Zoomcamp 2026.

## Live site

| Environment | URL |
|---|---|
| Production | <https://cfe-frontend-prod-qf6bvfuxjq-ew.a.run.app> |
| Dev | <https://cfe-frontend-dev-qf6bvfuxjq-ew.a.run.app> |

<picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/ledger-dark.png"><img alt="The ledger: one row per year, one cell per week, coloured by regime state" src="docs/images/ledger-light.png" width="800"></picture>

*The landing page: 1,523 classified weeks drawn as a ledger, with the five findings outlined.*

## The problem

When a government restricts civil liberties, the evidence arrives in pieces with different grains. Conflict-event records (ACLED) describe what happened on the street, network measurements (OONI) describe what happened to internet access, and platform transparency reports (Google) describe what content governments asked to have removed. Each has its own collection method and reliability.

A reader who wants to know whether there was coordinated pressure in a particular week has two options today: correlate three raw datasets by hand, or trust a summary with nothing traceable underneath. This project gives a third: a small set of weeks, each shown with its evidence and a statement of what that evidence does not establish. Details are in [product-spec.md](product-spec.md) §1 and §4.

## What it does

The app is read-only and never queries CLIO or BigQuery at runtime. Every number comes from the snapshot in `data/snapshot/`.

- **Ledger (`/`)**: every classified week as one cell, one row per year, coloured by regime state. Weeks with insufficient data are pale. Weeks with a finding are outlined and reachable by keyboard.
- **Finding page (`/findings/:slug`)**: state and confidence, the week's three family bands, a context strip of the 13 weeks either side, three exhibits (A: ACLED, B: OONI, C: Google), a limits box, and the public sources for real-world statements. An exhibit with no data for the week is still shown and says so.
- **Register (`/findings`)**, **methodology (`/methodology`)** and **about (`/about`)**: the list of findings, how CLIO classifies a week, and what the sources and the project are. Light and dark themes.

<picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/finding-dark.png"><img alt="A finding page: Finance Bill 2024" src="docs/images/finding-light.png" width="400"></picture>

<picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/finding-phone-dark.png"><img alt="The same finding page on a phone" src="docs/images/finding-phone-light.png" width="300"></picture>

| Week | Finding |
|---|---|
| 22–28 June 2024 | [Protest and suppression both SEVERE](content/findings/finance-bill-2024.yaml): CLIO's first CRISIS week of the 2024 Finance Bill protests. |
| 21–27 June 2025 | [STABLE, with Telegram far above its baseline](content/findings/june-july-2025.yaml): a limits case: suppression was raised, but entering REPRESSION needs two consecutive qualifying weeks. |
| 15–21 July 2023 | [CRISIS, with OONI signals flat](content/findings/july-2023.yaml): the week the opposition began three days of protests. |
| 6–12 August 2022 | [Suppression and violence SEVERE in the election week](content/findings/general-election-2022.yaml): a CRISIS label computed only from ACLED offline events. |
| 19–25 January 2008 | [The first week CLIO could score after the disputed election](content/findings/post-election-violence-2008.yaml): a limits case, where the busiest ACLED week around the election read "STABLE (insufficient data)". |

The snapshot (`2026-10-10.1`) holds 1,523 Kenya weeks, whose start dates run from 11 January 1997 to 14 March 2026 (the last week ends 20 March 2026). 961 of them are STABLE with insufficient data. It also holds 85 ACLED context rows, 550 OONI rows and 85 Google rows, plus 5 findings with 21 caveats in total.

## Does it work?

### Evidence review

Every finding was checked claim by claim by the [`evidence-reviewer`](.claude/agents/evidence-reviewer.md) subagent, which can only query the snapshot and read files. It gives each assertion a verdict: VERIFIED (the snapshot establishes it), CORRECTED, UNSUPPORTED (including any claim about cause or intent), or EXTERNAL (a real-world or CLIO-rule statement, which needs a cited source). A finding is published only with no UNSUPPORTED or CORRECTED row and no EXTERNAL row without a source. Counts below are from each log's verdict table.

| Finding | Assertions | VERIFIED | CORRECTED | UNSUPPORTED | EXTERNAL | Log |
|---|---|---|---|---|---|---|
| finance-bill-2024 | 26 | 17 | 0 | 0 | 9 | [log](docs/reviews/finance-bill-2024.md) |
| general-election-2022 | 35 | 23 | 0 | 0 | 12 | [log](docs/reviews/general-election-2022.md) |
| july-2023 | 35 | 24 | 0 | 0 | 11 | [log](docs/reviews/july-2023.md) |
| june-july-2025 | 39 | 28 | 0 | 0 | 11 | [log](docs/reviews/june-july-2025.md) |
| post-election-violence-2008 | 52 | 35 | 0 | 0 | 17 | [log](docs/reviews/post-election-violence-2008.md) |

One mismatch: the reviewer's own summary line in the finance-bill-2024 log says 15 VERIFIED and 11 EXTERNAL, but its 26-row table has 17 and 9. The table is unedited and its count is used here; the log notes the difference. The other four summary lines match their tables.

### Tests

One command runs every suite (needs the compose database running and seeded, and says so if it is not):

```bash
scripts/test-all.sh
```

| Suite | Tests | Covers |
|---|---|---|
| Hook tests | 74 | The git guard and the spec-first guard |
| Snapshot export, on-call receiver and on-call actor tests | 133 | The export, including that it refuses any synthetic-flagged table (fake BigQuery, fixtures only); the webhook receiver; the on-call actor's guards, gates and escalation, with fake `claude`, `docker` and `gh` (no Docker, no model, no network) |
| Backend unit | 132 | Evidence functions, content language check, schemas; no database |
| Backend integration | 80 | Real Postgres 16 with the real snapshot; every response validated against `openapi.yaml` |
| MCP server | 54 | `spec_lookup` and the read-only `query_snapshot` tool |
| Frontend | 103 | Vitest and Testing Library; also checks that only `client.ts` calls `fetch` |

That is 576 tests in a full run. CI runs the same suites as separate jobs on every push to `main` and every pull request, so `scripts/test-all.sh` is not part of CI. See [docs/ci.md](docs/ci.md).

### Monitoring

The backend emits OpenTelemetry traces (one per request, with database spans), metrics per route template and structured JSON logs that carry the trace ID. `docker compose up -d` starts a local Grafana at <http://127.0.0.1:3000> with a provisioned "Finding-page journey" dashboard; on Cloud Run the same logs go to Cloud Logging with the trace ID. What is collected, what never is, and how to move between a log line and its trace are in [docs/observability.md](docs/observability.md) ([#5](https://github.com/Sanjomwa/clio-findings-explorer/issues/5)).

A provisioned Grafana alert rule pages a webhook when, over 5 minutes with at least 10 requests, more than 5% of `/api/findings/*` requests return 5xx or their p95 latency exceeds 2 s. `ops/alerting/trigger-db-down.sh` fires it on purpose by stopping the database. The numbers, the recorded run and the webhook payload are in [docs/alerting.md](docs/alerting.md) ([#6](https://github.com/Sanjomwa/clio-findings-explorer/issues/6)).

The webhook is received by a small `oncall` service, which writes each alert to a git-ignored inbox folder. The on-call agent ([`ops/oncall/actor.py`](ops/oncall/actor.py), [#7](https://github.com/Sanjomwa/clio-findings-explorer/issues/7)) is started by hand, reads that inbox, collects evidence, asks one pinned model (Claude Sonnet 5.5, read-only tools) for a diagnosis, and, if the answer passes validation, runs one allow-listed `docker compose start` or `restart`. It counts the fix only if the service is healthy, a replay of the failing request passes, a fast test suite passes and the alert returns to Normal; otherwise it escalates with a GitHub issue labelled `incident`. Every incident gets a report folder in `docs/incidents/`. Usage guards (cooldown, call budgets, a kill switch) are described with the recorded end-to-end run, where the agent restarted a stopped database with no human step, in [docs/on-call.md](docs/on-call.md) ([incident report](docs/incidents/20261021T071101Z-1ee17afeb9fa5762/summary.md)).

## Limitations

- **Kenya only, fixed in time.** Weeks start from 11 January 1997 to 14 March 2026. The app does not update, so it says nothing about later weeks.
- **961 of 1,523 weeks are STABLE with insufficient data.** For those weeks a STABLE label means CLIO had too little data, not that things were calm.
- **ACLED is the classifier's own input.** The ACLED card is not independent confirmation of CLIO's label.
- **Narrow source windows.** The OONI rows run from 27 May 2023 to 28 June 2025, so earlier findings show no OONI data. Google data is half-yearly, so its card shows a half-year, not a week.
- **The reviewer is an LLM and was inconsistent across runs.** It gave a summary line that did not match its own table, and wrote a nonstandard verdict text in seven rows, which the clean-review test rejected ([docs/ai-workflow-log.md](docs/ai-workflow-log.md), 15 October 2026). A format rule was added afterwards.
- **No automated traceability test yet.** That every number on a finding page equals a snapshot value is checked by the reviewer and by tests of the evidence functions, not by a test that recomputes each card ([#13](https://github.com/Sanjomwa/clio-findings-explorer/issues/13)).
- **Cloud Run's platform logs record caller IP addresses.** The nginx access log does not, but the platform's cannot be switched off ([docs/deploy.md](docs/deploy.md)).
- **The on-call agent does service actions only.** It can start or restart `db`, `backend` or `frontend`; code and config fixes are not enabled, so it escalates anything else ([docs/on-call.md](docs/on-call.md)). A failed check after an action is not reverted (undoing a start would recreate the outage); it escalates instead.
- **The on-call agent runs only when started by hand** (`ONCALL_ENABLED=1 python3 ops/oncall/actor.py --watch`). It does not start at boot or from compose, so an unattended outage is not fixed. It has been run end to end against the local stack: one fix, and one escalation that opened [#15](https://github.com/Sanjomwa/clio-findings-explorer/issues/15) without calling the model.
- **The alert does not see a stopped backend.** A backend that is down emits no metrics, so the rule sees no data and stays Normal ([docs/alerting.md](docs/alerting.md)).

## Future work

Open issues, in priority order:

1. The agent team specification and modular docs for `AGENTS.md` ([#8](https://github.com/Sanjomwa/clio-findings-explorer/issues/8), [#9](https://github.com/Sanjomwa/clio-findings-explorer/issues/9)).
2. The traceability test ([#13](https://github.com/Sanjomwa/clio-findings-explorer/issues/13)).
3. Reviewer consistency fixes and two finding re-runs ([#10](https://github.com/Sanjomwa/clio-findings-explorer/issues/10)), and small fixes ([#11](https://github.com/Sanjomwa/clio-findings-explorer/issues/11)).
4. The final README pass and a clean-clone check ([#12](https://github.com/Sanjomwa/clio-findings-explorer/issues/12)).
5. Shift-left security checks: ruff `S` rules, CodeQL, dependency audit and injection tests ([#14](https://github.com/Sanjomwa/clio-findings-explorer/issues/14)).

## Self-evaluation

Against the [course rubric](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md): 12 criteria, 24 points, pass mark 10. Points are claimed only where the evidence exists today.

| Criterion | Max | Claimed | Evidence |
|---|---|---|---|
| Problem description | 2 | 2 | This README: [the problem](#the-problem), [what it does](#what-it-does); [product-spec.md](product-spec.md) §1, §4 |
| Product specification | 2 | 2 | [product-spec.md](product-spec.md) with acceptance criteria in §9; [public tracker](https://github.com/Sanjomwa/clio-findings-explorer/issues) with agent comments, e.g. [#1](https://github.com/Sanjomwa/clio-findings-explorer/issues/1) and [#2](https://github.com/Sanjomwa/clio-findings-explorer/issues/2) |
| Agent team specification | 2 | 1 | Roles in [How it was built](#how-it-was-built-the-agent-team-and-process), [AGENTS.md](AGENTS.md), [docs/permissions.md](docs/permissions.md). `docs/agent-team.md` is in progress ([#8](https://github.com/Sanjomwa/clio-findings-explorer/issues/8)) |
| Context management | 2 | 1 | [AGENTS.md](AGENTS.md) describes the project. Modular docs are in progress ([#9](https://github.com/Sanjomwa/clio-findings-explorer/issues/9)) |
| Application | 2 | 2 | [Run it locally](#run-it-locally); frontend, backend and Postgres work end to end with one command |
| Testing | 2 | 2 | [Tests](#tests): unit and integration, `scripts/test-all.sh`, 576 passing |
| Containerization | 2 | 2 | [docker-compose.yml](docker-compose.yml): db, seed, backend, frontend and the local Grafana stack with one command |
| Deployment | 2 | 2 | [Live site](#live-site); [docs/deploy.md](docs/deploy.md) |
| CI/CD | 3 | 3 | CI tests, automatic deploy to dev, manual promotion to production: [ci.yml](.github/workflows/ci.yml), [deploy.yml](.github/workflows/deploy.yml), [docs/deploy.md](docs/deploy.md) |
| Observability | 2 | 2 | [docs/observability.md](docs/observability.md); provisioned dashboard [finding-journey.json](ops/grafana/dashboards/finding-journey.json); privacy and trace-ID tests in [test_telemetry.py](backend/tests/unit/test_telemetry.py) and [test_telemetry_db.py](backend/tests/integration/test_telemetry_db.py); Cloud Logging trace fields on Cloud Run |
| Alerting on user impact | 1 | 1 | Provisioned rule on 5xx share and p95 latency: [docs/alerting.md](docs/alerting.md), [rules.yaml](ops/grafana/provisioning/alerting/rules.yaml), [test_alert_rules.py](backend/tests/unit/test_alert_rules.py); fired on purpose with [trigger-db-down.sh](ops/alerting/trigger-db-down.sh) |
| On-call agent | 2 | 2 | Agent that wakes on the alert, diagnoses with a pinned model, restarts the stopped service and verifies, with usage guards and an incident report: [docs/on-call.md](docs/on-call.md), [actor.py](ops/oncall/actor.py), [tests](ops/tests/test_oncall_actor.py); fixed run [docs/incidents/20261021T071101Z-1ee17afeb9fa5762/](docs/incidents/20261021T071101Z-1ee17afeb9fa5762/summary.md); escalation run [docs/incidents/20261021T074249Z-1ee17afeb9fa5762/](docs/incidents/20261021T074249Z-1ee17afeb9fa5762/escalation.md) and its issue [#15](https://github.com/Sanjomwa/clio-findings-explorer/issues/15) |
| **Total** | **24** | **22** | |

## Data and licence

MIT. See [LICENSE](LICENSE).

The data in `data/snapshot/` is third-party derived data under its sources' own terms, not MIT: see [data/README.md](data/README.md).
