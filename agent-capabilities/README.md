# agent-capabilities

Reusable Claude Code workflows for this repository.

## `/new-finding <slug>`

Canonical file: [`new-finding.md`](new-finding.md). Claude Code loads it as a project slash command from `.claude/commands/new-finding.md` (a copy; the docs confirm symlinks only for skill directories, and `$ARGUMENTS` carries the slug). `backend/tests/unit/test_agent_sync.py` fails if the copy differs. Edit the canonical file, then copy it. Start a new session after changing either file; Claude Code loads commands and agents at session start.

It is the only sanctioned way to add a finding. Steps:

1. Read the human-written draft `content/drafts/<slug>.yaml`.
2. Validate its shape (the finding format plus a `sources` list; see [content/README.md](../content/README.md)).
3. Gather the week's numbers with `query_snapshot`: the `regime_weeks` row, the `acled_signal_context` row with the median of the 12 weeks before it, the `ooni_weekly_signals` rows, and the half-year's `google_transparency_requests` totals. The exact queries are in the workflow file.
4. Invoke the [`evidence-reviewer`](../custom-agent/evidence-reviewer/README.md) subagent.
5. Write the verdict log to `docs/reviews/<slug>.md`.
6. Branch on the verdicts.
7. If a finding was written: run the seed, curl the finding and its three evidence endpoints, run the two content tests.

### Stop conditions

| Condition | What happens |
|---|---|
| No or malformed slug; draft missing; finding already exists; draft shape invalid | STOP before any query |
| `query_snapshot` returns an error (database down) | STOP |
| Any `UNSUPPORTED` verdict (includes every causal, response or targeting claim) | STOP; log written; no finding |
| Any `CORRECTED` verdict | STOP; corrections shown for the human to apply to the draft; never auto-applied |
| Any `EXTERNAL` verdict with `NO SOURCE` | STOP; the sentence needs a cited public source in `sources` |
| All clear | `content/findings/<slug>.yaml` written without `sources`; step 7 runs |

### Run

Needs the dev stack up and seeded (`docker compose up -d --build`), a human-written `content/drafts/<slug>.yaml`, and a Claude Code session started from the repo root (so `.mcp.json`, the agent and the command are loaded). Then type `/new-finding <slug>`. Review `docs/reviews/<slug>.md` and the new file, and commit them yourself.
