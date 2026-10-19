# Alerting

One Grafana alert rule watches the finding-page journey and pages a webhook when readers are being failed or kept waiting ([product-spec.md](../product-spec.md) §7.3). Issue [#6](https://github.com/Sanjomwa/clio-findings-explorer/issues/6). It uses the metrics from [observability.md](observability.md). The page is received by the `oncall` service and written to an inbox ([on-call.md](on-call.md)); the agent that acts on it is issue [#7](https://github.com/Sanjomwa/clio-findings-explorer/issues/7), Part B, and does not exist yet.

## The rule in plain words

Every 30 seconds, Grafana looks at the last 5 minutes of requests to `/api/findings` and everything under it (the finding, and its three evidence requests). It fires when there were **at least 10** such requests **and** either **more than 5% of them returned 5xx** or **their p95 latency was above 2 seconds**. Otherwise it stays Normal.

| Number | Value | Why |
|---|---|---|
| Window | 5 minutes | Long enough to hold a reader's whole visit, short enough to fire while the fault is still happening. |
| Minimum requests | 10 | This is a low-traffic archive. With fewer than 10 requests, one failed request would be 10% or more and would page someone for nothing. |
| 5xx share | more than 5% | A healthy read-only API returns none. Above 5%, roughly one reader in twenty is seeing an error. |
| p95 latency | above 2 s | Normal responses take tens of milliseconds. A reader waiting 2 s on one request in twenty is hurt even if nothing errors. |
| Evaluation | every 30 s, no pending period | The alert shows up within one evaluation of the condition becoming true. |

These are starting thresholds, as the spec says. They are asserted in [`backend/tests/unit/test_alert_rules.py`](../backend/tests/unit/test_alert_rules.py), so changing a number in the configuration without changing the spec and the test fails the build.

**Which requests.** The route matcher is `http_route=~"/api/findings(/.*)?"`. That covers `/api/findings`, `/api/findings/{slug}` and the three `/api/findings/{slug}/evidence/*` routes. `/api/health`, `/api/timeline` and `/api/methodology` are not counted.

**No data is not an alert.** With no traffic, or before the first request, there is no series; the rule is set to `noDataState: OK`, so an idle stack stays Normal. A query error is reported as an error (`execErrState: Error`), and Grafana can show that state briefly right after the `lgtm` container starts, before Prometheus is ready.

**How it is built.** One Grafana-managed rule with three Prometheus queries (`A` total, `B` 5xx, `C` p95 from the histogram buckets), each reduced to a number, a math expression `($TOTAL >= 10) && (($ERRORS / $TOTAL > 0.05) || ($P95 > 2))`, and a threshold on that result. Labels are `severity=page` and `journey=finding-page`. Files are in [`ops/grafana/provisioning/alerting/`](../ops/grafana/provisioning/alerting/): `rules.yaml`, `contact-points.yaml`, `policies.yaml`.

**Counting caveat.** The counts use `increase()` over the window. Prometheus drops the first sample of a series that appears inside the window, so the first failed requests after a quiet period are counted slightly low (in the run below, 24 failed requests showed as about 12). The rule can therefore fire a little later than the true count suggests, never earlier.

**It resolves when traffic thins out.** If the fault continues but fewer than 10 requests fall in the window, the rule goes back to Normal. Once the failing requests age out of the window or are outweighed by successful ones, it also clears.

## Where to see it

With `docker compose up -d`, open <http://127.0.0.1:3000/alerting/list>. Anonymous viewers can see the rule, its state and its history; they cannot edit it. The rule is in the folder "CLIO Findings Explorer", group `finding-page-journey`.

## Notification

The contact point `on-call-agent` is a webhook (`POST`, JSON). Its URL is `ONCALL_WEBHOOK_URL`, default `http://oncall:8090/alert`, set on the `lgtm` service in [docker-compose.yml](../docker-compose.yml). The notification policy sends every alert labelled `severity=page` to it, with a 10 s group wait, 1 minute group interval and 1 hour repeat interval.

**The `oncall` service listens on that URL.** It is a small receiver that writes each alert to `ops/oncall/inbox/` ([on-call.md](on-call.md)); nothing reads the inbox yet. A successful delivery shows as a `lastNotifyAttempt` with no `lastNotifyAttemptError` at `http://127.0.0.1:3000/api/alertmanager/grafana/config/api/v1/receivers`. If the `oncall` service is not running, a delivery fails with a message like `lookup oncall ... no such host`.

Alerts without `severity=page` go to the root contact point `grafana-default-email`, which is provisioned only because Grafana needs a root receiver; it has no mail server and delivers nothing.

## Firing it on purpose

```bash
ops/alerting/trigger-db-down.sh
```

It stops only the `db` service, then sends 24 `GET /api/findings` requests through `http://127.0.0.1:8080`, five seconds apart (about two minutes), and prints each status (500 while the db is down). It never restarts the db; that is for the on-call agent (Part B of #7, not built) or you. Watch the rule at the alert list URL above. To restore by hand:

```bash
docker compose start db
```

Then send a few normal requests; the rule returns to Normal once the failing requests have left the 5-minute window (about 5 minutes after the last failure). Never use `docker compose down` for this.

### A recorded run (19 October 2026, UTC)

| Time | Event |
|---|---|
| 07:05:24 | Script starts and stops the db |
| 07:05:30 | First request returns 500 |
| 07:06:30 | Rule Normal to Alerting (the pending period is 0 s, so there is no Pending state), 66 s after the db stopped |
| 07:07:42 | Latest delivery attempt to `on-call-agent`: `Post "<redacted>": dial tcp: lookup oncall on 127.0.0.11:53: no such host` |

A second, complete cycle the same day, including the restore:

| Time | Event |
|---|---|
| 07:16:22 | Script stops the db (rule Normal until now, after about 100 normal requests earlier) |
| 07:16:50 | Rule Normal to Alerting, 28 s after the db stopped |
| 07:20:02 | `docker compose start db`; the API answered 200 within about a second, and normal requests continued every 3 s |
| 07:24:50 | Rule Alerting to Normal, once the failing requests had left the 5-minute window |

## What the on-call agent receives

Grafana's standard webhook body. This is a real payload from a run, captured by a throwaway listener before the receiver existed (nothing sensitive: the stack is local and the labels are the rule's own). The long `valueString` and `message` fields are shortened here.

```json
{
  "receiver": "on-call-agent",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "Finding pages failing or slow",
        "grafana_folder": "CLIO Findings Explorer",
        "journey": "finding-page",
        "severity": "page"
      },
      "annotations": {
        "description": "Over the last 5 minutes, with at least 10 requests to /api/findings and /api/findings/*, more than 5% returned 5xx or their p95 latency exceeded 2 s. Runbook: docs/alerting.md.",
        "summary": "Finding pages: 100% 5xx, p95 4.875s, over 5 minutes"
      },
      "startsAt": "2026-10-19T07:11:20Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://localhost:3000/alerting/grafana/cfe-finding-page-impact/view?orgId=1",
      "fingerprint": "1ee17afeb9fa5762",
      "ruleUID": "cfe-finding-page-impact",
      "values": {
        "A": 11.714740900791455, "B": 11.714740900791455, "C": 4.875,
        "TOTAL": 11.714740900791455, "ERRORS": 11.714740900791455,
        "ERRRATIO": 1, "P95": 4.875, "IMPACT": 1, "FIRE": 1
      },
      "orgId": 1
    }
  ],
  "groupLabels": { "alertname": "Finding pages failing or slow" },
  "commonLabels": { "alertname": "Finding pages failing or slow", "journey": "finding-page", "severity": "page" },
  "externalURL": "http://localhost:3000/",
  "version": "1",
  "groupKey": "{}/{severity=\"page\"}:{alertname=\"Finding pages failing or slow\"}",
  "truncatedAlerts": 0,
  "orgId": 1,
  "title": "[FIRING:1] Finding pages failing or slow (CLIO Findings Explorer finding-page page)",
  "state": "alerting",
  "message": "**Firing** ..."
}
```

The agent should read `status` (`firing` or `resolved`), `alerts[].labels` and `alerts[].values` (`ERRRATIO` is the 5xx share as a fraction, `P95` is seconds, `TOTAL` is the request count in the window).

## Known gap: backend down

If the backend container itself is down, it emits no metrics, so this rule sees no data and stays Normal (`noDataState: OK`). Readers get a 502 from nginx and nothing pages. A second rule on the frontend's health or on the absence of backend metrics is a candidate for later; it is not part of this issue. A stopped database, which the backend survives and reports as 500s, is covered.

The receiver writes each element of `alerts` to the inbox on its own; a later run is in [on-call.md](on-call.md#a-recorded-run-19-october-2026-utc).
