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
