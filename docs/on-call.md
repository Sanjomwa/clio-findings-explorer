# On-call agent

The path from an alert to an agent that can act on it ([product-spec.md](../product-spec.md) §7.4). Issue [#7](https://github.com/Sanjomwa/clio-findings-explorer/issues/7), in two parts.

| Part | What | Status |
|---|---|---|
| A | The design, and the path that wakes the agent: alert, webhook receiver, inbox | **Done**, described below |
| B | The agent: evidence, diagnosis, the allow-listed fix, verification, the incident report and escalation | **In progress.** Nothing in this file marked "Part B" exists yet. |

Today, when the alert fires, the alert is written to a folder and nothing else happens. No agent reads it, and nothing is fixed.

## Architecture

```
Grafana alert rule (docs/alerting.md)
  -> contact point "on-call-agent": POST http://oncall:8090/alert
  -> oncall container (receiver)   validates the body, writes one file per alert
  -> ops/oncall/inbox/             on the host, git-ignored
  -> host-side actor               Part B: reads the inbox, gathers evidence, acts
```

**The receiver** is [`ops/oncall/receiver.py`](../ops/oncall/receiver.py): Python standard library only, built from [`ops/oncall/Dockerfile`](../ops/oncall/Dockerfile) and started as the `oncall` service by `docker compose up -d`. It has no published port; only `lgtm` calls it, over the compose network.

| Request | Answer |
|---|---|
| `POST /alert` with a valid Grafana body | 200, `{"accepted": [<file names>]}`. Each alert in the body is written to the inbox. |
| `GET /health` | 200 |
| Not JSON, not an object, `alerts` not a list, or an alert missing `status`, `labels` or `startsAt` (or a status other than `firing` or `resolved`) | 400; nothing is written, not even the valid alerts in the same body |
| Body over 256 KB | 413 |
| No `Content-Length` (including chunked bodies) | 411 |
| Any other path | 404 |
| Wrong method for a known path | 405 |

**The inbox.** Each accepted alert is written as received (the alert object, not Grafana's whole group envelope) to `ops/oncall/inbox/<UTC timestamp>-<fingerprint>-<status>.json`, for example `20261019T161402.480180Z-1ee17afeb9fa5762-firing.json`. The write is atomic: the receiver writes a hidden `.tmp` file in the same folder, then links it to its final name, so a reader never sees half a file and a name is never overwritten. The fingerprint is stripped to letters, digits, `_` and `-` before it is used in a name. Grafana repeats a firing notification (every hour while the alert stays firing), so the inbox can hold several files for one alert; the actor will need to deduplicate on fingerprint and `startsAt`. The folder is git-ignored; only `.gitkeep` is committed.

**Hardening.** The container runs as a non-root user (uid:gid 1000:1000 by default, so the inbox files belong to the host user; set `ONCALL_UID` and `ONCALL_GID` if yours differ), with a read-only root filesystem, all capabilities dropped, `no-new-privileges`, and a healthcheck on `/health`. The only writable path is the inbox mount. Log lines are JSON in the same shape as the backend's ([observability.md](observability.md)) and carry no client address and no request body.

**Why the receiver and the actor are separate.** The actor needs `docker compose` and the working tree: it restarts services and may change files. Giving a container the Docker socket would give it control of the whole machine, and the container is the one thing that takes input from the network. So the container only receives and writes a file; the actor runs on the host (WSL), where the person running the demo can see it, and acts only on what it reads from the inbox. An alert body is untrusted data to the actor too: it is never run or put into a command.

## The actor (Part B, in progress)

Planned from spec §7.4. None of it is built.

- **Allow-list.** At most one fix per incident, either restarting a compose service or a code or config fix in the working tree. Anything else escalates.
- **Never.** Git writes, `docker compose down` (with or without `-v`), touching volumes or secrets, acting on production.
- **Evidence.** Health, recent logs and the failing requests' traces, from the same Grafana stack.
- **Verification gate.** A fix counts only if the tests pass, a replay of the failing request succeeds, and the alert clears.
- **Revert.** If any check fails, the agent reverts its own change.
- **Report.** An incident report (what fired, evidence, diagnosis, action, verification) is always written to `docs/incidents/`.
- **Escalation.** When it cannot fix the fault, it opens a GitHub issue labelled `incident`.

## Run the wake-up demo (Part A)

With the stack running (`docker compose up -d`; all services healthy):

```bash
ops/alerting/trigger-db-down.sh        # stops the db, sends failing requests for about two minutes
ls ops/oncall/inbox/                   # a -firing.json file appears once the rule fires (1 to 2 minutes)
docker compose logs oncall --no-log-prefix   # the receiver's "accepted 1 alert(s)" line
```

Then restore by hand and wait for the window to clear (about 5 minutes after the last failure); a `-resolved.json` file appears:

```bash
docker compose start db
```

To see that Grafana's delivery succeeded, open `http://127.0.0.1:3000/api/alertmanager/grafana/config/api/v1/receivers`: the `on-call-agent` integration has a `lastNotifyAttempt` and no `lastNotifyAttemptError`. Never use `docker compose down` for any of this.

To try the receiver without Grafana, from inside the compose network only (there is no host port), or by running it directly:

```bash
ONCALL_INBOX=$(mktemp -d) ONCALL_PORT=8090 python3 ops/oncall/receiver.py
```

### A recorded run (19 October 2026, UTC)

| Time | Event |
|---|---|
| 16:11:50 | Script stops the db |
| 16:13:50 | Rule Normal to Alerting (`startsAt`), 120 s after the db stopped |
| 16:14:02 | `...-firing.json` written; the receiver logged 200; Grafana's delivery to `on-call-agent` shows no error |
| 16:16:29 | `docker compose start db` |
| 16:20:20 | `endsAt` of the alert: the rule is Normal again |
| 16:20:32 | `...-resolved.json` written |

## Order Tracker pattern

Part B reuses the responder from the Order Tracker homework (`incident-response/` in that project: `RUNBOOK.md`, `responder.py`, `fixmode.py`). What it does, and where this project differs:

- **Trigger.** Grafana posts to a small HTTP listener; it replies 202 at once and handles one incident at a time on a worker. It ignores `resolved`, and deduplicates on fingerprint plus `startsAt`. There the listener runs on the host (127.0.0.1:8001, reached from Grafana as `host.docker.internal`); a receiver container writing to a bind-mounted inbox was tried and worked (its canary notes), but the host listener was chosen. Here the receiver is a container and the actor reads its inbox, as above.
- **Who decides.** The "agent" is an LLM: headless Claude Code (`claude -p`) with `--tools` restricted (read-only: Read, Grep, Glob; fix mode adds Edit and Write), `--permission-mode dontAsk`, a spend cap, no MCP servers and no shell. But the mode (read-only or fix), the gates and the rollback are decided by code, never by the model.
- **Allow-list.** Enforced by the harness, not the prompt: in fix mode the model works in a scratch copy of `app/`, `tests/` and the evidence, with Edit and Write allowed only inside it and denied for `tests/` and `evidence/`. A code diff gate then allows only edits to existing `app/*.py` files, at most 60 lines, with no new or deleted files and a clean secret scan.
- **Fix gate.** Eleven gates in order: replay the failing request from the evidence and see it fail before the fix, tests pass in the patched copy, the same replay passes, then the real tree is changed, the service rebuilt, the replay is run against the live service, and Grafana shows the rule Normal within 5 minutes.
- **Revert and escalate.** A failure before the real tree is touched changes nothing. A failure after restores the original files from a saved `baseline/` copy (not git), rebuilds, and escalates by writing `escalation.md` for a human. A fix mode precondition (not a test alert, Grafana's own API shows the rule `Alerting`, the code directory is clean, no other fix running) that fails means analysis only, plus an escalation.
- **Reports.** One folder per incident, `incident-response/incidents/<ID>/`: `alert.json`, `timeline.jsonl`, `evidence/` (fixed queries, redacted, with a manifest), `answer.md`, `gates.json`, `fix.patch`, `verification.json`, `summary.md` and, when escalating, `escalation.md`.

Differences Part B has to settle: the spec asks for reports in `docs/incidents/` and a GitHub issue labelled `incident` on escalation, where Order Tracker keeps its folders under `incident-response/` and escalates by file; and this project's fault in the demo is a stopped database, which needs a service restart rather than a code fix.
