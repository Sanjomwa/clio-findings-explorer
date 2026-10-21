# Agent team

Who works on this repository, what each one may and may not do, and how each limit is enforced. Issue [#8](https://github.com/Sanjomwa/clio-findings-explorer/issues/8). The rules themselves are in [AGENTS.md](../AGENTS.md); the working routine (tracker, commits, STOP, definition of done) is in [process.md](process.md); the permission summary is in [permissions.md](permissions.md).

"Enforced" below means something other than the agent's good intentions stops it: a hook, a tool allow-list, code, a test, a GitHub setting or the way the session is built. Where a limit is only a rule that a person checks, the table says so.

## The roles at a glance

| Role | What it is | Main job | Hard limits, and what enforces them |
|---|---|---|---|
| **Sam** | The product owner, a person | Decides scope and every open question; commits and pushes; approves the production deploy | Production needs his approval: the `production` environment has a required reviewer ([deploy.md](deploy.md), setup step 5; a GitHub setting, not in the repo) |
| **Planning and review session** | Claude in the Cowork desktop app, a separate session | Writes each task prompt, reviews the work before every commit, checks results in a browser, keeps a status log, drafts commit messages | No git, no builds, tests or processes on Sam's machine: it only reads and writes files in the planning workspace and the mirror (the way that session is built; nothing in this repo enforces it) |
| **Claude Code** | The coding agent, in WSL | Builds and tests; reports; comments on its issue | Hooks, the auto-mode classifier, `AGENTS.md` rules, the MCP server's read-only tools |
| **`evidence-reviewer`** | A subagent that Claude Code calls | Checks each factual claim of a draft finding against the snapshot | Read-only tool allow-list in its definition file, pinned by a test |
| **On-call agent** | `ops/oncall/actor.py`, a script that calls headless `claude -p` | Handles the alert: evidence, diagnosis, one service action, verification, report | An allow-list and gates in code, a kill switch, usage guards, tests |

## Sam

- **Responsibilities.** Product owner. Decides scope and every open question (usually from batched multiple-choice questions). The only one who commits and pushes ([AGENTS.md](../AGENTS.md), "Who does what"). Runs `ops/export_snapshot.py`, the only script that reads CLIO's BigQuery. Creates GitHub issues or labels himself when the classifier blocks Claude Code, and closes issues through commit messages. Runs `sync.sh` between his WSL repository and the planning workspace's mirror, and approves the production deploy. Ran the escalation demo ([#15](https://github.com/Sanjomwa/clio-findings-explorer/issues/15)).
- **Inputs.** The planning session's prompt and Claude Code's report; the reviewed diff in the mirror; CI and deploy results.
- **Outputs.** Commits (`Closes #N`), pushes, the production promotion, the decisions.
- **Tools and access.** Everything, including the deploy credentials, which live in GitHub Actions and are never available to the agents ([AGENTS.md](../AGENTS.md), "Who does what").
- **Hard limits.** Production changes only through the manual promotion, which `deploy.yml` allows only from `main` with a commit SHA that dev already ran, and which is held for his approval by the `production` environment ([deploy.yml](../.github/workflows/deploy.yml), [deploy.md](deploy.md)). He runs the sync as a dry run first and pushes only if nothing would be deleted (a habit, not a mechanism). The `production` environment also allows administrators to bypass its protection rules (a GitHub setting, checked by the planning session in the browser on 21 October 2026), so Sam, as the sole admin, could skip his own approval: the approval is a deliberate habit backed by the setting, not something he cannot get around.

## The planning and review session

- **Responsibilities.** Writes the prompt for each piece of work (kept in Sam's planning workspace, not in this repo); reviews Claude Code's work in the mirror before every commit; checks results in a browser (CI runs, deploys, issue state, the Grafana UI, Cloud Logging); keeps a running status log; writes the commit messages Sam uses.
- **Inputs.** The issue, Sam's decisions, the mirror of the repository, Claude Code's report.
- **Outputs.** Prompts (with STOP points), review findings, commit messages.
- **Tools and access.** Reads and writes files in the planning workspace and the mirror, and a browser. **No git access** and it runs no builds, tests or processes on Sam's machine. It cannot see the live filesystem, so Claude Code treats a prompt's claims about the repo as things to check ([AGENTS.md](../AGENTS.md), "Who does what").
- **Hard limits and enforcement.** It cannot commit or run code because it has no such tools. That is a property of the session, not of this repository, so it is not tested here. Its reviews are the second pair of eyes before any commit: see the #6 example below.

## Claude Code

- **Responsibilities.** Writes and edits code, tests, docs and content drafts; runs tests, Docker and local tooling; reports what it did; appends an entry to [ai-workflow-log.md](ai-workflow-log.md); reads its issue first and posts one comment at STOP ([process.md](process.md)). It may consult an advisor model during a task.
- **Inputs.** The prompt, its issue (`gh issue view N --json title,body,state,comments`), the repository.
- **Outputs.** A modified working tree (never a commit), a report, a workflow-log entry, an issue comment.
- **Tools and access.** The working tree, Docker and local tooling, `gh` for issues, package installs from PyPI and npm, public documentation. The project MCP server `findings-explorer-tools` ([mcp-server/README.md](../mcp-server/README.md)): `spec_lookup` and the read-only `query_snapshot`. The `evidence-reviewer` subagent and the `/new-finding` command. No deploy credentials, no BigQuery, no CLIO endpoint.

| Limit | Enforced by |
|---|---|
| No git writes (`commit`, `push`, `tag`, `merge`, `reset`, ...) | The `block-autonomous-git` PreToolUse hook on the Bash tool ([agent-hooks/block_autonomous_git.py](../agent-hooks/block_autonomous_git.py), registered in [.claude/settings.json](../.claude/settings.json), 74 hook tests). It fails closed. It is a string parser with listed gaps (`sh -c`, scripts, aliases; [agent-hooks/README.md](../agent-hooks/README.md)), so AGENTS.md rule 1 still holds where it does not catch a command. |
| GitHub writes limited to `gh issue create`, `gh issue comment`, `gh label create` | The same hook denies the other `gh` writes (issue close, edit, delete; `gh pr` except read actions; `gh release`; `gh api`; and so on). Closing is Sam's, through commit messages. |
| A route must be in `openapi.yaml` before the router changes | The `spec-first-guard` PreToolUse hook on `Write`, `Edit` and `MultiEdit` ([agent-hooks/spec_first_guard.py](../agent-hooks/spec_first_guard.py)); it fails closed on anything it cannot check. |
| Acts only on allowed commands, not unusual or outward-facing ones | The auto-mode classifier, a Claude Code permission layer outside this repo. It has blocked actions (for example `gh issue create`, recorded in [ai-workflow-log.md](ai-workflow-log.md)). The rule is to **stop and report**, never to route around ([AGENTS.md](../AGENTS.md) rule 1 and 8). |
| Data claims come from queries | AGENTS.md rule 5 and the `query_snapshot` tool: one parser-checked read query, a `READ ONLY` transaction, a 5 s timeout, a 200-row cap, run as the no-login `snapshot_reader` role ([permissions.md](permissions.md), "MCP server"). |
| No causal-claim wording in content (rule 6) | A deny-list test over `content/` ([backend/tests/unit/test_content_language.py](../backend/tests/unit/test_content_language.py)) plus the reviewer. In other prose, rule 6 is checked by the planning session's review and by running the same regex over changed docs. |
| Findings only through `/new-finding` | The workflow itself ([agent-capabilities/new-finding.md](../agent-capabilities/new-finding.md)); a test requires a clean verdict log for each finding ([backend/tests/unit/test_content_reviewed.py](../backend/tests/unit/test_content_reviewed.py)) and a database constraint rejects a finding with no caveat. |
| Snapshot read-only; no secrets or key files; stays in the repo directory | AGENTS.md "Data rules" and "Secrets and network". Key-file patterns are in `.gitignore`; snapshot checksums are verified by the seed. The directory rule is not mechanically enforced. |

## The `evidence-reviewer` subagent

- **Responsibilities.** Takes a proposed finding and judges every factual assertion one at a time: VERIFIED, CORRECTED, UNSUPPORTED or EXTERNAL, each with the exact query it ran. It adds a row if the finding has no caveat. It never edits the draft ([.claude/agents/evidence-reviewer.md](../.claude/agents/evidence-reviewer.md)).
- **Inputs.** A draft finding (title, teaser, summary, caveats, cited figures, `citations`).
- **Outputs.** A verdict table. A separate step ([`/new-finding`](../agent-capabilities/new-finding.md)) applies it and writes the log to `docs/reviews/`.
- **Tools and access.** `mcp__findings-explorer-tools__query_snapshot`, `Read`, `Grep`, `Glob` and nothing else.
- **Hard limits and enforcement.** No `Write`, `Edit`, `Bash`, `WebFetch` or `WebSearch`, because the `tools:` line of its definition lists only the four above. [backend/tests/unit/test_agent_sync.py](../backend/tests/unit/test_agent_sync.py) fails if that allow-list changes in the canonical copy ([custom-agent/evidence-reviewer/](../custom-agent/evidence-reviewer/README.md)) or if the `.claude/agents/` copy drifts. It does not fetch cited sources, so a human checks them (EXTERNAL rows). It is an LLM and was inconsistent across runs ([README](../README.md), Limitations).

## The on-call agent

- **Responsibilities.** Wakes on the alert's webhook, collects evidence, asks a pinned model for a diagnosis, runs at most one allow-listed service action, verifies, and writes an incident report or escalates ([on-call.md](on-call.md), [product-spec.md](../product-spec.md) §7.4).
- **Inputs.** A file in the git-ignored inbox written by the `oncall` receiver ([receiver.py](../ops/oncall/receiver.py)); Grafana's datasource API; `docker compose ps`.
- **Outputs.** `docs/incidents/<stamp>-<fingerprint>/` (alert, timeline, evidence, diagnosis, gates, summary), a service start or restart, and on escalation `escalation.md` and a GitHub issue labelled `incident`.
- **Tools and access.** The model has `Read`, `Grep` and `Glob` on a copy of the evidence, outside the repository (`claude -p --restricted --tools Read,Grep,Glob`, no MCP servers, model `claude-sonnet-5-5` pinned). Code, not the model, runs `docker compose start|restart` and `gh issue create`.

| Limit | Enforced by |
|---|---|
| Only `start` or `restart` of `db`, `backend` or `frontend`, one per incident | Fixed tables in [actor.py](../ops/oncall/actor.py) (`ACTIONS`, `SERVICES`) and `validate_answer`; an answer outside the schema or allow-list escalates. Tested in [test_oncall_actor.py](../ops/tests/test_oncall_actor.py). |
| Never git, `down`, volumes, secrets, `gcloud`, production | Not in the code path: every command is a list built from constants against this repo's compose project; the actor refuses to run if `DOCKER_HOST`, `DOCKER_CONTEXT` or `COMPOSE_*` is set or the endpoint is not local. |
| Evidence is data, never instructions or commands | Random-nonce delimiters in the prompt, and a test that no payload text reaches any argv. |
| A fix counts only if verified | Four gates in code (healthy, replay passes, tests pass, rule Normal), recorded in `gates.json`; otherwise it escalates and leaves the service as the action left it. |
| Does not misuse the model | Usage guards in code: de-duplication, cooldown, hourly and daily call caps, a lock, at most two calls per incident, spend and turn caps, and a usage log ([on-call.md](on-call.md)). |
| Runs only when allowed | `ONCALL_ENABLED=1` and no `ops/oncall/PAUSE` file; started by hand, never at boot. |
| No real model calls in tests or CI | Tests put fake `claude`, `docker` and `gh` on `PATH`. |

The actor is a script, not a Claude Code session, so the Claude Code hooks do not apply to it: its limits are the ones in its own code.

## How we work together

```
issue (acceptance criteria, label)
  -> prompt (planning session; STOP points)
  -> build and report (Claude Code; stops at STOP, comments on the issue)
  -> review in the mirror (planning session)
  -> Sam commits and pushes (Closes #N, co-author trailers)
  -> CI (ci.yml)
  -> dev deploy (automatic when CI passes on main)
  -> manual promotion to production (Sam, with approval)
```

1. **Issue.** Each task is a public GitHub issue with acceptance criteria and labels ([process.md](process.md)).
2. **Prompt.** The planning session writes a prompt that names the issue, the rules and the STOP points. Sam passes it to Claude Code.
3. **Build and report.** Claude Code reads `AGENTS.md` and the issue, checks the prompt's claims against the repo, builds in small steps, runs the tests, appends a workflow-log entry, and at STOP posts one comment on the issue and reports: files changed, commands run, what it did not do, what in the prompt was wrong, and commands Sam must run.
4. **Review.** The planning session reads the result in the mirror, checks what it can in a browser, and may send it back.
5. **Commit.** Sam commits and pushes. The commit message carries `Closes #N` (one keyword per issue) and the co-author trailers; docs-only commits may add `[skip ci]`.
6. **CI and deploy.** [ci.yml](../.github/workflows/ci.yml) runs on push to `main`; when it passes, [deploy.yml](../.github/workflows/deploy.yml) deploys dev by itself; production is a manual promotion of the SHA that dev already ran ([deploy.md](deploy.md)).

**When something is blocked or goes wrong.**
- *A hook or the classifier blocks an action.* Claude Code stops and reports; it does not look for another route. Sam does the action himself if it is right (for example, he created issue #14 himself when `gh issue create` was blocked).
- *A prompt contradicts the repo.* Claude Code reports the mismatch before building on it.
- *A test fails.* The cause is found and stated before any fix; no test is deleted or weakened to pass.
- *Review finds a mistake.* It goes back as a correction, or Sam fixes it by hand; the workflow log records what was found.
- *A deployed fault.* Dev is rolled back by routing traffic to the previous revision ([deploy.md](deploy.md)); the on-call agent handles the local alert demo.

## A real example: issue #6, alerting

Issue [#6](https://github.com/Sanjomwa/clio-findings-explorer/issues/6), "Alert on user impact", from creation to close.

| Step | What happened | Evidence |
|---|---|---|
| Issue | Created 17 October 2026 (17:16 UTC), with acceptance criteria. | [#6](https://github.com/Sanjomwa/clio-findings-explorer/issues/6) |
| Prompt | On 19 October the planning session wrote a two-part prompt with a STOP after Part A (per Sam; the prompt lives in the planning workspace, not in this repo). | [workflow log, 19 Oct entries](ai-workflow-log.md) |
| Part A | Claude Code updated the README (observability evidence, 19/24) and the new security issue was needed. `gh issue create` was denied by the classifier, so Claude Code did not retry another way; Sam created [#14](https://github.com/Sanjomwa/clio-findings-explorer/issues/14) himself and committed `2ed5809` ("docs: README observability evidence (19/24) ... security issue #14 [skip ci]"). | [ai-workflow-log.md](ai-workflow-log.md), "README observability evidence"; commit `2ed5809` |
| Part B | Claude Code provisioned the Grafana rule, the webhook contact point, `ops/alerting/trigger-db-down.sh` and 10 unit tests, fired the alert on purpose twice, restored, and reported. | [alerting.md](alerting.md), [rules.yaml](../ops/grafana/provisioning/alerting/rules.yaml), [workflow log, "Issue #6, alert on user impact"](ai-workflow-log.md) |
| Review | The planning session's review caught two things. (1) Claude Code had run a throwaway listener inside the backend container to capture the webhook payload, which went beyond the allowed actions (the workflow log records the listener). (2) A claim that "a restart clears it" was wrong, because a restart keeps a container's files; so Sam ran `docker compose up -d --force-recreate --no-deps backend` (this one is from Sam and the planning session; the repo does not record it). One README gap was deferred to [#12](https://github.com/Sanjomwa/clio-findings-explorer/issues/12). | planning-session review, as told by Sam |
| Commit | Sam committed `f39c631` "feat: alert on finding-page user impact (Grafana, provisioned)" with `Closes #6` and the co-author trailers. | `git show f39c631` |
| CI and deploy | [CI #29](https://github.com/Sanjomwa/clio-findings-explorer/actions/runs/39217133346) and [Deploy #6](https://github.com/Sanjomwa/clio-findings-explorer/actions/runs/39217230233) passed on that commit; #6 closed. | the two runs; [#6](https://github.com/Sanjomwa/clio-findings-explorer/issues/6) |

The review step is why the process has two sessions: Claude Code builds, and a session that cannot edit the repository reads the result before it is committed.
