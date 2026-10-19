# Observability

Traces, metrics and structured logs for the finding-page journey ([product-spec.md](../product-spec.md) §7.2). Issue [#5](https://github.com/Sanjomwa/clio-findings-explorer/issues/5). Alerting (#6) and the on-call agent (#7) build on this and are not part of it.

The journey is opening a finding page: the finding request, the findings list, the timeline range and the three evidence requests. The reader's browser sends no telemetry, so there is no single trace for the whole page. Each request is its own trace, and the dashboard shows the journey across its routes.

## What is collected

| Signal | What | Where it comes from |
|---|---|---|
| Traces | One server span per request, named by route template (`GET /api/findings/{slug}`), with a child span for each database statement | FastAPI and psycopg OpenTelemetry instrumentation, set up in [`backend/app/telemetry.py`](../backend/app/telemetry.py) |
| Metrics | `http.server.request.duration` (a histogram, in seconds) with only `http.route`, `http.request.method` and `http.response.status_code`. Its count is the request rate, its count with a 5xx status is the error rate, its buckets give p95 | The same instrumentation, through an allow-list view |
| Logs | One JSON object per line on stdout, plus one access line per request | The standard `logging` module through one formatter |

The service name is `cfe-backend`. The health check (`/api/health`) is left out of traces, metrics and the access log, because the container healthcheck calls it every few seconds.

Every log line has `timestamp`, `severity`, `message`, `logger`, `trace_id` and `span_id`. The two IDs are null outside a request. The access line adds `method`, `route` (the template), `status` and `duration_ms`. Uvicorn's own access log is off (`--no-access-log` in the Dockerfile), because it prints the client IP.

## What is never collected

Client IP addresses, user agents, query strings, request bodies, cookies, the concrete URL path, and the database URL or any part of its credentials. This is enforced in code, not by configuration:

- **Spans** pass through `ScrubbingSpanExporter`, which drops `client.*`, `net.peer.*`, `network.peer.*`, `user_agent.*`, `url.query`, `url.path`, `url.full`, `http.target`, `http.url`, request and response headers, `server.address`, `server.port`, `db.user` and `db.connection_string`, and redacts the database URL from the remaining strings and from exception events.
- **Metrics** keep only the three attributes above; any other attribute is removed by a view.
- **Logs** have a fixed set of fields. Arbitrary record attributes are not copied, and the database URL and its password are redacted from every message and traceback.

Tests: `backend/tests/unit/test_telemetry.py` sends a request carrying `X-Forwarded-For`, a `User-Agent`, a query string and a cookie, with a fake database URL in the environment, and checks that none of those values, and no forbidden key, appears in any span, metric or log line. `backend/tests/integration/test_telemetry_db.py` checks the same for real database spans.

## Opening it locally

```bash
docker compose up -d        # starts db, seed, backend, frontend and lgtm
```

Open <http://127.0.0.1:3000>. Anyone on this machine can view and use Explore without a login (the provisioned dashboard cannot be changed or saved); the `admin` password is `GF_ADMIN_PASSWORD` from `.env` (default `change-me-local-only`). The OTLP ports (4317, 4318) are reachable by the other services in the compose network and are not published.

The dashboard **Finding-page journey** is in the folder *CLIO Findings Explorer* (<http://127.0.0.1:3000/d/cfe-finding-journey>). It is provisioned from [`ops/grafana/dashboards/finding-journey.json`](../ops/grafana/dashboards/finding-journey.json) and [`ops/grafana/provisioning/dashboards/cfe.yaml`](../ops/grafana/provisioning/dashboards/cfe.yaml), so it cannot be edited in the UI. It shows request rate, 5xx rate and p95 latency for each of the six journey routes, a table of recent traces and the logs.

The telemetry is sent only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Compose sets it for the backend; CI, the tests and Cloud Run do not, and then nothing is exported. The backend does not wait for `lgtm`: with it stopped the API answers as usual, and the exporter logs a warning every few seconds.

## From a log line to its trace, and back

Both directions work for anyone who opens Grafana, with no login. The links come from the data sources of the `grafana/otel-lgtm` image: a Loki derived field turns the `trace_id` of a log line into a link to Tempo, and Tempo's "Logs for this span" runs a Loki query on the trace ID.

One setting differs from the image. [`ops/grafana/provisioning/datasources/grafana-datasources.yaml`](../ops/grafana/provisioning/datasources/grafana-datasources.yaml) is a copy of the image's file with `spanStartTimeShift: "-1m"` and `spanEndTimeShift: "1m"` added to Tempo's `tracesToLogsV2`. Grafana searches the logs only within the span's own time window, and the access line is written a few milliseconds after the request span ends, so without the shift "Logs for this span" finds nothing. Compose mounts the file over the image's one.

**Log line to trace**

1. Open <http://127.0.0.1:3000/explore>.
2. Choose the **Loki** data source at the top left.
3. In *Label filters*, pick `service_name` = `cfe-backend`, and select **Run query** (top right). Or switch to *Code* and enter `{service_name="cfe-backend"}`.
4. Expand a log line in the results.
5. In the expanded line, select the **Trace: <id>** link next to the `trace_id` field. The trace opens in Tempo.

The same lines are in the dashboard's *Logs* panel (<http://127.0.0.1:3000/d/cfe-finding-journey>); expand a line there and use the same link.

**Trace to its log lines**

1. Open the trace (from the link above, or from the *Recent traces* panel of the dashboard, or in *Explore* with the **Tempo** data source and the **Search** tab: *Service Name* `cfe-backend`, **Run query**, then select a trace).
2. In the trace view, expand a span (the top one is the request).
3. Select **Logs for this span** (the logs icon). The span's log lines open in a split pane: Loki with `{service_name="cfe-backend"} | trace_id = "<the trace's ID>"`.

The same two IDs are in the raw stdout lines (`docker compose logs backend`), so a line can also be matched to a trace by hand.

## What Cloud Run gets

Cloud Run (dev and production) has logs only. The JSON lines on stdout go to Cloud Logging, and with `GOOGLE_CLOUD_PROJECT` set (from `GCP_PROJECT_ID` in [`deploy.yml`](../.github/workflows/deploy.yml)) each line inside a request also carries `logging.googleapis.com/trace` (`projects/<project>/traces/<trace_id>`) and `logging.googleapis.com/spanId`. The backend continues the W3C `traceparent` that Cloud Run sends, so the platform's request log and the app's lines share a trace ID. There is no metrics or trace UI on Cloud Run: those exist only in the local stack.

Cloud Run's own request logs record caller IP addresses. That is a platform behaviour we cannot switch off, and it is outside what this app collects.
