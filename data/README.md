# Data in this repository

The files in `data/snapshot/` are third-party derived data. They are **not** covered by the MIT licence in [LICENSE](../LICENSE), which applies to the code only. Each file stays under the terms of the source it was derived from. `data/snapshot/MANIFEST.json` records, for every file, the source table, the exact SQL, the row count, a sha256 checksum and the export time, plus the attribution details below.

| Source | Files | Terms | Filter | Manipulation |
|---|---|---|---|---|
| ACLED (Armed Conflict Location & Event Data) | `regime_weeks.ndjson`, `acled_signal_context.ndjson` | Contractual licence, non-commercial use, under ACLED's EULA and Attribution Policy. The access date of the ACLED export is in the manifest. | Kenya | Weekly aggregation and classification by CLIO |
| OONI (Open Observatory of Network Interference) | `ooni_weekly_signals.ndjson` | CC BY-NC-SA 4.0. Derived files carry the same licence. | Kenya | Weekly aggregation by CLIO |
| Google Transparency Report | `google_transparency_requests.ndjson` | Reuse terms not determined | Kenya | Filtered to Kenya. `period_date` derived by CLIO from the reporting period label. |

## ACLED-derived files

The ACLED-derived files hold CLIO's weekly regime classifications for Kenya (`regime_weeks.ndjson`). For the weeks around each finding, `acled_signal_context.ndjson` holds national weekly totals of events and fatalities across all types (`total_events`, `total_fatalities`), plus statistics CLIO derives: z-scores, baseline week counts and data-quality flags.

They contain no event-level records, no sub-national data and no data broken down by ACLED's sub-event types. They cannot be used to recreate ACLED's dataset. Use of ACLED-derived material is governed by ACLED's End User License Agreement (EULA) and ACLED's Attribution Policy.

## How the snapshot is made

The snapshot is produced once, by hand, with [`ops/export_snapshot.py`](../ops/export_snapshot.py) (see [ops/README.md](../ops/README.md)). Nothing in it is edited after export.
