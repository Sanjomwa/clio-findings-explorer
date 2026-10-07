# AI workflow log

A running record of the work coding agents do in this repository, appended after each task as the work happens (AGENTS.md, "Workflow log"). Newest entries at the bottom. Entries are not rewritten later; corrections go in a new entry.

## Entry format

```
## YYYY-MM-DD: <short task name>

- **Agent:** <tool and model>
- **Task as given:** <the prompt, summarised faithfully; quote the key instructions>
- **Produced:** <files created or changed, and what they do>
- **Verified:** <commands run and their results; how each claim was checked>
- **Not done / open:** <what was skipped, deferred or left for Sam>
```

---

## 2026-10-05: Part A, read-only recon (written after the fact)

*This entry was written during Part B, after Part A had finished. Part A's prompt forbade any change to the repository, and this log did not exist yet. Its content comes from the Part A report delivered in the same session.*

- **Agent:** Claude Code, Claude Opus 5.5.
- **Task as given:** Read-only recon, change nothing. Report pwd, files, `git status`, `git log`, tool versions. Read `product-spec.md` and `openapi.yaml` and validate the spec as OpenAPI 3.1 without global installs. List anything contradictory, ambiguous or wrong in the three docs ("I want disagreement here, not agreement"). Check current Claude Code hook documentation, with source. STOP and report.
- **Produced:** No files. A report with 20 numbered findings. Among them: evidence 404 vs. an empty card; "one week" vs. multi-week content; undefined week-start day (2024-06-22 is a Saturday in ISO week 25; Parliament was stormed on Tuesday 2024-06-25, ISO week 26); FastAPI's 422 body shape vs. the `Error` schema; no home for curated content; the manifest SQL not served; Google's half-year grain; the deny-list missing `pull` and other history-changing commands; the synthetic-fixture contradiction; a relative hook path that would break every Bash call from a subdirectory.
- **Verified:**
  - `git status`: no commits, 3 untracked files. `git log`: "does not have any commits yet".
  - Versions: Python 3.12.3, node v24.21.0, npm 11.19.0, uv 0.11.25. docker and docker compose not usable: the Docker Desktop shim reports that WSL integration is not enabled for this distro, exit 1.
  - `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml` (validator 0.9.0): `openapi.yaml: OK`, exit 0.
  - Hook docs fetched from https://code.claude.com/docs/en/hooks: settings location, PreToolUse stdin format, exit 2 / `permissionDecision: "deny"` blocking, other exit codes non-blocking.
  - Weekdays computed with Python `datetime`. `python3 /nonexistent.py` exits 2, the basis of the relative-path finding.
- **Not done / open:** No log entry at the time (forbidden by the prompt). Docker WSL integration needs Sam to enable it.

## 2026-10-05: Part B, repository skeleton and the block-autonomous-git hook

- **Agent:** Claude Code, Claude Opus 5.5.
- **Task as given:** After Sam revised AGENTS.md (v2), product-spec.md (v0.2) and openapi.yaml (v0.2.0), re-read them. Create CLAUDE.md, .gitignore (not ignoring `data/snapshot/`), .env.example with placeholders, a README stub, this log, docs/permissions.md v1 and an MIT LICENSE (2026, Samwel Njogu Mwaniki). Build the `block-autonomous-git` PreToolUse hook (stdlib Python):
  - Deny-list from AGENTS.md hard rule 1; allow status, diff, log, show, fetch, add and `restore --staged`.
  - Handle chained commands, `git -C`, env prefixes. Fail closed on unparseable input.
  - Register it as `python3 "$CLAUDE_PROJECT_DIR/agent-hooks/block_autonomous_git.py"`.
  - unittest tests; a README that documents the `sh -c` / `eval` / script / subprocess gap.
  - Log Part A after the fact. Add only commands that ran successfully to the AGENTS.md Commands table. Do not create `content/`. STOP and report.
- **Produced:**
  - `CLAUDE.md`, `.gitignore`, `.env.example`, `README.md`, `LICENSE`, `docs/permissions.md`, `docs/ai-workflow-log.md`.
  - `agent-hooks/block_autonomous_git.py`: shlex-based segment splitter, prefix and wrapper stripping, git global-option skipping, `.exe` normalisation, quoted-heredoc skipping, a conservative text-scan fallback for untokenizable commands, and fail-closed exit 2 on bad input or internal error.
  - `agent-hooks/tests/test_block_autonomous_git.py`: 28 test methods with subtests, run as a subprocess the way Claude Code calls the hook.
  - `agent-hooks/README.md`.
  - `.claude/settings.json`: the PreToolUse registration, written last, after the tests passed.
  - AGENTS.md: only the Commands table row changed.
