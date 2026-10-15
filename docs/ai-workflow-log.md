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

## 2026-10-10: openapi.yaml v0.3.0, Part 1

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Task 0 read-only checks, then edit `openapi.yaml` 0.2.1 to 0.3.0 (seven-state `RegimeState`; `Band` replaced by `ConfidenceLevel` and `FamilyBand`; `confidence_band` renamed `confidence_level`; new `WeekClassification` on the finding detail only; `MethodologyResponse` gets `confidence_levels` and `family_bands`; `x-provisional` kept only on `EvidenceCard.supporting` and `SourceNote`), validate, then STOP before Part 2.
- **Produced:** the edited `openapi.yaml`. `pre_transition_target` uses the file's existing nullable-ref style, `oneOf: [$ref, {type: "null"}]`.
- **Verified:**
  - Tree clean at `5f31729` before editing.
  - A stdlib script over `regime_weeks.ndjson` (1,523 rows) matched every expected count: states 1341/123/27/21/11, confidence 976/473/74, bands only NORMAL/ELEVATED/SEVERE/UNKNOWN, pre-transition targets REPRESSION, CONFLICT, CONTESTATION, MOBILISATION.
  - `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml` printed `openapi.yaml: OK`.
  - grep for `Band"`, `confidence_band`, `confidence_bands` matches only `FamilyBand`.
- **Not done / open:** An in-script rename first turned `confidence_bands` into `confidence_levels` by accident; the first script run aborted on an assertion before writing, and the corrected run wrote the file. No other file was changed. Part 2 not started.

