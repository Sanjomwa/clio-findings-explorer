# ops/: snapshot export

`export_snapshot.py` exports the snapshot of CLIO output that this app serves. It is the only script in this repository that reads CLIO's BigQuery. **Sam runs it once, by hand**, in an environment where the `bq` CLI is authenticated. Coding agents write and test it against fixtures and never run it against BigQuery (AGENTS.md, "Data rules").

It uses the Python standard library only (tested with Python 3.12) and shells out to `bq query --use_legacy_sql=false --format=json --max_rows=100000`, with the `--quiet` global flag so job-status lines stay out of the JSON.

## What it checks

Any failure stops the export with a message starting `export_snapshot: STOPPED:` and exit status 1. **Nothing is written to `--out` unless every check passes.** The files are built in a temporary directory beside `--out` and renamed into place at the end.

1. **`--out`** must be outside every git working tree, except this repository's own `data/snapshot/`. It must not exist or must be empty, and its parent must exist.
2. **Deny-list.** No pinned data query may mention `lumen`, `composite_pressure_score` or `legal_pressure`, in any letter case.
3. **Schema read**, one `INFORMATION_SCHEMA.COLUMNS` query per dataset. This runs for real even with `--dry-run`; it reads metadata only.
   - **Synthetic gate:** the export refuses any source table that has a column whose name ends in `is_synthetic`, whatever its values.
   - Every column the queries read must exist with the BigQuery type the script declares.
4. **Data queries.** For every row:
   - **Deny-list again:** no returned column name may contain a denied term.
   - **Shape:** every row must be an object with no unexpected key, and its key column must be present. Absent keys become null.
   - **Types:** every value must cast to its declared type. Values are written as JSON numbers, booleans and nulls; dates and timestamps are ISO strings, with timestamps in UTC.
   - **Truncation:** a result of 100,000 rows or more stops the export, because bq may have cut it off.
5. **Row checks.**
   - `regime_weeks`: at least 1,523 rows; every week a Saturday; no gaps; no duplicates.
   - `acled_signal_context`: exactly 17 rows, one per week, for each finding anchor.
   - `ooni_weekly_signals`: at least 550 rows; no duplicate (`week_start_date`, `test_name`).
   - `google_transparency_requests`: at least 85 rows.

## Output

| File | Source table | Rows |
|---|---|---|
| `regime_weeks.ndjson` | `intelligence.acled_pressure_regimes` | every Kenya week |
| `acled_signal_context.ndjson` | `features.acled_pressure_signals` | finding windows only |
| `ooni_weekly_signals.ndjson` | `features.ooni_weekly_signals` | every Kenya week and test |
| `google_transparency_requests.ndjson` | `stg.google_transparency_requests` | every Kenya row |
| `MANIFEST.json` | | `version`, `exported_at`, `tables[]` (file, source table, exact SQL, row count, sha256, export time), `synthetic_audit`, `finding_anchors`, `attribution` |

Every query sorts by its natural keys and then by every other selected column, so the row order, and therefore each file's sha256, does not depend on how BigQuery breaks ties.

A finding window is the anchor week, the 12 weeks before it and the 4 after it. The anchors are in `FINDING_ANCHORS` at the top of the script; adding a finding window means adding one date there.

## How to run it

Do this in the environment that has `bq` authenticated against CLIO's project, from a clone of this repository at the commit that contains the script.

**1. Check that bq points at CLIO's project.** The queries use `dataset.table` names with no project id, so they run against bq's default project.

```bash
bq ls
```

The list must include the `intelligence`, `stg` and `features` datasets. If it doesn't, set the default project (`gcloud config set project <CLIO project>`, or `project_id` in `~/.bigqueryrc`) and check again.

**2. Check how bq writes JSON.** This is one cheap query:

```bash
bq --quiet query --use_legacy_sql=false --format=json 'SELECT 1 AS n, TRUE AS b, CAST(NULL AS STRING) AS s, CURRENT_TIMESTAMP() AS t'
```

The script accepts numbers and booleans either as JSON values or as strings, and accepts NULL either as `null` or as a missing key. For timestamps it accepts `2026-10-07 09:00:00 UTC`, ISO 8601 and epoch seconds. If the output looks like none of these, stop and send it to the coding session before going further.

**3. Dry run.** This runs the schema reads for real, dry-runs every data query and writes nothing. `--out` must already pass its checks, so pick a directory outside any git repository whose parent exists:

```bash
python3 ops/export_snapshot.py \
  --out ~/clio-snapshot-out \
  --acled-access-date YYYY-MM-DD \
  --dry-run
```

It prints `Synthetic gate and schema check passed for 4 tables.`, then the bytes each data query would process, then a total. Read the total before going on.

**4. Export.** This is the same command without `--dry-run`. `--snapshot-version` defaults to today's UTC date plus `.1`; pass it to choose another, for example on a second export the same day.

```bash
python3 ops/export_snapshot.py \
  --out ~/clio-snapshot-out \
  --acled-access-date YYYY-MM-DD
```

On success it prints each file's row count and `Snapshot <version> written to <dir>`.

**5. Verify the checksums.** Run this in the output directory:

```bash
cd ~/clio-snapshot-out
python3 -c "import hashlib, json; m = json.load(open('MANIFEST.json')); [print(t['file'], t['row_count'], 'OK' if hashlib.sha256(open(t['file'], 'rb').read()).hexdigest() == t['sha256'] else 'MISMATCH') for t in m['tables']]"
```

Every line must end in `OK`.

**6. Copy it into this repository.** From the root of this repository's clone, with `data/snapshot/` absent or empty:

```bash
mkdir -p data/snapshot
cp -p ~/clio-snapshot-out/* data/snapshot/
```

Then run the step 5 command again inside `data/snapshot/`. Alternatively, steps 3 and 4 can write straight into the clone with `--out data/snapshot`. That is the one place inside a git working tree the script accepts, and only for the clone the script itself lives in.

Before committing `data/snapshot/`, read [data/README.md](../data/README.md) on the data's terms.

## If it stops

The message names the guard or check and the table, row or column. Nothing has been written to `--out`. Do not edit the script's checks to get past it; send the message to the coding session.

## Tests

The tests use a fake bq runner and generated fixtures under `ops/tests/fixtures/`, and never call BigQuery:

```bash
python3 -m unittest discover -s ops/tests -v
```
