# CLIO Findings Explorer

A public, read-only web app that presents curated Kenya civil-liberties findings from a committed snapshot of CLIO output. Each finding is one classified week, shown with its regime state, a plain-language summary, evidence from ACLED, OONI and the Google Transparency Report, and a limitations box stating what the evidence does not establish.

This is a course final project for AI Dev Tools Zoomcamp 2026.

**Status: work in progress.** The backend API (eight read-only `/api` endpoints, FastAPI and Postgres, seeded from `data/snapshot/`) runs locally with Docker Compose and serves five published findings and the methodology text. There is no frontend yet, and the app is not deployed yet.

## Findings

| Week | Finding |
|---|---|
| 22–28 June 2024 | [Protest and suppression both SEVERE](content/findings/finance-bill-2024.yaml): CLIO's first CRISIS week of the 2024 Finance Bill protests. |
| 21–27 June 2025 | [STABLE, with Telegram far above its baseline](content/findings/june-july-2025.yaml): a limits case: suppression was raised, but entering REPRESSION needs two consecutive qualifying weeks. |
| 15–21 July 2023 | [CRISIS, with OONI signals flat](content/findings/july-2023.yaml): the week the opposition began three days of protests. |
| 6–12 August 2022 | [Suppression and violence SEVERE in the election week](content/findings/general-election-2022.yaml): a CRISIS label computed only from ACLED offline events. |
| 19–25 January 2008 | [The first week CLIO could score after the disputed election](content/findings/post-election-violence-2008.yaml): a limits case, where the busiest ACLED week around the election read "STABLE (insufficient data)". |

Every finding was checked before publication, one factual assertion at a time, by an `evidence-reviewer` subagent that queries the snapshot. Figures must match the data; statements about real-world events or about CLIO's own rules must carry a cited source; causal wording is rejected. The verdict log for each finding is in [docs/reviews/](docs/reviews/), the workflow is [`/new-finding`](.claude/commands/new-finding.md), and every AI-assisted step is recorded in [docs/ai-workflow-log.md](docs/ai-workflow-log.md).

- Product definition: [product-spec.md](product-spec.md)
- API contract: [openapi.yaml](openapi.yaml)
- Instructions for coding agents: [AGENTS.md](AGENTS.md)
- Agent permissions: [docs/permissions.md](docs/permissions.md)

## Run it locally

Docker (with Docker Compose) is required.

```bash
cp .env.example .env              # skip if you already have a .env; local placeholder values only
docker compose up -d --build      # starts Postgres, loads the snapshot, starts the API on 127.0.0.1:8000
curl -s localhost:8000/api/health
```

The API can take a few seconds to come up after the compose command returns; if `curl` prints nothing, run it again. Expected result (key fields):

```json
{"status": "ok", "database": "reachable", "snapshot_version": "2026-10-10.1", "migration_head": "0003",
 "row_counts": {"regime_weeks": 1523, "acled_signal_context": 85, "ooni_weekly_signals": 550,
                "google_transparency_requests": 85, "findings": 5, "finding_caveats": 21}}
```

For tests and the backend layout see [backend/README.md](backend/README.md); the full command list is in [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).

The data in `data/snapshot/` is third-party derived data under its sources' own terms, not MIT: see [data/README.md](data/README.md).
