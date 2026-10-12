# Review: bad-corrected-unresolved (test-only fixture)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "167 conflict events were recorded." | VERIFIED | `SELECT 1` -> 167 |
| 2 | "A statement." | CORRECTED | correct value 55 via `SELECT 1` |

Summary: fixture.