- **Verified:**
  - `python3 -m unittest discover -s agent-hooks/tests -v`: first run 26 tests, 1 failure (`2>/dev/null git push` allowed). Cause: shlex returns the fd `2` as its own word, so it was read as the program name. Fixed by dropping an all-digit word before a redirect operator. Next run: 26 OK. After adding an internal-error fail-closed test: `Ran 27 tests ... OK`, exit 0.
  - A review flagged backslash-newline continuations as untested. Checked directly: `git \⏎ commit`, `git status && \⏎git commit` and `git -C /d \⏎ push` were all allowed (bypass confirmed). Cause: in POSIX mode shlex keeps the escaped newline as a literal character inside the next word (`\ngit`), or as a standalone `\n` word that the splitter treated as a separator. Fixed by deleting unescaped backslash-newline pairs before tokenizing, as the shell does. Added blocked and allowed continuation cases. Final run: `Ran 28 tests ... OK`.
  - Registration check (scratchpad script): read the command string from `.claude/settings.json` and ran it with `sh -c` from the scratchpad directory with `CLAUDE_PROJECT_DIR` set. A blocked payload exited 2 with the rule message; `git status` exited 0. Re-run after the continuation fix, same result.
  - `git check-ignore -v`: `.env`, `.claude/settings.local.json`, `*-key.json`, `service-account*` and `__pycache__/` are ignored. `.env.example`, `data/snapshot/*` and `.claude/settings.json` are not.
  - `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml` on the revised v0.2.0: OK, exit 0.
  - `python3 -m json.tool .claude/settings.json`: valid JSON.
- **Not done / open:**
  - The live block has not been tested: no deny-list command was run in this session. That is Part C, after a session restart.
  - The registered string uses `${CLAUDE_PROJECT_DIR}` with braces rather than Sam's `$CLAUDE_PROJECT_DIR`; the shell treats both the same.
  - Gaps are documented in `agent-hooks/README.md`, not fixed.
  - `content/` was not created.

## 2026-10-05: Doc fixes after the Part B review

- **Agent:** Claude Code, Claude Opus 5.5.
- **Task as given:** Four doc edits, then STOP (Part C not started):
  1. AGENTS.md, "Secrets and network": allow the session scratchpad for temporary files and reading public web documentation; keep "stay inside this repository" for everything else.
  2. openapi.yaml: replace the `FindingDetail.evidence_available` description with "Sources whose evidence card has data for this finding (has_data true). Every source still returns a card."; bump `info.version` to 0.2.1; re-validate.
  3. product-spec.md §6, "The manifest" bullet: add the synthetic-data audit (columns whose `*_is_synthetic` flag was true in any row) and that the export fails if one would be included.
  4. This log entry.
- **Produced:** The three edits above, worded as given. No other lines changed.
- **Verified:**
  - `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml`: `openapi.yaml: OK`, exit 0.
  - `diff -u` of each file against a copy taken before editing (the files are untracked, so `git diff` shows nothing); diffs reported to Sam.
- **Not done / open:** The `openapi.yaml` description paragraph still says "Status of this version (v0.2.0, …)" while `info.version` is now 0.2.1. Left unchanged because it was not in the requested edits; flagged to Sam.

## 2026-10-05: Part C, proving the git block

- **Agent:** Claude Code, Claude Opus 5.5.
- **Task as given:** After Sam restarted the session and confirmed the hook in `/hooks`: run `git commit --allow-empty -m "hook test"`, which must be blocked, then confirm `git status` still works. Save the exact commands and outputs, with the date, to `security/hook-demos/block-autonomous-git.md`. If the commit is not blocked, stop and tell Sam without undoing anything. STOP and give the final report.
- **Produced:** `security/hook-demos/block-autonomous-git.md`.
- **Verified:**
  - Read-only pre-check: `.claude/settings.json` registration present, AGENTS.md v2 present (the session-start notice that it was "no longer present" only meant it is no longer auto-loaded), no commits on `main`.
  - `git commit --allow-empty -m "hook test"` was blocked by the hook before running, with the rule message.
  - `git status` ran normally (exit 0). `git log` still reports "does not have any commits yet", so no commit was created.
- **Not done / open:** Only the plain `git commit` form was demonstrated live; the other forms rely on the unit tests. No further deny-list commands were run.

## 2026-10-07: Step 1, snapshot export script

