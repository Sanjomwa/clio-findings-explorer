# Review: bad-counted-mismatch (test-only fixture)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "167 conflict events were recorded." | VERIFIED | `SELECT 1` -> 167 |
| 2 | "A statement." | VERIFIED | `SELECT 1` -> 1 |
| 3 | "An event." | EXTERNAL | source attached |
| 4 | "A rule." | EXTERNAL | NO SOURCE RESOLVED |

Summary: fixture.
Counted: 3 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 1 EXTERNAL (1 without source).
