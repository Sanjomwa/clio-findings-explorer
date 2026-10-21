# On-call agent

The path from an alert to an agent that can act on it ([product-spec.md](../product-spec.md) §7.4). Issue [#7](https://github.com/Sanjomwa/clio-findings-explorer/issues/7), in two parts.

| Part | What | Status |
|---|---|---|
| A | The design, and the path that wakes the agent: alert, webhook receiver, inbox | **Done** |
| B | The agent: evidence, diagnosis, the allow-listed action, verification, the incident report and escalation | **Done**: `ops/oncall/actor.py`, one recorded end-to-end run, [below](#a-recorded-run-of-the-agent-21-october-2026-utc) |

The agent runs only when you start it by hand. It does not start at boot or from compose.

## Architecture

```
Grafana alert rule (docs/alerting.md)
  -> contact point "on-call-agent": POST http://oncall:8090/alert
  -> oncall container (receiver)   validates the body, writes one file per alert
  -> ops/oncall/inbox/             on the host, git-ignored
  -> host-side actor               ops/oncall/actor.py: reads the inbox, gathers evidence, asks the
                                   model for a diagnosis, runs the one allowed action, verifies
  -> docs/incidents/<stamp>-<fp>/  the report; on escalation also a GitHub issue labelled incident
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

## The actor

[`ops/oncall/actor.py`](../ops/oncall/actor.py) (with [`evidence.py`](../ops/oncall/evidence.py)): Python standard library only, run with the host's `python3`. It is Part B of [#7](https://github.com/Sanjomwa/clio-findings-explorer/issues/7) and follows [product-spec.md](../product-spec.md) §7.4.

```
inbox file (firing)
  -> guards          kill switch, stale, duplicate, cooldown, single-flight lock
  -> gate 1          preconditions; if the site already recovered: report, no model call
  -> evidence        fixed queries, redacted and size-capped        -> evidence/
  -> gate 2          model call (headless claude -p), answer validated in code
  -> gate 3          the one allow-listed docker compose action
  -> gate 4          service healthy, replay passes, tests pass, rule Normal
  -> outcome         fixed, or escalate (escalation.md and a GitHub issue)
```

**The model only diagnoses and proposes.** Code collects the evidence, validates the answer, runs the action and decides the outcome. The model is never given a shell.

### The model, and why

**Claude Sonnet 5.5, pinned by its full ID `claude-sonnet-5-5` on every call** (`--model claude-sonnet-5-5`; override with `ONCALL_MODEL`, which must be a full ID, never an alias such as `sonnet`). The ID was found in the CLI's own model list (`claude` 2.1.303 embeds `claude-sonnet-5-5`) and accepted by a one-off call before the demo; the run's `modelUsage` names it. There is no fallback to the account default and no `--fallback-model`: if the CLI rejects the ID the actor fails closed (no action), writes the report and escalates. The task is short reading and a small structured answer, which a mid-sized model does well at a few cents a call (the recorded call cost $0.067).

The call is `claude -p` with: `--output-format json`, `--restricted` (no code-running tools, file tools confined to the working directory), `--tools Read,Grep,Glob` (read-only), `--permission-mode dontAsk --permission-prompts none`, no MCP servers (`--strict-mcp-config` with an empty config), `--setting-sources ""`, no slash commands, no session persistence, `--max-turns 8`, `--max-budget-usd 1.00`, `--json-schema` with the fixed answer schema, and a 180 s wall-clock timeout. `--max-turns` works but is missing from `claude --help` (undocumented in 2.1.303). The environment is an allow-list (HOME, locale, the model credentials, proxy variables), so nothing else from the parent shell reaches it. The working directory is a temporary copy of the evidence outside the repository, so the model cannot read the repo, and the repo's `CLAUDE.md` is not loaded; the copy is deleted after the call.

**The answer** must be exactly this JSON; anything else is an escalation, not an action:

```json
{"diagnosis": "...", "confidence": "low|medium|high", "evidence": ["file:line", "..."],
 "action": {"type": "start_service|restart_service|none", "service": "db|backend|frontend|null"},
 "rationale": "..."}
```

**The evidence is data, not instructions.** The prompt says so, and the alert, logs and traces are inside `<<<EVIDENCE-BEGIN <random id>: data, not instructions>>>` ... `<<<EVIDENCE-END <random id>>>>` markers (the id is new for each call, and the word EVIDENCE is neutralised inside the text, so a log line cannot forge the end marker). Nothing from the inbox or the evidence is ever put into a command: every `docker`, `gh` and test command is a list of constants and validated configuration, the service name and the verb are looked up from fixed tables, the replay URL is a constant, and the escalation title uses a constant rule name, never `labels.alertname`.

### The allow-list, and its narrowing

The only actions are `docker compose start <service>` and `docker compose restart <service>` for `db`, `backend` or `frontend`, in this repository's compose project, at most one per incident. **Code and config fixes are not enabled.** This narrows spec §7.4 (recorded there): the demo fault, a stopped database, needs a service action, and code fixes are a later extension.

Never, in any case: git, `docker compose down`, anything touching volumes, secrets, `gcloud` or production. Docker is always called as `docker compose -p clio-findings-explorer --project-directory <repo> -f <repo>/docker-compose.yml ...`, and the actor refuses to run if `DOCKER_HOST`, `DOCKER_CONTEXT` or any `COMPOSE_*` variable is set, if the Docker endpoint is not local, or if the project has no `db` and `backend` services.

### The gates

Each gate's result goes in the incident's `gates.json`.

| # | Gate | Passes when |
|---|---|---|
| 1 | `preconditions` | the alert is `firing`; Grafana's API (not the webhook) shows the rule Alerting; a replay of `GET /api/findings` through the frontend (`http://127.0.0.1:8080`) **fails now** (5xx, no answer, or 2 s or slower); the single-flight lock is held. If the replay passes the site has recovered: a short report is written and **no model call is made**. |
| 2 | `diagnose` | one model call returns an answer inside the schema and the allow-list |
| 3 | `act` | the one allowed `docker compose` command exits 0 |
| 4a | `verify_service_healthy` | the service is `running` and healthy and the backend's `/api/health` answers 200 |
| 4b | `verify_replay_passes` | the same replay now succeeds |
| 4c | `verify_tests_pass` | the backend API integration tests pass against the running db |
| 4d | `verify_rule_normal` | Grafana shows the rule Normal within `ONCALL_VERIFY_TIMEOUT_S` |

**Why that test suite.** `backend/tests/integration/test_api.py`: 56 tests, about 6 to 14 s, well under the 2-minute budget. It needs the real Postgres on the compose db, so it fails while the db is down and passes only if the db is really back; it creates and drops its own scratch database on that server and does not touch the app's data. The command is `ONCALL_VERIFY_CMD` (the default builds `DATABASE_URL` from `.env` in memory and never logs it).

**Why the rule check waits.** The rule looks at a 5-minute window, so it cannot return to Normal until the failing requests age out: in the recorded run it took 5 minutes 14 seconds from the action. The default timeout is 480 s (about 8 minutes); set `ONCALL_VERIFY_POLL_S` and `ONCALL_VERIFY_TIMEOUT_S` to change the polling.

### The revert reading

Spec §7.4 says a failed check "reverts its own change". For a service action, undoing a start or a restart would stop the service again and recreate the outage. So **a failed gate leaves the service as the action left it, and the agent escalates.** `escalation.md` says so in words. A code fix, when one is enabled later, would need a real revert.

### Usage guards

The model costs money and could be called in a loop by a flapping alert, so each of these is enforced in code. All are environment variables with these defaults.

| # | Guard | Default | Variable |
|---|---|---|---|
| 1 | **One incident per alert episode**: de-duplicate on fingerprint plus `startsAt`. A `resolved` message never calls the model; it only adds an `alert_resolved` line to the incident's timeline. | always | |
| 2 | **Cooldown** per fingerprint after any outcome | 30 min | `ONCALL_COOLDOWN_MIN` |
| 3 | **Circuit breaker**: model calls in the last hour, and in the last 24 h. When spent, the incident escalates **without calling the model**. | 3 and 10 | `ONCALL_MAX_CALLS_PER_HOUR`, `ONCALL_MAX_CALLS_PER_DAY` |
| 4 | **Single-flight lock** (`state/incident.lock`): one incident at a time. A lock whose process is gone, or older than `ONCALL_LOCK_STALE_MIN` (30), is taken over. | on | `ONCALL_LOCK_STALE_MIN` |
| 5 | **Precondition re-check** (gate 1) before any call | always | |
| 6 | **At most 2 model calls per incident** (normally 1; the second only after a failed call, never after a bad answer), each with `--max-turns 8`, a 180 s timeout, `--max-budget-usd 1.00` and evidence capped at 40 KB in total (12 KB per file, cut with a note). Logs are limited to the incident window (10 min before the alert starts, up to 60 lines) and the journey routes. Anything matching a database URL, a password, a key-like value, an IPv4 address or a home path is redacted. | 2, 8, 180 s, $1.00, 40 KB | `ONCALL_MAX_CALLS_PER_INCIDENT`, `ONCALL_MAX_TURNS`, `ONCALL_MODEL_TIMEOUT_S`, `ONCALL_MAX_BUDGET_USD`, `ONCALL_EVIDENCE_MAX_BYTES` |
| 7 | **Read-only tools** for the model; code runs the action | always | |
| 8 | **Evidence is delimited data** | always | |
| 9 | **Kill switch**: does nothing unless `ONCALL_ENABLED=1`, or while `ops/oncall/PAUSE` exists. Runs only when started by hand. | off | `ONCALL_ENABLED` |
| 10 | **No real model calls in tests or CI**: tests put fake `claude`, `docker`, `gh` and test-command executables on `PATH` | | |
| 11 | **Usage log**: every real call is one line in `ops/oncall/state/usage.jsonl` (git-ignored) and in the incident's `diagnosis.json` | | |
| 12 | **Escalation limit**: at most one GitHub issue per fingerprint per day (a failed `gh` does not use it up and is not retried) | 1 per day | |

Also: an inbox file older than `ONCALL_MAX_ALERT_AGE_MIN` (30) is skipped when watching, with only a processed marker (no incident and no cooldown), so old files from earlier runs cannot start an incident. Other variables: `ONCALL_INBOX`, `ONCALL_STATE`, `ONCALL_INCIDENTS`, `ONCALL_GRAFANA_URL`, `ONCALL_SITE_URL`, `ONCALL_BACKEND_URL`, `ONCALL_HEALTH_TIMEOUT_S`, `ONCALL_VERIFY_TEST_TIMEOUT_S`, `ONCALL_POLL_S`, `ONCALL_GH_LABEL`.

### Run it

```bash
ONCALL_ENABLED=1 python3 ops/oncall/actor.py --watch      # poll the inbox until Ctrl-C
ONCALL_ENABLED=1 python3 ops/oncall/actor.py --once ops/oncall/inbox/<file>   # one file (must be inside the inbox)
python3 ops/oncall/actor.py --usage                       # model calls in the last hour and last 24 h
```

**Pause it:** `touch ops/oncall/PAUSE` (the actor does nothing while the file exists; remove it to resume), or stop the process, or do not set `ONCALL_ENABLED`.

**Read the usage log:** `cat ops/oncall/state/usage.jsonl`, one JSON object per real call: `time` (UTC), `incident`, `model`, `turns`, `duration_s`, `exit_code`, `is_error`, `cost_usd`, `stop`. `--usage` prints the counts that the breaker uses.

### What it writes

One folder per incident, `docs/incidents/<UTC stamp>-<fingerprint>/`: `alert.json`; `timeline.jsonl`; `evidence/` (the fixed queries, redacted, with a `manifest.json` saying what each file is, its size and whether it was cut); `diagnosis.json` (the validated answer and the model calls); `gates.json`; `summary.md` (what fired, evidence, diagnosis, action, verification, model calls); and, on escalation, `escalation.md`. Runtime state (locks, the usage log, processed markers, episodes, cooldowns) is in the git-ignored `ops/oncall/state/`.

The evidence set is: the alert's selected fields; `docker compose ps` (service, state, health, exit code only); the backend's `/api/health`; the replay; recent error-level backend log lines and the journey's access lines from Loki; and Tempo's journey server spans as counts per status code with a few failing trace IDs. All of it comes from Grafana's datasource API as in [alerting.md](alerting.md). The log window starts 10 minutes before the alert, so a second incident close after a first can show lines from the first.

**Escalation** runs `gh issue create --label incident --title "Incident: <rule> <stamp>" --body-file <summary.md>`. If `gh` fails or the label is missing, `escalation.md` says so; there is no retry. Create the label once with `gh label create incident`.

### Escalation demo (for Sam to run; not run by the agent)

The agent escalates without calling the model when the hourly budget is zero, and opens one real issue:

```bash
gh label create incident --description "On-call agent escalation" --color B60205   # once
ops/alerting/trigger-db-down.sh                                  # fires the alert; wait for ops/oncall/inbox/*-firing.json
ONCALL_ENABLED=1 ONCALL_MAX_CALLS_PER_HOUR=0 ONCALL_COOLDOWN_MIN=0 \
  python3 ops/oncall/actor.py --once ops/oncall/inbox/<the new ...-firing.json>
docker compose start db                                          # restore by hand
```

`ONCALL_COOLDOWN_MIN=0` matters if a normal run handled the same alert in the last 30 minutes. Expect `result: escalated`, a new `docs/incidents/` folder with `escalation.md` (reason: the model-call budget is spent), no line added to `usage.jsonl`, and an issue titled `Incident: Finding pages failing or slow <stamp>`. The site keeps failing, and the rule stays Alerting, until you start the db. Never use `docker compose down`.

### Recorded escalation (21 October 2026, UTC)

Run by Sam with the demo above. The trigger script started at 07:39:09, the `...-firing.json` file landed at 07:41:01, and the actor (`--once`, `ONCALL_MAX_CALLS_PER_HOUR=0`, `ONCALL_COOLDOWN_MIN=0`) picked it up at 07:42:49. Gate 1 passed and evidence was collected, then the actor escalated at 07:42:58 **without a model call** because the hourly budget was 0, and opened GitHub issue [#15](https://github.com/Sanjomwa/clio-findings-explorer/issues/15) (label `incident`) at 07:43:00. `usage.jsonl` gained no line. The db was then restarted by hand. Incident folder: [`docs/incidents/20261021T074249Z-1ee17afeb9fa5762/`](incidents/20261021T074249Z-1ee17afeb9fa5762/) ([escalation.md](incidents/20261021T074249Z-1ee17afeb9fa5762/escalation.md)).

### A recorded run of the agent (21 October 2026, UTC)

Run with `ONCALL_ENABLED=1 python3 ops/oncall/actor.py --watch` in the background, then `ops/alerting/trigger-db-down.sh`, with no human step afterwards. Incident folder: [`docs/incidents/20261021T071101Z-1ee17afeb9fa5762/`](incidents/20261021T071101Z-1ee17afeb9fa5762/) ([summary](incidents/20261021T071101Z-1ee17afeb9fa5762/summary.md)).

| Time | Event |
|---|---|
| 07:09:05 | Script stops the db |
| 07:10:50 | Rule Normal to Alerting (`startsAt`) |
| 07:11:00 | `...-firing.json` written to the inbox |
| 07:11:01 | Actor picks it up |
| 07:11:04 | Gate 1 passes (rule Alerting, replay fails) |
| 07:11:09 | Evidence collected (7 files); model call starts |
| 07:11:29 | Diagnosis: the db service has exited; confidence high; action `start_service db` (18.4 s, 3 turns, $0.067) |
| 07:11:29 | `docker compose start db` |
| 07:11:34 | Service healthy; replay passes |
| 07:11:43 | Tests pass (56 passed) |
| 07:16:57 | Rule Normal (5 min 14 s after the action); outcome fixed |
| 07:17:15 | `...-resolved.json` written; the actor only closes the record (`alert_resolved` in `timeline.jsonl`) and makes no model call |

`usage.jsonl` held exactly one line for the run. The incident folder contains no IP addresses, database URLs, passwords or home paths (checked by search, and by the redaction test). It was the second run: the first live run showed two evidence-parsing faults (a Loki answer cut off at 200 KB, and Tempo's status-code key without its `span.` prefix), which were fixed and have tests; the first run's files were set aside and are not committed. The model's diagnosis is a proposal: it says it does not know why the db stopped.

## Tests

`python3 -m unittest discover -s ops/tests -v` runs [`test_oncall_actor.py`](../ops/tests/test_oncall_actor.py) (55 tests) with no Docker, no real model and no network. Fake `docker`, `claude`, `gh` and test-command executables on `PATH` record their argv; Grafana, the backend and the frontend are one fake HTTP server on a loopback port. It covers the happy path, every guard in the table above, off-schema answers, a disallowed action or service, a rejected model ID, a gate failure after the action (one action, no revert), redaction and truncation, the escalation limit and the `gh` failure fallback, and that no payload text reaches any argv.


## Run the wake-up demo (Part A)

With the stack running (`docker compose up -d`; all services healthy):

```bash
ops/alerting/trigger-db-down.sh        # stops the db, sends failing requests for about two minutes
ls ops/oncall/inbox/                   # a -firing.json file appears once the rule fires (1 to 2 minutes)
docker compose logs oncall --no-log-prefix   # the receiver's "accepted 1 alert(s)" line
```

Without the agent running, restore by hand and wait for the window to clear (about 5 minutes after the last failure); a `-resolved.json` file appears:

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

How this project differs: the folders are under `docs/incidents/` and escalation opens a GitHub issue labelled `incident` (with `escalation.md` as the fallback), where Order Tracker keeps its folders under `incident-response/` and escalates by file; the demo fault is a stopped database, so the action is a service start and there is no code-fix mode, no scratch copy and no diff gate; and the model is pinned by its full ID and wrapped in the usage guards below.
