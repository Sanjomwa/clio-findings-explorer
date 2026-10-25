# What transfers to CLIO's roadmap (spec §9.4)

Three things from this project that CLIO could reuse. Each is a file in this repository; nothing here is in CLIO's repository.

## 1. The API contract shape: `openapi.yaml`

An OpenAPI 3.1 contract (version 0.7.0), hand-authored and read-only. Endpoints: `/api/health`, `/api/timeline` (weekly regime series), `/api/findings`, `/api/findings/{slug}`, `/api/findings/{slug}/evidence/acled`, `.../evidence/ooni`, `.../evidence/google-transparency`, and `/api/methodology`. The evidence card (`EvidenceCard`) is one shape for all three sources: `source`, `has_data`, `period_start`, `period_end`, `period_grain` (`week`, `month`, `half_year` or `other`), `headline_metric`, `metric_value`, a nullable `comparison`, `provenance_note`, `snapshot_files` (the snapshot files the numbers come from) and a source-specific `supporting` object. A source with no data for the window still returns a card, with `has_data` false and the reason in `provenance_note`.

## 2. The snapshot manifest format: `data/snapshot/MANIFEST.json`

Top level: `version`, `exported_at`, `tables`, `synthetic_audit`, `finding_anchors`, `attribution`. Each entry in `tables` has:

- `file`
- `source_table`
- `sql` (the exact query that produced the file)
- `row_count`
- `sha256`
- `exported_at`

`synthetic_audit` records the rule, the tables checked, the SQL used to check them, the flag columns found (none) and the result. `attribution` records, per source, name, licence, filter, manipulation and files (ACLED also has an access date). Note: `openapi.yaml`'s `SnapshotTable` schema lists `file`, `source_table`, `sql`, `row_count` and `exported_at` as required and does not mention `sha256`, which the manifest carries.

## 3. The traceability test: `backend/tests/integration/test_traceability.py`

It checks that every number an evidence endpoint serves equals the snapshot. The expected side reads `data/snapshot/*.ndjson` with the standard library and applies the rules written in `product-spec.md` §4.2 and `openapi.yaml`; it imports nothing from `app.evidence` or `app.db`. The served side is the real app over Postgres seeded with the real snapshot and the real `content/` findings. For each of the five findings and three sources it compares each served value (floats with `math.isclose(rel_tol=1e-9)`, everything else exactly) and fails with the finding, source and field if one differs. The mutation check: set `CFE_TRACE_SNAPSHOT_DIR` to a copy of the snapshot with one value changed, and the test fails. The recorded run changed one `total_events` value (week 2023-07-15) and the failure named `finding=july-2023 source=acled` ([docs/ai-workflow-log.md](ai-workflow-log.md), 2026-10-24, issue #13).

## Questions for CLIO

A question to verify, not a finding. In `data/snapshot/regime_weeks.ndjson`, three weeks have `classification_reason` starting `CRISIS:THREE_FAMILY_SEVERE`:

- 2022-08-06: `CRISIS:THREE_FAMILY_SEVERE|protest=NORMAL(z=0.37),suppression=SEVERE(z=3.06),violence=SEVERE(z=3.41)|HIGH:HIGH|`
- 2022-08-13: `CRISIS:THREE_FAMILY_SEVERE|protest=NORMAL(z=0.06),suppression=NORMAL(z=0.73),violence=NORMAL(z=-2.9)|HIGH:HIGH|exit_persistence`
- 2022-08-20: `CRISIS:THREE_FAMILY_SEVERE|protest=NORMAL(z=-1.9),suppression=NORMAL(z=-0.46),violence=NORMAL(z=-1.7)|HIGH:HIGH|exit_persistence`

For 2022-08-06, `protest_band` is NORMAL, so two of the three families are SEVERE in that row. Is the reason label meant to count SEVERE families, or does it mean something else?

## Nothing changed in CLIO

Nothing in CLIO's repository or pipeline was changed by this project.