- **Agent:** Claude Code, Claude Opus 5.5.
- **Task as given:**
  - **Part A:** a read-only check of the prompt against the repo, AGENTS.md and product-spec.md v0.3, then STOP.
  - **Part B, after Sam's answers:**
    - Write `ops/export_snapshot.py`, stdlib only. It shells out to `bq query --use_legacy_sql=false --format=json --max_rows=<n>` through one replaceable function.
    - Arguments: `--out`, `--acled-access-date`, `--snapshot-version` and `--dry-run`.
    - Five NDJSON files (regime weeks, ACLED event and signal context for five finding windows, OONI weekly signals, Google Transparency requests) plus `MANIFEST.json`.
    - Guards: the synthetic gate, the deny-list, shape, row counts. Build in a temporary directory and move it into place.
    - Write `data/README.md`, `ops/README.md`, unittest tests with a fake bq, the AGENTS.md Commands row and this entry.
    - "You will NOT run this script against BigQuery." Do not change `openapi.yaml`; do not create `data/snapshot/`.
  - **Sam's decisions after Part A:**
    1. Keep the strict synthetic gate: refuse any source table with an `*is_synthetic` column, whatever its values. Align AGENTS.md and spec §6 to say so.
    2. The deny-list applies to pinned data SQL and returned data-row keys, not to `INFORMATION_SCHEMA` results.
    3. The manifest uses the openapi names (`version`, `exported_at`, `tables[]`), plus `sha256` and extra top-level keys.
    4. Five anchors are intended.
    5. `--dry-run` runs the schema reads for real and checks expected columns, and dry-runs the data queries.
    6. Refuse a non-empty `--out`.
    - Also: declare and cast a type for every column; a shape rule allowing a subset of the expected keys; six added signal columns; the 17-row check on signal context only.
- **Produced:**
  - `ops/export_snapshot.py`:
    - The pinned SQL is built at import from column constants and the single `FINDING_ANCHORS` constant.
    - Checks run in this order: the `--out` guard, the deny-list on pinned SQL, then per-dataset `INFORMATION_SCHEMA.COLUMNS` reads (the synthetic gate, plus the expected columns and their BigQuery types).
    - With `--dry-run`, it then dry-runs the data queries and prints bytes.
    - Otherwise it runs the data queries with the truncation guard (`MAX_ROWS` = 100000), the deny-list on returned keys, shape, the type cast and the row checks. It builds in a `mkdtemp` directory beside `--out` and renames it into place.
    - It adds `--quiet` (a bq global flag) to the bq command.
  - `ops/tests/test_export_snapshot.py`: 50 tests. Three of them test `run_bq` itself with `subprocess.run` patched: the exact argv, a non-zero exit, bq missing.
  - `ops/tests/fixtures/fake_bq.py`: a fake runner and generated full-size fixture rows marked FIXTURE.
  - `ops/README.md`, `data/README.md` and a one-line link in `README.md`.
  - The synthetic-wording alignment in AGENTS.md (Data rules) and product-spec.md (§6, both bullets, and §9.2).
  - The AGENTS.md Commands row.
- **Verified:**
  - Part A date facts were computed with Python `datetime`:
    - All five anchors are Saturdays, and the windows don't overlap.
    - 1997-01-11 to 2026-03-14 is 1,523 Saturday weeks.
    - The OONI span is 110 weeks.
  - `python3 -m unittest discover -s ops/tests -v`: `Ran 47 tests ... OK` on the first run.
  - A review then pointed out two gaps:
    - `run_bq` was untested.
    - Timestamp parsing relied on Python 3.12's lenient `fromisoformat`, which accepts any length of fraction. Older versions accept only 3 or 6 digits.
  - Fixes: fractional seconds are now normalised to 6 digits, and `run_bq` and timestamp tests were added. Final run: `Ran 50 tests ... OK`. Only Python 3.12 was tested.
  - Mutation check in a scratchpad copy. Each deliberate break made the expected tests fail:
    - synthetic gate disabled: 3 failures
    - gap check disabled: 1
    - 17-row check disabled: 2
    - shape check disabled: 1
    - pinned-SQL deny-list disabled: 3
    - `--out` repo guard disabled: 3
    - `--out` created at the start of the run: 25
  - `python3 -m unittest discover -s agent-hooks/tests`: 28 OK, unchanged.
  - `python3 ops/export_snapshot.py --help` ran. A fixture run printed the generated SQL and manifest, and the `ops/README.md` checksum one-liner reported OK on that output and MISMATCH after one file was altered.
  - `git diff --quiet openapi.yaml`: unchanged. `data/snapshot/` was not created.
