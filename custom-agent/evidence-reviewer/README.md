# evidence-reviewer

A Claude Code subagent that reviews a proposed finding before it is published. Canonical file: [`evidence-reviewer.md`](evidence-reviewer.md). Claude Code loads it from `.claude/agents/evidence-reviewer.md`, which is a copy (the Claude Code docs do not say that symlinked agent files are followed). `backend/tests/unit/test_agent_sync.py` fails if the two differ. Edit the canonical file, then copy it.

## Its one job

Take a proposed finding (summary, caveats, cited figures, citations), split it into individual factual assertions, and return one verdict per assertion. It changes nothing. A separate step (the [`/new-finding`](../../agent-capabilities/README.md) workflow) acts on the verdicts.

| Verdict | Meaning |
|---|---|
| `VERIFIED` | Checked against the snapshot with `query_snapshot`; the exact query and result are shown. |
| `CORRECTED` | The snapshot disagrees; the correct value and the query that shows it are given. |
| `UNSUPPORTED` | The snapshot cannot establish it. Every "X caused Y", "X was in response to Y" or "X targeted Y" claim is UNSUPPORTED, because the snapshot has no attribution field. |
| `EXTERNAL` | A real-world event the snapshot cannot check, or a statement of CLIO's own rules or code. The reviewer checks only that a cited source is attached to the draft (`source attached` / `NO SOURCE`), not that the source is true; for a rule statement the source must be `content/methodology.yaml` or CLIO's production code. A human checks the source. |

## Tool allowlist

`mcp__findings-explorer-tools__query_snapshot`, `Read`, `Grep`, `Glob`. No `Write`, `Edit`, `Bash`, `WebFetch` or `WebSearch`. `tools` is an allowlist in Claude Code, so anything not listed is unavailable to it. Model: `opus` (the docs list `opus` as a valid alias).

## Verdict table format

```
| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
```

followed by a `Summary:` line with the counts.

## Lineage

This is the review pattern Sam uses on CLIO: a separate reviewer that sees the claim and the data but cannot edit the work, so the author and the checker are never the same step. Here the "data" is the committed snapshot and the checker is limited to read-only queries.
