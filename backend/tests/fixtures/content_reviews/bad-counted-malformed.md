# Review: bad-counted-malformed (test-only fixture)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "167 conflict events were recorded." | VERIFIED | `SELECT 1` -> 167 |
| 2 | "A statement." | VERIFIED | `SELECT 1` -> 1 |
| 3 | "An event." | EXTERNAL | source attached |
| 4 | "A rule." | EXTERNAL | NO SOURCE RESOLVED |

Summary: fixture.
Counted: 2 VERIFIED, 2 EXTERNAL.
