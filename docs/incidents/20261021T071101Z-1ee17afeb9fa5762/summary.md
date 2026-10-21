# Incident 20261021T071101Z-1ee17afeb9fa5762

**Outcome: fixed**

## What fired
- Rule: Finding pages failing or slow (finding-page journey)
- Alert started: 2026-10-21T07:10:50Z
- Window values: {"ERRRATIO": 1.0, "P95": 4.875, "TOTAL": 11.274} (TOTAL requests, ERRRATIO 5xx share, P95 seconds)

## Evidence
Collected by code from the same stack; see `evidence/manifest.json` for what each file is.

## Diagnosis (the model's answer, a proposal, not a fact)
- Diagnosis: The db service has exited (exit code 0), so the backend cannot resolve host 'db'. Every /api/findings request fails with a psycopg OperationalError after about 3.6 s, which explains the 5xx errors and the high p95 latency. The evidence does not show why db stopped. It also does not show whether the data is intact, because health reports snapshot_version and migration_head as null only while the database is unreachable.
- Confidence: high
- Cited evidence: compose-ps.json:9-12 (db State exited, ExitCode 0), compose-ps.json:3-6 (backend running but Health unhealthy), backend-health.json:2-3 (503, database unreachable), logs-errors.json:10 (failed to resolve host 'db': Name or service not known), repeated through logs-errors.json:178 (07:11:04), logs-journey.json:215-366 (GET /api/findings 500 at about 3.6 s, 07:09:11 to 07:11:04), journey-replay.json:3-5 (500 in 3.77 s), traces-journey.json:3-6 (19 of 30 traces returned 500), alert.json:11 (100% 5xx, p95 4.875 s)
- Rationale: The db container is exited, and all backend errors point to it being unreachable. Starting db is the minimal fix. The backend is running and unhealthy only because of the missing db, so it should not need a restart. The logs show the same failure window at 07:00:55 to 07:01:50 ending with 200 responses from 07:01:55 (logs-journey.json:93-99), which suggests the backend recovers once db is available.

## Action
`docker compose start db` (exit 0)

## Verification gates
| Gate | Result | Note |
|---|---|---|
| preconditions | pass | alert firing, rule alerting, replay fails now, lock held |
| diagnose | pass | valid answer, confidence high, action start_service |
| act | pass | `docker compose start db` (exit 0) |
| verify_service_healthy | pass | db running and healthy, backend /api/health answers 200 |
| verify_replay_passes | pass | replay of /api/findings: HTTP 200 in 0.01 s |
| verify_tests_pass | pass | 56 passed, 1 warning in 6.29s |
| verify_rule_normal | pass | Grafana rule cfe-finding-page-impact state: normal |

## Model calls used
- claude-sonnet-5-5, 3 turn(s), 18.4 s, exit 0
- Total cost reported by the CLI: $0.0673