## 2026-10-10: product-spec.md v0.4, Part 2

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** After Part 1 was committed (`7edd5f5`, confirmed with `git log`; the prompt's hash was an unfilled `<hash>` placeholder), edit `product-spec.md` to v0.4: version line, §2 states, §4 family bands and new §4.1 display wording, §5 five anchors and approved notes, §8 item 1, §9.2 limits wording. Change nothing else. Then STOP.
- **Produced:** the edited `product-spec.md`. All wording is verbatim from the prompt. The family-bands sentence was placed inside §4 item 2 (the finding page item). The §5 notes sit after the "Dropped from the plan" paragraph and "How the sources relate" is untouched; no new riots caveat was written.
- **Verified:** tree was clean at `7edd5f5` before editing; each replacement matched exactly once; no number was written beyond those in the prompt.
- **Not done / open:** sentences now possibly wrong were left and reported as questions (see report).
  - **Follow-up edits:** Sam answered the open questions, and three edits were made to `product-spec.md`: §4 item 5 now names the confidence levels and family bands, the §5 second sentence now cites snapshot 2026-10-10.1, and the §9.6 last sentence now says "five". README.md left unchanged as instructed.

## 2026-10-10: Phase 1a, spec-first-guard and the MCP server, Part A

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Task 0 read-only checks; build the `spec-first-guard` PreToolUse hook and tests, the `findings-explorer-tools` MCP server with `spec_lookup` and tests, register both, update the docs; then STOP before the live demo (Part B).
- **Produced:**
  - `agent-hooks/spec_first_guard.py`, `agent-hooks/tests/test_spec_first_guard.py` and `agent-hooks/tests/fixtures/openapi.yaml`; a second PreToolUse entry in `.claude/settings.json` (Bash entry unchanged).
  - `mcp-server/` (`server.py`, `pyproject.toml`, `uv.lock`, tests, README) and `.mcp.json`.
  - Docs: `agent-hooks/README.md`, `docs/permissions.md` v2, `AGENTS.md` (rule 2 sentence, two Commands rows).
- **Verified:**
  - Tree clean at `372d4cf`; `backend/`, `mcp-server/` and `.mcp.json` did not exist.
  - `python3 -m unittest discover -s agent-hooks/tests -v`: 69 tests OK (28 git-hook, 41 new).
  - `uv run --directory mcp-server pytest -v`: 7 passed.
  - Hook per-call time with system python3 (PyYAML 6.0.1): 0.18 to 0.22 s. The uv fallback also worked with `UV_OFFLINE=1`.
  - The MCP server answered `initialize` and a `spec_lookup` call over stdio when started from `/tmp`.
- **Not done / open:**
  - Part B (live `/mcp` check and guard demo) needs a new session.
  - The hooks reference documents `Write` and `Edit` input but not `MultiEdit`; its field names are implemented from the older tool shape.
  - The first `mcp-server` run resolved `mcp` 2.x, where `mcp.server.fastmcp` no longer exists; pinned `mcp<2`.
  - `${CLAUDE_PROJECT_DIR}` is not set in Claude Code's own environment, so `.mcp.json` uses `${CLAUDE_PROJECT_DIR:-.}`, which resolves relative to the launch directory.

## 2026-10-10: Phase 1a, spec-first-guard and the MCP server, Part B

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Live demo of the guard hook and the MCP server: confirm Part A files are present, check MCP status, call `spec_lookup` twice, try to write an undeclared-route router (blocked) and a `GET /api/health` router (allowed, then deleted), write the demo document, log it, then STOP. No Part A file changed.
- **Produced:** `security/hook-demos/spec-first-guard.md`; this entry.
- **Verified:**
  - `git status --short` showed `.mcp.json`, `mcp-server/` and `agent-hooks/spec_first_guard.py` present, and no `backend/`.
  - `claude mcp list`: `findings-explorer-tools` Connected.
  - `spec_lookup` with no arguments returned version 0.3.0 and 8 operations; with `/api/findings/{slug}` it returned `found: true`, `getFinding`, responses 200/404/422.
  - The Write of `GET /api/undeclared` was blocked by spec-first-guard, and `ls` confirmed no file and no `backend/`.
  - The Write of `GET /api/health` succeeded; the file and `backend/app/routers`, `backend/app`, `backend` were then removed and `ls backend` confirmed it is gone.
- **Not done / open:** Only the `Write` tool was exercised live; `Edit` and `MultiEdit` are covered by unit tests only.

## 2026-10-10: Phase 1b, database schema, migrations, seed and the db/seed compose services

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Task 0 read-only checks; build `backend/` (uv project, SQLAlchemy 2.0 models, Alembic migration, `python -m app.seed`), the `db` and `seed` compose services, unit and integration tests, and the docs they change; then STOP. No FastAPI, no `content/`, no git writes.
- **Produced:**
  - `backend/` (models, migration `0001_initial_schema`, seed modules, Dockerfile, README, tests and fixtures).
  - `docker-compose.yml` (`db`, `seed`; project name `clio-findings-explorer`) and `docker-compose.content.yml` (optional content mount).
  - Docs: `product-spec.md` §6 Storage line, `AGENTS.md` Commands rows, `backend/README.md`.
- **Verified:**
  - Task 0: tree clean at `0d67d31`; `backend/`, `docker-compose.yml`, `content/` absent; a stdlib script over the NDJSON confirmed row counts 1523/85/550/85, key uniqueness and every null count in the prompt's table; port 55432 was free.
  - `uv run pytest tests/unit`: 26 passed. `uv run pytest tests/integration` (separate `clio_findings_test` database): 18 passed, covering migration up/down/up, real-snapshot counts, `snapshot_meta`, idempotent second run, the caveat trigger cases and an enum CHECK.
  - `docker compose run --rm seed` twice: first run migrated and loaded, second printed "snapshot already loaded"; both exit 0. The image runs as uid 10001.
  - `content/` still does not exist.
- **Not done / open:**
  - Findings FK is `DEFERRABLE INITIALLY DEFERRED` (not in the prompt) so the seed can reload snapshot tables in one transaction; the seed pre-checks and fails clearly if a reload would orphan a finding.
  - `content/` is mounted through a separate `docker-compose.content.yml`, because a plain bind mount of a missing `./content` makes Docker create that directory on the host.
  - `snapshot_meta` "exactly one row" is a unique index on a constant, so the table has only the specified columns.
  - `velocity_band` and `conversion_band` have no CHECK (the prompt listed none).
  - `uv sync` and the image build were slow on this network (first lock about 80 s).
  - Follow-up (doc-only): added `backend/tests/fixtures/README.md` and a sentence in `data/README.md` stating that the test fixtures carry the snapshot's third-party terms; unit tests re-run after.

## 2026-10-11: Phase 1c-1, evidence-card contract (openapi.yaml v0.4.0)

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Contract change only: fix the evidence-card shapes and derivation rules in `openapi.yaml` (0.3.0 to 0.4.0), update `product-spec.md` §4.2 and §6, move the MCP server test pin to 0.4.0, then STOP. No backend, frontend, snapshot or git writes.
- **Produced:**
  - `openapi.yaml`: `comparison`, `snapshot_files`, typed `supporting` (`AcledSupporting`, `OoniSupporting`, `GoogleTransparencySupporting` and row schemas), derivation rules in the three evidence operations' descriptions, snapshot-version example `2026-10-10.1`.
  - `product-spec.md`: new §4.2, one sentence changed in §6.
  - `mcp-server/tests/test_spec_lookup.py`: expected version 0.4.0.
- **Verified:**
  - Column names and null/type profile of the three snapshot tables read from the NDJSON files; they match the prompt.
  - The ACLED 17-week window is 12 weeks before to 4 weeks after the anchor: a stdlib script showed five runs of 17 consecutive weeks, e.g. 2007-10-27 to 2008-02-16 for anchor 2008-01-19.
  - Validator, MCP tests and hook tests: see the report.
- **Not done / open:** the prompt did not define the 17-week window; the 12-before/4-after reading is inferred from the data. `x-provisional` now remains only on `SourceNote`.
- **Follow-up:** Sam confirmed the 17-week window rule (12 weeks before, the anchor, 4 weeks after; `finding_anchors` in `MANIFEST.json`); stated it in `AcledSupporting.series`, renamed the MCP test to `test_version_is_0_4_0`, validator and MCP tests re-run.

## 2026-10-11: Phase 1c-2, the eight endpoints and the `backend` compose service

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** FastAPI app with the eight `/api` operations of `openapi.yaml` v0.4.0, evidence-card logic, unit and integration tests (every response validated against the contract), the `backend` compose service, docs. No `openapi.yaml` change, no `content/`, no git writes, then STOP.
- **Produced:**
  - `backend/app/`: `main.py` (`create_app`), `routers/` (health, timeline, findings, evidence, methodology, common), `schemas.py`, `evidence/` (pure `acled.py`, `ooni.py`, `google.py`; `service.py` fetches rows), `classification.py` (`pre_transition:` parser), `deps.py` (read-only session per request).
  - Tests: `tests/unit/test_evidence.py`, `tests/integration/test_api.py`, test-only fixtures in `tests/fixtures/content_evidence/findings/` (slugs `test-week-<date>`).
  - `backend/Dockerfile` (CMD uvicorn), `docker-compose.yml` (`seed` explicit command, new `backend`), `docker-compose.content.yml` (backend mount), `backend/README.md`, `AGENTS.md` Commands.
  - New dependencies: `fastapi`, `uvicorn`; dev: `openapi-core`, `httpx`.
- **Verified:**
  - `spec_lookup` with no arguments: version 0.4.0, eight operations; each operation read before its router was written.
  - Unit tests 44 passed; integration tests 58 passed, including every real value in the prompt's table, the 17-week ACLED series (2024-03-30 to 2024-07-20), median 11.5, timeline 1523 weeks, CRISIS 27, `ZZ` empty, 404, 422 and both 503 cases. Each response body is validated with `openapi-core`; a deliberately wrong body (`regime_state: BOGUS`) was confirmed to be rejected.
  - `docker compose up -d --build`: seed exited 0, backend started; `curl /api/health` returned `ok` with the seeded counts; `/api/timeline?state=CRISIS` returned 27 weeks.
- **`spec-first-guard`:** it did not block any router write during this build (all eight paths and methods were in the contract before the routers were written). It was not tested adversarially in this step; its own tests are in `agent-hooks/tests`.
- **Not done / open:** see the report (contract points that were hard to implement as written).
- **Follow-up (contract v0.4.1, commit `b738309`):** three contract fixes decided by Sam, in two steps. Step 1 (contract only): `/api/findings` ordered by curated position, ACLED prior-12-week medians nullable, 503 `Error` response on the seven non-health operations, MCP test pinned to 0.4.1; validator and MCP tests (7 passed) run, then stopped for Sam's commit. Step 2 (code): the `NO_SNAPSHOT` 503 response declared on the seven routers, app version 0.4.1, `backend/README.md` updated; added a unit test for the null-median case (anchor with no earlier weeks gives `comparison` null and null medians) and an integration test, validated against the contract, that each of the seven operations returns 503 `{"detail": "No snapshot is loaded."}` when `snapshot_meta` is empty. Verified: unit 45 passed, integration 65 passed, ruff clean. The running compose `backend` image was not rebuilt (only the declared version string and docs changed).

## 2026-10-11: Phase 1c-3 Part A, the `query_snapshot` MCP tool

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Second tool `query_snapshot` in `findings-explorer-tools`: migration `0002_snapshot_reader_role`, sqlglot validation, read-only transaction under `SET LOCAL ROLE snapshot_reader`, 200-row cap, tests and docs; no endpoints, `openapi.yaml`, `ci.yml`, frontend or git writes. Part A only, then STOP.
- **Produced:**
  - `backend/alembic/versions/0002_snapshot_reader_role.py`; backend integration tests for the role and the downgrade; health test head expectation moved to `0002`.
  - `mcp-server/snapshot_query.py`, the tool in `server.py`, dependencies `psycopg[binary]` and `sqlglot`, unit and integration tests, `integration` marker.
  - `.mcp.json` `env` block; `mcp-server/README.md`, `docs/permissions.md`, `AGENTS.md` (rule 5 sentence, Commands rows) updated.
- **Verified:** see the report. The `env` expansion source was checked by the planning side (Claude Code docs, "Environment variable expansion in .mcp.json"); two fetches by this session failed, a third by `curl` returned the same section.
- **Decisions and deviations:** the query runs through a server-side cursor (bounded memory, Postgres itself refuses a second statement). The downgrade drops the role only if no other database depends on it (roles are cluster-wide). `mcp-server/README.md` still said version 0.3.0 and one tool; corrected.

## 2026-10-11: Phase 1c-3 Part B, live demo of `query_snapshot`

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** With the Part A changes left untouched and uncommitted, confirm `findings-explorer-tools` is connected with two tools, call `query_snapshot` through MCP four times (regime count, `DELETE`, `pg_read_file`, `SELECT *`), write `security/mcp-demos/query-snapshot.md`, append this entry, then STOP. No git writes and no edits to any Part A file other than this log.
- **Produced:** `security/mcp-demos/query-snapshot.md`; this entry.
- **Verified:**
  - `git status --short` showed the Part A changes present before and after.
  - `claude mcp list`: `findings-explorer-tools` ✔ Connected; the session exposed `spec_lookup` and `query_snapshot`.
  - Regime counts STABLE 1341, ESCALATION 123, CRISIS 27, CONFLICT 21, MOBILISATION 11 (as expected).
  - `DELETE FROM findings` and `SELECT pg_read_file('PG_VERSION')` were rejected by the parser with an error.
  - `SELECT * FROM regime_weeks` returned `row_count` 200, `truncated` true, 22 columns. The response was too large for the client, so the fields were read from the saved output file with `jq`.
- **Not done / open:** the live demo does not show Postgres itself refusing the same statements; that is covered by the Part A integration tests.

## 2026-10-11: Phase 1d, CI workflow

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** One GitHub Actions workflow running every existing suite, validated locally, plus docs. No deploy, Schemathesis, frontend, app-code change or git write.
- **Stopped once, then continued:** at the lint gate `ruff@0.17.0` found 3 / 10 / 24 findings in `mcp-server` / `agent-hooks` / `ops` because only `backend` had a ruff config. Sam decided: root `ruff.toml` with backend's selection, pinned to the `backend/uv.lock` version (0.17.0), safe `--fix` only, per-file ignores for the 21 leftovers (more than 15). This is the one explicit exception to "no app code changes", for lint only.
- **Produced:** `.github/workflows/ci.yml` (six jobs), `ruff.toml`, safe lint fixes in `ops/export_snapshot.py` and `ops/tests/test_export_snapshot.py` (import and annotation modernisation only), `docs/ci.md`, two `AGENTS.md` Commands rows. No dependency changes (`pytest-cov` is added at run time with `--with`, not to the dev group, so `uv.lock` is untouched).
- **Verified:** suite counts before and after the lint change were identical (hooks 69, ops 53, backend unit 45, backend integration 67, MCP 54). actionlint 1.7.7 clean. The integration steps were reproduced against a throwaway Postgres on port 55433 (migrate, seed, 67 integration tests at 93% coverage, 54 MCP tests with no SKIPPED). The compose-smoke checks were run against the already-running dev stack after `docker compose up -d --build` (no `down`). The SKIPPED guard was checked against a dead database (9 SKIPPED lines).
- **Not done:** no `act` run; the first real run is on GitHub after Sam pushes.

## 2026-10-12: Phase 2a Part A, evidence-reviewer, /new-finding, content/

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Build the `evidence-reviewer` subagent, the `/new-finding` workflow, the `content/` folder and formats, move the content mount into `docker-compose.yml`, add two content checks and docs; no real findings or methodology text, frontend, `openapi.yaml`, deployment or git writes. Part A only, then STOP.
- **Produced:**
  - `content/` (`findings/`, `drafts/`, `README.md`), `docs/reviews/.gitkeep`.
  - `custom-agent/evidence-reviewer/{evidence-reviewer.md,README.md}` and the copy `.claude/agents/evidence-reviewer.md` (tools: `query_snapshot`, `Read`, `Grep`, `Glob`; model `opus`).
  - `agent-capabilities/{new-finding.md,README.md}` and the copy `.claude/commands/new-finding.md`.
  - `docker-compose.yml` content mount for `seed` and `backend`; `docker-compose.content.yml` deleted; `backend/README.md` updated.
  - Unit tests `test_content_language.py`, `test_content_reviewed.py`, `test_agent_sync.py` with fixtures in `backend/tests/fixtures/{content_language,content_reviews}/` (33 new tests).
  - `AGENTS.md` data rule, `docs/permissions.md` subagent section.
- **Verified:** Claude Code docs for subagents and skills fetched and quoted in the report (symlinks are documented only for skill directories, so copies plus a sync test). Backend unit 78 passed, hooks 69, ops 53, MCP 45 passed and 9 skipped, ruff clean. The four workflow queries were parsed with the MCP server's `validate()`.
- **Not verified at first:** Docker Desktop's daemon was not reachable from this WSL distro, so the database-dependent checks waited for a follow-up.
- **Follow-up verification (Docker running):**
  - `docker compose up -d --build`: seed reported `findings loaded: 0`; `/api/health` returned `status: ok`, snapshot `2026-10-10.1`, migration head `0002`, 0 findings.
  - The four workflow queries run through `query_snapshot` for 2024-06-22: regime CRISIS, HIGH confidence, transition detected (protest SEVERE, violence ELEVATED, suppression SEVERE); ACLED 167 events, 56 fatalities, prior-12-week median 55.0 events (11.5 fatalities, 12 prior weeks); OONI 5 tests, highest anomalous rate and count whatsapp (48 of 1217, 0.0394), then telegram, signal, dnscheck and psiphon at zero; Google January - June 2024: 9 requests, 12 items requested for removal, 0 removed legal, 2 removed policy.
  - Suites with the database up: backend integration 67 passed, MCP 54 passed (no skips), backend unit 78, hooks 69, ops 53, ruff clean.
- **Fix after review:** Q3 in `agent-capabilities/new-finding.md` (and its `.claude/commands/` copy) ranked OONI tests by raw rate, so `whatsapp` came first. The contract (`getOoniEvidence`) picks the highest non-null `anomalous_zscore_12w`, ties broken by `test_name`. Q3 now selects both z-scores, orders by `anomalous_zscore_12w DESC NULLS LAST, test_name`, and the workflow states the rule. Re-run for 2024-06-22: signal first (z 1.2371), then whatsapp 0.9337, telegram 0.7691, psiphon 0.0, dnscheck -0.4149. The earlier follow-up bullet above that called whatsapp the top test is superseded by this.
- **Prompt discrepancies:** `AGENTS.md` and `docs/ci.md` did not reference `docker-compose.content.yml` (only `backend/README.md` did); older log entries still mention it as history and were left.

## 2026-10-12: Phase 2a Part B, /new-finding demo

- **Agent:** Claude Code, Claude Sonnet 5.5 (session); `evidence-reviewer` subagent configured as `opus`.
- **Task as given:** Confirm the subagent and command are registered and check `--debug` for unrecognised frontmatter; create a throwaway flawed draft for 2024-06-22; run `/new-finding demo-bad-finding` and expect a STOP; record the demo in `docs/agent-extension-demos/new-finding.md`; delete the draft and its review log. No reviewer or workflow edits, no git writes.
- **Produced:** `docs/agent-extension-demos/new-finding.md`. The draft and `docs/reviews/demo-bad-finding.md` were created and then deleted, as instructed.
- **Result:** the reviewer returned 4 VERIFIED, 1 CORRECTED (median 80 -> 55.0, 12 prior weeks), 1 UNSUPPORTED (causal sentence), 1 EXTERNAL with no source. Every expected verdict appeared. The workflow stopped at step 6 on the UNSUPPORTED row; `content/findings/` held only `.gitkeep`.
- **Verified:** the four step-3 queries ran through `query_snapshot` (167 events, prior median 55.0, signal top OONI test by z-score). `git status --short` after deletion shows neither demo file.
- **Not verified:** the `--debug` output is not visible from inside the session, so unrecognised-frontmatter warnings were not checked. `/agents` in this Claude Code version prints "The /agents wizard has been removed.", so registration was confirmed from the session's agent list and the file frontmatter, not from `/agents`. Sam's later debug-log check found no unrecognised-frontmatter warning; see "Post-run checks" in `docs/agent-extension-demos/new-finding.md`.
- **Observation:** step 2 of the workflow says `sources` may be empty only if the draft makes no real-world event statement, which a mechanical shape check cannot judge. The demo draft has `sources: []` and a real-world claim, and reached the reviewer, which flagged it as EXTERNAL NO SOURCE. The wording may need tightening; the workflow was not changed.
- **Follow-up:** the step 2 `sources` wording in `agent-capabilities/new-finding.md` (and its `.claude/commands/` copy) was tightened as Sam directed: `sources` must be a list, possibly empty, and whether real-world statements have sources is left to the reviewer's EXTERNAL rule. This supersedes the observation above.

## 2026-10-12: Phase 2b-1 Part A, `citations` contract (v0.5.0)

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Part A only: change the contract from v0.4.1 to v0.5.0 with a new required `citations` array on `FindingDetail` (public sources for real-world event statements, distinct from the data-source `sources`), update the MCP version pin and `product-spec.md` §4, then STOP so Sam can commit the contract. No implementation, no git writes.
- **Produced:** `openapi.yaml` (version 0.5.0, status note, schema `Citation`, `citations` required on `FindingDetail`, cross-referencing descriptions on `sources` and `citations`; `FindingSummary` untouched), one sentence in `product-spec.md` §4 item 2, the expected version in `mcp-server/tests/test_spec_lookup.py`.
- **Verified:** `uvx openapi-spec-validator --schema 3.1.0 openapi.yaml` reported OK. MCP tests: 45 passed, 9 skipped (integration tests skipped, database not running).
- **Not done (Part B):** the `0.4.1` strings in `backend/app/main.py`, `backend/README.md` and `mcp-server/README.md`, and everything else in the implementation.

## 2026-10-12: Phase 2b-1 Part B, `citations` implementation

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** After Sam committed the v0.5.0 contract (244d68a): migration 0003, seed validation, API field, rename of the draft key `sources` to `citations` in the content format, `/new-finding` and `evidence-reviewer`, tests and docs; also bump the remaining 0.4.1 pins. No real findings, frontend, `data/snapshot/` or git writes.
- **Produced:**
  - `backend/alembic/versions/0003_finding_citations.py` (`findings.citations` JSONB NOT NULL default `'[]'`); model column; `Citation` schema and `FindingDetail.citations`; router returns them in stored order, `sources` unchanged.
  - `app/seed/content.py`: `citations` required, list (may be empty), items exactly `{claim, citation, url}`, non-blank, `https://`; a `sources` key is rejected with a rename message.
  - `content/README.md`, `agent-capabilities/{new-finding.md,README.md}` (step 7 now compares citation counts), `custom-agent/evidence-reviewer/{evidence-reviewer.md,README.md}`, the `.claude/` copies, a note atop `docs/agent-extension-demos/new-finding.md`, `backend/README.md`, `mcp-server/README.md`. Version pins 0.4.1 -> 0.5.0 in `backend/app/main.py` and both READMEs.
  - Tests: 22 new unit cases in `test_content.py`; integration tests for ordered citations on all five fixture findings (two have test-only citations), the snapshot_reader SELECT, and the 0003 column and downgrade; fixtures given `citations`; health head `0003`.
- **Verified:** `docker compose up -d --build` seeded 0 findings and `/api/health` reports migration head `0003`. Backend unit 101 passed, integration 74 passed (every finding detail response validated with openapi-core), MCP 54 passed with no skips, hooks 69, ops 53, ruff clean.

## 2026-10-14: Phase 2b-2 Part A, `families` contract (v0.6.0)

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** Part A only: change the contract from v0.5.0 to v0.6.0 with a required `families` list on the methodology response and a `PressureFamily` schema, bump the version pins, add one sentence to `product-spec.md`, then STOP so Sam can commit locally. No implementation, no git writes.
- **Produced:** `openapi.yaml` (version 0.6.0, status note, `PressureFamily`, `families` required on `MethodologyResponse`); pins in `backend/app/main.py`, `backend/app/schemas.py` docstring, `backend/README.md`, `mcp-server/README.md`, `mcp-server/tests/test_spec_lookup.py`; one sentence in `product-spec.md` section 4 item 5.
- **Verified:** see the Part A report (validator and MCP tests).
- **Not done (Part B):** reader, models, `content/methodology.yaml`, tests, `frontend/src/api/schema.d.ts` regeneration.

## 2026-10-14: Phase 2b-2 Part B, `families` implementation and methodology text

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** After Sam committed the v0.6.0 contract (b623e5b): read `families` from `content/methodology.yaml`, add the response models, write `content/methodology.yaml` with Sam's approved text exactly as given, update `content/README.md`, add tests, run all suites and compose. No findings, frontend (`schema.d.ts` left for the frontend phase), `data/snapshot/` or git writes.
- **Produced:** `FamilyDefinition` and `PressureFamily` in `backend/app/schemas.py`; `families` read in `backend/app/routers/methodology.py` (absent key gives `[]`); `content/methodology.yaml` verbatim; `content/README.md` format; `backend/tests/unit/test_methodology.py` (4 tests); integration test updates plus `test_methodology_real_content_is_complete`.
- **Verified:** `test_content_language.py` passes on the real file (wording unedited). Backend unit 105 passed, integration 75 passed (responses validated with openapi-core), MCP 54 passed with no skips, hooks 69, ops 53, ruff clean. After `docker compose up -d --build`, `/api/methodology` returns 3 families, 7 regime states, 4 confidence levels, 4 family bands.

## 2026-10-14: `/new-finding finance-bill-2024` (stopped at step 6)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** copy Sam's approved draft to `content/drafts/finance-bill-2024.yaml` with a plain `cp`, then run `/new-finding finance-bill-2024`.
- **Produced:** `content/drafts/finance-bill-2024.yaml` (unedited copy), `docs/reviews/finance-bill-2024.md` (queries Q1 to Q4 with results, reviewer table verbatim). No file in `content/findings/`.
- **Verified:** draft shape passed (ten keys, position 1 free, 4 caveats, 8 citations with https URLs). Reviewer summary: 23 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 8 EXTERNAL (2 without source). Stopped at step 6: rows 25 and 26 (OONI caveat sentences) have no matching citation.
- **Not done:** the finding file and step 7 (seed, curl, content tests).

## 2026-10-14: `/new-finding finance-bill-2024`, second run (finding written, seed failed)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** re-copy the revised draft, then re-run `/new-finding finance-bill-2024`.
- **Produced:** `docs/reviews/finance-bill-2024.md` (overwritten), `content/findings/finance-bill-2024.yaml` (the draft minus its two comment lines; checked with `diff`, 10 keys, 8 citations).
- **Verified:** reviewer found no UNSUPPORTED, CORRECTED or NO SOURCE rows. Step 7 failed at the seed: `week_start_date must be a YYYY-MM-DD date`. The draft quotes `week_start_date` and `published_at`, so they load as strings, and the loader requires native YAML date and datetime values.
- **Not done:** curl checks and content tests (blocked by the seed failure). I did not edit the draft or the finding.

## 2026-10-14: `/new-finding finance-bill-2024`, third run (finding loaded)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** after deleting the unseedable finding and re-copying the draft with unquoted `week_start_date` and `published_at`, re-run `/new-finding finance-bill-2024`.
- **Produced:** `docs/reviews/finance-bill-2024.md` (overwritten), `content/findings/finance-bill-2024.yaml` (draft minus its two comment lines; `diff` clean).
- **Verified:** reviewer 22 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 7 EXTERNAL (0 without source); the count matches its 29-row table. Seed reported `findings loaded: 1`. The finding and its three evidence endpoints returned 200. The API returned 8 citations and 4 caveats, as in the draft. `test_content_language.py` and `test_content_reviewed.py`: 29 passed.

## 2026-10-14: `/new-finding june-july-2025` (stopped at step 6)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** copy the draft to `content/drafts/june-july-2025.yaml` (plain `cp`), `chmod 644 content/drafts/*.yaml`, then run `/new-finding june-july-2025`.
- **Produced:** `content/drafts/june-july-2025.yaml` (unedited copy), `docs/reviews/june-july-2025.md`. No file in `content/findings/`.
- **Verified:** draft shape passed (ten keys, position 2 free, 5 caveats, 8 citations, native date and datetime). Reviewer: 26 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 10 EXTERNAL (1 without source); the count matches its 36-row table. Stopped at step 6 on row 31.
- **Not done:** the finding file and step 7.

## 2026-10-14: `/new-finding june-july-2025`, second run (finding loaded)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** after Sam revised the draft ("only family raised" wording, ninth citation for the STABLE definition) and it was re-copied with a plain `cp`, re-run `/new-finding june-july-2025`.
- **Produced:** `docs/reviews/june-july-2025.md` (overwritten), `content/findings/june-july-2025.yaml` (draft minus its two comment lines; `diff` clean).
- **Verified:** reviewer 29 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 10 EXTERNAL (0 without source); the count matches its 39-row table. Seed reported `findings loaded: 2`. Curl and test results are in the task report.

## 2026-10-14: `/new-finding july-2023` (stopped at step 6)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** copy the draft to `content/drafts/july-2023.yaml` (plain `cp`, mode 644), then run `/new-finding july-2023`.
- **Produced:** `content/drafts/july-2023.yaml` (unedited copy), `docs/reviews/july-2023.md`. No file in `content/findings/`.
- **Verified:** draft shape passed (ten keys, position 3 free, 4 caveats, 7 citations). Reviewer: 23 VERIFIED, 0 CORRECTED, 1 UNSUPPORTED, 7 EXTERNAL (1 without source); the count matches its 31-row table. Stopped at step 6 on the UNSUPPORTED row 2; row 14 is also unsourced.
- **Not done:** the finding file and step 7.

## 2026-10-14: `/new-finding july-2023`, second run (finding loaded)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** after Sam revised the draft (title "OONI signals", protests described as beginning 19 July, caveat 2 reworded, two citations for the CONTESTATION wording) and it was re-copied with a plain `cp`, re-run `/new-finding july-2023`.
- **Produced:** `docs/reviews/july-2023.md` (overwritten), `content/findings/july-2023.yaml` (draft minus its two comment lines; `diff` clean).
- **Verified:** reviewer 24 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 8 EXTERNAL (0 without source); the count matches its 32-row table. Seed reported `findings loaded: 3`. Curl and test results are in the task report.

## 2026-10-14: `/new-finding general-election-2022` (stopped at step 6)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** copy the draft to `content/drafts/general-election-2022.yaml` (plain `cp`, mode 644), then run `/new-finding general-election-2022`.
- **Produced:** `content/drafts/general-election-2022.yaml` (unedited copy), `docs/reviews/general-election-2022.md`. No file in `content/findings/`.
- **Verified:** draft shape passed (ten keys, position 4 free, 4 caveats, 11 citations). Q3 returned zero rows, as the draft says; the first OONI week in the snapshot is 2023-05-27. Reviewer: 20 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 10 EXTERNAL (2 without source); the count matches its 30-row table. Stopped at step 6 on rows 5 and 26.
- **Not done:** the finding file and step 7.

## 2026-10-14: `/new-finding general-election-2022`, second run (finding loaded)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** after Sam revised the draft (teaser "computed only from ACLED offline events", sub-type wording, two added citations) and it was re-copied with a plain `cp`, re-run `/new-finding general-election-2022`.
- **Produced:** `docs/reviews/general-election-2022.md` (overwritten), `content/findings/general-election-2022.yaml` (draft minus its three comment lines).
- **Verified:** reviewer 23 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 12 EXTERNAL (0 without source); the count matches its 35-row table. Seed reported `findings loaded: 4`. The finding and its three evidence endpoints returned 200 (the OONI card returns `has_data: false`, as expected for a week before OONI data begins). The API returned 13 citations and 4 caveats, as in the draft. `test_content_language.py` and `test_content_reviewed.py`: 29 passed.

## 2026-10-14: Phase 2b-3, corrected INSUFFICIENT_DATA, MEDIUM and UNKNOWN definitions

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** replace `content/methodology.yaml` with the supplied text exactly, change one anchor-weeks row in `product-spec.md`, add this entry and run the backend unit tests. No contract, finding, draft, frontend or snapshot changes; no git writes.
- **Produced:** `content/methodology.yaml` (MEDIUM gains one sentence, INSUFFICIENT_DATA's first two sentences are rewritten, UNKNOWN gains two sentences, the header gains two comment lines); the `post-election-violence-2008` row of `product-spec.md` now says the classifier read STABLE (insufficient data) because one family's baseline was too thin to score.
- **Verified:** `sha256sum content/methodology.yaml` matches the prompt's expected value; `uv run --directory backend pytest tests/unit -v` gave 105 passed, including `test_methodology.py` and `test_content_language.py`.

## 2026-10-14: `/new-finding post-election-violence-2008` (stopped at step 6)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** copy the approved draft from the OneDrive folder to `content/drafts/post-election-violence-2008.yaml` (plain `cp`, mode 644; that one file read, nothing else touched), then run `/new-finding post-election-violence-2008`. No git writes; stop when the workflow finishes.
- **Produced:** `content/drafts/post-election-violence-2008.yaml` (unedited copy), `docs/reviews/post-election-violence-2008.md`. No file in `content/findings/`.
- **Verified:** draft shape passed (ten keys, position 5 free, 4 caveats, 24 citations). Q3 and Q4 returned no rows, as the draft says. Reviewer: 36 VERIFIED, 0 CORRECTED, 8 UNSUPPORTED, 6 EXTERNAL (0 without source); the count matches its 50-row table. Stopped at step 6 on rows 6, 11, 14, 23, 29, 33, 46 and 47.
- **Not done:** the finding file and step 7 (seed, curl, tests).

## 2026-10-14: Phase 2b-4, citation-backed statements of CLIO's rules count as EXTERNAL

- **Agent:** Claude Code, Claude Sonnet 5.5.
- **Task as given:** add one sentence group to the reviewer's EXTERNAL definition (both copies), update the matching README row and one sentence in `new-finding.md`, then run the unit tests. No findings, drafts, methodology, contract or git writes.
- **Produced:** the reviewer now files a statement of CLIO's own rules or code as EXTERNAL when a citation points to `content/methodology.yaml` or CLIO's production code (otherwise NO SOURCE); causal wording stays UNSUPPORTED. The `new-finding.md` edit was also made in its canonical copy `agent-capabilities/new-finding.md`, which the prompt did not name, because `test_agent_sync.py` requires the two to match.
- **Verified:** `cmp` on the two reviewer files shows them identical; `uv run --directory backend pytest tests/unit -v` (result in the report).

## 2026-10-15: `/new-finding post-election-violence-2008` (first run stopped at step 3; second run loaded the finding)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Task as given:** copy the revised approved draft from the OneDrive folder over `content/drafts/post-election-violence-2008.yaml` (plain `cp`, mode 644; that one file read, nothing else touched), then run `/new-finding post-election-violence-2008`, replacing the existing untracked finding and review log. No git writes.
- **First run:** stopped at step 3. All four `query_snapshot` calls returned `connection refused` on port 55432 because the database was down, and the workflow stops on a database error. I did not start the database myself. The old untracked finding was moved aside and then restored, because no replacement had been written. Sam started the database and asked for a re-run.
- **Second run:** the old untracked finding was moved aside to the session scratchpad (`old-finding.yaml`), and the workflow ran from step 1.
- **Produced:** `content/drafts/post-election-violence-2008.yaml` (unedited copy), `docs/reviews/post-election-violence-2008.md` (overwritten), `content/findings/post-election-violence-2008.yaml` (draft minus its three comment lines).
- **Verified:** draft shape passed (ten keys, position 5 free after the old file was moved aside). Q3 and Q4 returned no rows, as the draft says. Reviewer: 35 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 17 EXTERNAL (0 without source); the count matches its 52-row table. Seed reported `findings loaded: 5`. The finding and its three evidence endpoints returned 200. The API returned 23 citations, as in the draft (the finding sits under the `finding` key of the response). `test_content_language.py` and `test_content_reviewed.py`: 29 passed, including `test_every_finding_has_a_clean_review`, which also passed when run on its own.
- **Not done:** a human check of the 0.15 margin and the list of MEDIUM conditions (row 12), which rest on `content/methodology.yaml` and CLIO's production SQL, not on the snapshot.

## 2026-10-15: consistency pass over findings 1-4 (three loaded; general-election-2022 stopped at the clean-review test)

- **Agent:** Claude Code, Claude Sonnet 5.5; verdicts by the `evidence-reviewer` subagent.
- **Earlier run today (not part of this pass):** a finance-bill-2024 run from the OONI-only draft stopped at step 6: 21 VERIFIED, 0 CORRECTED, 1 UNSUPPORTED ("because"), 3 EXTERNAL without source (12-week window, qualifying week, own input), 35 rows. Its leftovers were discarded by Sam with `git restore`.
- **First run of this pass:** `finance-bill-2024` stopped at step 6 on one CORRECTED row: "the test whose anomaly rate was furthest above its own 12-week baseline" is ambiguous (by rate gap WhatsApp 0.01847 beats Signal 0.01664; by z-score Signal is first at 1.24). Reviewer: 17 VERIFIED, 1 CORRECTED, 0 UNSUPPORTED, 11 EXTERNAL (0 without source), 29 rows. The old finding was put back unchanged. Sam then restored the drafts' leftovers and revised drafts 1-3 to "<Test>'s anomaly rate had the highest z-score against its own 12-week baseline, at N".
- **Task as given:** for `finance-bill-2024`, `june-july-2025`, `july-2023` and `general-election-2022` in order, copy the revised consistency draft from the OneDrive folder over `content/drafts/<slug>.yaml` (plain `cp`, mode 644; only those four draft files and the prompt read), move the committed finding to the session scratchpad, run `/new-finding <slug>`, and stop at the first problem, restoring that finding. No git writes.
- **Produced (second run):** the four drafts as unedited copies; `docs/reviews/<slug>.md` for all four (overwritten); `content/findings/<slug>.yaml` (draft minus its two comment lines) for `finance-bill-2024`, `june-july-2025` and `july-2023`. For `general-election-2022` the old finding was moved back unchanged.
- **Verified:**
  - finance-bill-2024: 15 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 11 EXTERNAL (0 without source) as printed by the reviewer; its 26-row table actually has 17 VERIFIED and 9 EXTERNAL (noted in the review log). 13 citations and 4 caveats in the API, as in the draft.
  - june-july-2025: 28 VERIFIED, 0, 0, 11 EXTERNAL (0 without source); 39 rows; 12 citations, 5 caveats.
  - july-2023: 24 VERIFIED, 0, 0, 11 EXTERNAL (0 without source); 35 rows; 13 citations, 4 caveats.
  - general-election-2022: 22 VERIFIED, 0, 0, 13 EXTERNAL (0 without source); 35 rows; 15 citations, 4 caveats in the API. Seed, finding and the three evidence endpoints were fine, but `test_every_finding_has_a_clean_review` failed: seven rows (5, 11, 15, 16, 18, 21, 28) carry the verdict text `EXTERNAL (CLIO rule)`, which the test reads as the unknown verdict `EXTERNAL(CLIORULE)`.
  - For the three loaded findings: seed `findings loaded: 5`; each finding and its `/evidence/acled`, `/ooni` and `/google-transparency` returned 200; `test_content_language.py` and `test_content_reviewed.py` gave 29 passed.
- **Not done:** `general-election-2022` is not republished. Its new review log is on disk with the nonstandard verdict text and the old finding is back, so the clean-review test currently fails until Sam decides how to resolve it.