- **Not done / open:**
  - The script has never touched BigQuery. Unconfirmed until Sam's first run:
    - the format of bq's JSON values (strings vs numbers, null vs a missing key, timestamp format);
    - the shape of the dry-run output (the parser accepts the JSON job resource or the text message);
    - the declared BigQuery types (`INT64`, `FLOAT64`/`NUMERIC`, `BOOL`, `DATE`, `TIMESTAMP`), which the schema read checks before any data query.
  - Version headers in AGENTS.md and product-spec.md were not bumped.
  - `docs/permissions.md` was not reworded; it doesn't define "flagged synthetic".
- **Revision after Sam's review (same day):**
  - **Task as given:**
    - Remove `acled_event_context.ndjson` from the export entirely: the query, checks, manifest entry, tests, fixtures and README mentions. `stg.acled_conflict_events` leaves the schema reads and the synthetic audit. Sam's reason: ACLED's EULA (section 3.1) requires published material to be transformative, and says excerpting or reorganising the data is not enough. Counts by ACLED's own event and sub-event types are too close to that line.
    - Rewrite the ACLED part of `data/README.md`: CLIO's weekly classifications and national weekly totals per CLIO pressure domain, with derived statistics. No event-level, sub-national or sub-event-type data, and it can't be used to recreate ACLED's dataset. Name the EULA and the Attribution Policy.
    - Keep `--quiet`, the type check and the non-null key column. Set Google's manipulation to "Filtered to Kenya. period_date derived by CLIO from the reporting period label."
    - Make every ORDER BY deterministic by adding all remaining selected columns as tie-breakers. Add a duplicate check on OONI (`week_start_date`, `test_name`).
  - **Produced:**
    - `ops/export_snapshot.py`:
      - The event-context columns, SQL, check function and export entry are removed. The ACLED attribution now lists two files.
      - A new `_order_by()` builds each ORDER BY from the leading keys plus every other selected column. The schema read keeps `ORDER BY table_name, ordinal_position`, which is already unique.
      - A new `check_ooni()` checks the minimum rows and duplicates.
      - The Google `manipulation` entry is added.
    - Fixtures: `event_rows()` and the event table's data are removed.
    - Tests:
      - The event-only test is removed, and the counts are now 4 data files, 4 tables and 4 dry-run queries.
      - The pinned-SQL deny-list test now picks the export by file name, not by position.
      - Added: ORDER BY covers every selected column; the leading sort keys; the event table appears in no export; the OONI duplicate check; the Google manipulation entry.
    - `ops/README.md`: the event row is removed, the dry-run message now says 4 tables, and it describes the OONI duplicate check and the deterministic ordering.
    - `data/README.md`: the ACLED section is rewritten as instructed.
  - **Verified:**
    - `python3 -m unittest discover -s ops/tests -v`: `Ran 53 tests ... OK`. `python3 -m unittest discover -s agent-hooks/tests -v`: `Ran 28 tests ... OK`.
    - Mutation check in a scratchpad copy: with the OONI duplicate check disabled, `test_ooni_duplicate_week_and_test` failed (1 failure).
    - `grep` finds no remaining `acled_event_context`, `EVENT_` or `acled_conflict_events` in `ops/` or `data/`, except the test that asserts the table is absent.
  - **Not done / open:**
    - Earlier lines of this entry still describe the five-file version, as they were at the time.
    - Whether CLIO's pressure domains are new categories or one-to-one renamings of ACLED's own categories was not checked. There is no access to CLIO; flagged to Sam.
  - **Second revision:** Sam confirmed that `protest_events` is ACLED's "Protests" count and `disorder_events` is ACLED's "Riots" count, one to one. As instructed, these six columns were removed from `acled_signal_context` in the column list, SQL, fixtures and tests: `protest_events`, `disorder_events`, `disorder_fatalities`, `violence_events`, `violence_fatalities`, `suppression_events`. `total_events` and `total_fatalities` stay. The typed-values test now checks the signal row's keys against `SIGNAL_COLUMNS`, and a guard asserts that none of the six names is in any pinned SQL. The `data/README.md` sentence about per-domain totals was replaced with one naming the all-type totals and the derived statistics. `python3 -m unittest discover -s ops/tests -v`: `Ran 53 tests ... OK`. `python3 -m unittest discover -s agent-hooks/tests -v`: `Ran 28 tests ... OK`.
