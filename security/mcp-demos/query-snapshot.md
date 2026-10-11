# Demo: the `query_snapshot` MCP tool answers a data question and refuses writes and file reads

**Date:** 2026-10-11
**Agent:** Claude Code, Claude Sonnet 5.5 (`claude-sonnet-5-5`)
**MCP server:** `findings-explorer-tools` ([`mcp-server/`](../../mcp-server/), registered in [`.mcp.json`](../../.mcp.json)), tool `query_snapshot`
**Rule served:** AGENTS.md hard rule 5 (no unverified factual claims)

## Setup

`claude mcp list` reported:

```
findings-explorer-tools: uv run --directory ${CLAUDE_PROJECT_DIR}/mcp-server python server.py - ✔ Connected
```

The session exposed two tools from this server: `spec_lookup` and `query_snapshot`. All four calls below went through the MCP tool, not by importing the module.

## a. An aggregate over the snapshot

Call:

```sql
SELECT primary_regime, count(*) FROM regime_weeks GROUP BY 1 ORDER BY 2 DESC
```

Result:

```json
{"columns": ["primary_regime", "count"],
 "rows": [["STABLE", 1341], ["ESCALATION", 123], ["CRISIS", 27], ["CONFLICT", 21], ["MOBILISATION", 11]],
 "row_count": 5, "truncated": false}
```

(Reformatted onto fewer lines; values as returned.) These match the expected counts and sum to 1523 weeks.

## b. A write

Call:

```sql
DELETE FROM findings
```

Result:

```json
{"error": "Rejected before reaching the database: only SELECT, a set operation of SELECTs, or WITH ... SELECT is allowed, got Delete"}
```

## c. A server file read

Call:

```sql
SELECT pg_read_file('PG_VERSION')
```

Result:

```json
{"error": "Rejected before reaching the database: function pg_read_file() is not allowed"}
```

## d. The row cap

Call:

```sql
SELECT * FROM regime_weeks
```

Result summary (the rows are not reproduced; the full response exceeded the client's output limit and was saved to a file, from which these fields were read with `jq`):

- `row_count`: 200
- `truncated`: true
- `columns` (22): `iso2`, `week_start_date`, `country`, `primary_regime`, `confidence_level`, `previous_regime`, `transition_detected`, `transition_type`, `regime_duration_weeks`, `weeks_in_current_regime`, `regime_held_by_exit_persistence`, `fallback_used`, `methodology_caveat_required`, `protest_band`, `violence_band`, `suppression_band`, `velocity_band`, `conversion_band`, `classification_reason`, `regime_methodology_version`, `feature_version`, `computed_at`

The table holds 1523 rows (sum in a), so 200 returned with `truncated: true` is the cap working.

## What this shows and does not show

- Calls b and c were refused by the parser, before reaching the database. Postgres itself (the `snapshot_reader` role and the read-only transaction, not the parser) also refuses writes and file reads, as proven by the integration tests named in [`mcp-server/README.md`](../../mcp-server/README.md), in particular `test_database_layer_blocks_file_read_and_writes_without_the_parser` and `test_database_refuses_multiple_statements_even_if_parser_were_bypassed` in `mcp-server/tests/test_query_snapshot_integration.py`. This demo did not exercise that layer live.
- Only these four calls were made; the parser's other rejections and the 5 s timeout are covered by the unit and integration tests.
