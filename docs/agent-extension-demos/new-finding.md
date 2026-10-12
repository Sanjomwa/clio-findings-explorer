# Demo: /new-finding stops on a flawed draft

- **Date:** 2026-10-12
- **Models:** session Claude Sonnet 5.5 (`claude-sonnet-5-5`); `evidence-reviewer` subagent `opus` (set in its frontmatter; the report does not show a runtime model name, so that is the configured value, not an observed one)

## Debug check (step 1)

Session started with `claude --debug`. **I cannot see the debug output from inside the session**, so I cannot say whether it names any unrecognised frontmatter field in `.claude/agents/evidence-reviewer.md` or `.claude/commands/new-finding.md`. Sam should check the debug log himself. `/agents` in this Claude Code version prints "The /agents wizard has been removed.", so registration was confirmed from the session's agent list and the file frontmatter, not from `/agents`. See "Post-run checks" below for the debug log. What I could see:

- The session's agent list (the Agent tool's available types) shows: `evidence-reviewer: Reviews a proposed Kenya civil-liberties finding ... Read-only. ... (Tools: mcp__findings-explorer-tools__query_snapshot, Read, Grep, Glob)`. The list does not show the model.
- The skills list shows: `new-finding: Review a human-written draft finding against the snapshot and, only if every assertion passes, write it to content/findings/. The only sanctioned way to add a finding.`
- The frontmatter in the agent file reads `tools: mcp__findings-explorer-tools__query_snapshot, Read, Grep, Glob` and `model: opus`. The command file has only `description` and `argument-hint`.

## Draft (`content/drafts/demo-bad-finding.yaml`, deleted afterwards)

```yaml
slug: demo-bad-finding
week_start_date: "2024-06-22"
iso2: KE
position: 1
title: "Demo draft: a deliberately flawed week"
teaser: "Throwaway draft used to demonstrate the /new-finding review stop."
summary_md: |
  167 conflict events were recorded that week, against a median of 80 in the 12 weeks before.
  In addition, the network anomalies were caused by the protests.
  Parliament was breached on 25 June 2024.
published_at: "2026-10-12T09:00:00+03:00"
caveats:
  - severity: limitation
    caveat_md: "This is a throwaway demonstration draft and is not a real finding."
sources: []
```

## Verdict table

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "Demo draft: a deliberately flawed week" (title) | VERIFIED | Describes the draft itself and makes no claim about the data. No query needed. |
| 2 | "Throwaway draft used to demonstrate the /new-finding review stop." (teaser) | VERIFIED | Describes the draft itself and makes no claim about the data. No query needed. |
| 3 | "167 conflict events were recorded that week" | VERIFIED | `SELECT week_start_date, total_events FROM acled_signal_context WHERE week_start_date = DATE '2024-06-22'` -> `2024-06-22, 167` |
| 4 | "against a median of 80 in the 12 weeks before" | CORRECTED | The correct value is a median of **55.0** across the 12 prior weeks, not 80. `WITH prior AS (SELECT total_events FROM acled_signal_context WHERE week_start_date < DATE '2024-06-22' ORDER BY week_start_date DESC LIMIT 12) SELECT count(*) AS n_weeks, percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events FROM prior` -> `n_weeks 12, median_events 55.0` |
| 5 | "In addition, the network anomalies were caused by the protests." | UNSUPPORTED | This is a causal claim. The snapshot has no attribution field, so it cannot say why the network anomalies happened. At most the data can show that the two things happened in the same week, and the sentence would have to say only that. The draft also does not say which OONI measure "the network anomalies" means. |
| 6 | "Parliament was breached on 25 June 2024." | EXTERNAL | NO SOURCE. The `sources` list is empty (`sources: []`), so no item covers this sentence. |
| 7 | "This is a throwaway demonstration draft and is not a real finding." (caveat, limitation) | VERIFIED | Limitation statement; makes no claim about the data. |

Summary: 4 VERIFIED, 1 CORRECTED, 1 UNSUPPORTED, 1 EXTERNAL (1 without source).

## Stop message

STOPPED at step 6 of `/new-finding` (first match wins: UNSUPPORTED).

- UNSUPPORTED: row 5, "In addition, the network anomalies were caused by the protests." The human rewrites or removes it.
- Also outstanding (not reached, because the first match stops the workflow): row 4 CORRECTED to a prior-12-week median of 55.0 (query in the table), and row 6 EXTERNAL with NO SOURCE (a cited public source is needed in `sources` for "Parliament was breached on 25 June 2024.").

`docs/reviews/demo-bad-finding.md` was written. Nothing was written to `content/findings/`; `ls content/findings/` showed only `.gitkeep`.

## Post-run checks (Sam, 2026-10-12)

1. **`/agents`:** in this Claude Code version it prints "The /agents wizard has been removed." So registration was confirmed from the session's agent list and the file frontmatter, not from `/agents`.
2. **Debug log:** the session was started with `claude --debug`; the log file is `~/.claude/debug/e9a12444-2e52-4332-a40f-da67ecb3060a.txt`. These three lines, verbatim:

   ```
   2026-10-12T09:34:26.636Z [DEBUG] [API REQUEST] /v1/messages x-client-request-id=42827dfb-ba40-4dce-bec3-84846ac44554 source=agent:custom:evidence-reviewer
   2026-10-12T09:34:34.180Z [DEBUG] [API REQUEST] /v1/messages x-client-request-id=71f6a499-fde6-4333-8b90-38f89c13ed30 source=agent:custom:evidence-reviewer
   2026-10-12T09:34:43.850Z [INFO] [Stall] agent_completion agentId=a552912b2ea0f9b0a agentType=evidence-reviewer exitPath=completed durationMs=18042 turns=2 finalStopReason=tool_use lastChunkAgeMs=60 lastToolUseId=toolu_01SwMbcXbjakcyGM2x2VoDgd lastToolResultSeen=toolu_01SwMbcXbjakcyGM2x2VoDgd
   ```

   Grepping the log for unknown|invalid|ignor|warn combined with agent|command|field returned no lines, so no unrecognised-frontmatter warning was logged.
3. **Model:** the reviewer's frontmatter sets `model: opus`. The same log mentions model IDs claude-opus-5-5 (23 times), claude-sonnet-5-5 (19) and claude-haiku-5-5 (1). The main session ran on Sonnet 5.5, so the Opus mentions are consistent with the reviewer running on Opus. The log's request lines don't name the model per request, so this is not a direct per-request confirmation.
4. **Workflow wording:** after the demo, step 2 of the workflow was tightened. The shape check now only requires `sources` to be a list (it may be empty). Enforcing sources for real-world event statements is the reviewer's EXTERNAL rule, which is what stopped this demo.
