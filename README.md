# CLIO Findings Explorer

A public, read-only web app that presents curated Kenya civil-liberties findings from a committed snapshot of CLIO output. Each finding is one classified week, shown with its regime state, a plain-language summary, evidence from ACLED, OONI and the Google Transparency Report, and a limitations box stating what the evidence does not establish.

This is a course final project for AI Dev Tools Zoomcamp 2026.

**Status: work in progress.** The backend API (eight read-only `/api` endpoints, FastAPI and Postgres, seeded from `data/snapshot/`) runs locally with Docker Compose. There is no frontend yet, the app is not deployed yet, and the published findings are still being written, so the API currently serves no findings.

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
                "google_transparency_requests": 85, "findings": 0, "finding_caveats": 0}}
```

For tests and the backend layout see [backend/README.md](backend/README.md); the full command list is in [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).

The data in `data/snapshot/` is third-party derived data under its sources' own terms, not MIT: see [data/README.md](data/README.md).
