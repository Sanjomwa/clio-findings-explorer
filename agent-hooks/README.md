# Agent hooks

Claude Code hooks that enforce rules from [AGENTS.md](../AGENTS.md). Python; `block-autonomous-git` uses the standard library only, `spec-first-guard` also needs PyYAML.

## block-autonomous-git

`block_autonomous_git.py` enforces AGENTS.md hard rule 1: the agent never runs git writes. Sam commits, pushes, tags, merges and releases.

### What it blocks

- `git commit`, `push`, `pull`, `tag`, `merge`, `rebase`, `reset`, `cherry-pick`, `revert`, `am`, `update-ref`, `commit-tree`, in every form. That includes `git reset` without `--hard` and read-only uses such as `git tag -l`, because the rule names the subcommand, not a flag.
- `git branch -d`, `-D`, `--delete`, and bundled short flags containing `d` or `D` (for example `-df`).
- `gh pr create` (and its alias `gh pr new`), `gh pr merge`, `gh release create` (and `gh release new`).

Everything else is allowed. That includes `git status`, `diff`, `log`, `show`, `fetch`, `add`, `restore --staged`, `git branch` for listing, and read-only `gh` commands.

### Forms it recognises

- **Chained commands:** `&&`, `||`, `;`, `|`, `&`, newlines, backslash-newline line continuations, `( )` subshells, `{ ...; }` groups, `$( )` and backtick substitution, `<( )` process substitution, and `if` / `while` / `!` prefixes.
- **Prefixes:** environment assignments (`FOO=1 git commit`), and the wrappers `env`, `command`, `builtin`, `exec`, `nohup`, `time`, `sudo`, `nice` and `xargs`, including their common flags.
- **git global options before the subcommand:** `-C <dir>`, `-c <key=value>`, `--git-dir`, `--work-tree`, `--namespace` (with or without `=`), `--no-pager` and so on.
- **Program paths:** `/usr/bin/git`, `git.exe` and `GIT.EXE`. On WSL, `git.exe` runs the Windows git.
- **Quoted text is not a command:** `echo "git commit"`, `grep "git push"` and the body of a quoted heredoc (`<<'EOF'`) are allowed. An unquoted heredoc body is still checked, because the shell expands `$( )` inside it.
- **False-positive traps it allows:** `git add reset.py`, `git log --grep=push`, `git show HEAD:merge.md` and `git commit-graph`.

### Failure behaviour

The hook fails closed: if its input cannot be read, or if the hook itself raises an error, it exits 2 and the command is blocked. This matters because Claude Code only blocks on exit code 2. Any other non-zero exit lets the command run.

A command that `shlex` cannot tokenize, such as `echo it's` with an unbalanced quote, is not blocked automatically. The hook falls back to a conservative text scan and blocks the command only if it mentions a denied operation. This keeps ordinary commands containing apostrophes working. The fallback can over-block, for example `git add` followed by the word `am`.

### Known gaps

This is a string parser for the Bash tool's command text. It catches the common forms, not every way to run git. AGENTS.md hard rule 1 applies whether or not the hook catches a command. It does **not** catch:

- **Commands run by another interpreter:** `sh -c "git commit"`, `bash -c '...'`, `eval "git push"`, `env -S '...'`. The git command there is one quoted string.
- **Commands inside scripts:** a shell script, Makefile or npm script that runs git. The hook only sees `./script.sh`.
- **Child processes:** Python `subprocess`, Node `child_process` and similar.
- **git aliases:** for example `git ci` configured as `commit`, or `git -c alias.x=commit x`.
- **Substitution inside double quotes:** `echo "$(git push)"`. The whole quoted string is one word.
- **Wrapper flags that take a separate value** but are not in the hook's list, for example `sudo -C 3 git push`.
- **Destructive commands that are not on the list:** plain `git restore <file>` (discards working-tree changes), `git checkout -- <file>`, `git stash`, `git clean`, `git branch -m`/`-M`/`-f`, and `gh api` calls that write. AGENTS.md does not forbid these, so the hook allows them.
- **Tools other than Bash:** the hook is registered on the Bash tool only.

## spec-first-guard

`spec_first_guard.py` enforces AGENTS.md hard rule 2: a route's method and path must exist in `openapi.yaml` before the router is written or changed.

### What it checks

It runs before every `Write`, `Edit` and `MultiEdit`. For a `.py` file under `backend/app/routers/` it:

1. rebuilds the file as it would be after the edit (`Write`: the content; `Edit`: the current file with `old_string` replaced, honouring `replace_all`; `MultiEdit`: the edits applied in order);
2. parses it with `ast` and extracts every route: `@<router>.get/post/put/patch/delete/head/options(<path>)` and `@<router>.api_route(<path>, methods=[...])`, with the literal `prefix=` of the `APIRouter(...)` assignment added to the path;
3. compares each `(METHOD, full_path)` with the operations in `openapi.yaml` at the repository root, by exact string match (`{name}` path parameters are written the same way in FastAPI and OpenAPI).

Routes that are not declared block the call. The message lists them, says to edit `openapi.yaml` first, and says to stop so Sam can commit that edit separately.

### What it allows

- Any file that is not a `.py` file under `backend/app/routers/`. The spec is not even opened for these.
- A router file with no routes, or only declared routes.

### Failure behaviour

Fails closed with exit 2 on: unreadable or non-object stdin; an edit that cannot be applied (`old_string` not found, ambiguous without `replace_all`, file missing); a resulting file that does not parse; a path, prefix or `methods` list that is not a literal (routers must use literal paths so the guard can check them); an unreadable or malformed `openapi.yaml`; and any unexpected exception.

### YAML

The hook imports PyYAML only when it has a router file to check. The system `python3` here (3.12.3) has PyYAML 6.0.1, so the hook is registered as plain `python3`, the same as the git hook. Measured per call: 0.18 to 0.22 s. If PyYAML ever goes missing the hook blocks router writes (fail closed) with a message saying so. The fallback is to register it as `uv run --no-project --with pyyaml python3 "${CLAUDE_PROJECT_DIR}/agent-hooks/spec_first_guard.py"`. That form was tried: about 0.25 s once cached, and it also works with `UV_OFFLINE=1` after the first run has cached PyYAML.

### Known gaps

- **Routes registered without decorators:** `router.add_api_route(...)`, `app.add_api_route(...)`, `APIRoute(...)` and `Mount` are not seen.
- **Routers mounted with an extra prefix:** `app.include_router(router, prefix="/api")` changes the real path, but the guard sees only the `APIRouter(prefix=...)` and the decorator path. Keep the full path in the router.
- **Files written outside `backend/app/routers/`:** a route declared in `main.py` or any other module is not checked, nor is a router written through `Bash` (`cat > ...`, `sed -i`).
- **Other name patterns:** only `<name>.get(...)`-style decorators on a plain variable are read. A decorator on an attribute (`self.router.get`) is ignored.
- **Spec side:** only `paths` operations are compared. Parameters, responses and models are not checked against the contract.
- **MultiEdit:** the field names (`edits` with `old_string`, `new_string`, `replace_all`) follow the older Claude Code tool; the current hooks reference documents only `Write` and `Edit`.

## Registration

Both hooks are registered as project hooks in [`.claude/settings.json`](../.claude/settings.json). `spec-first-guard` is a second `PreToolUse` entry with matcher `Write|Edit|MultiEdit`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}/agent-hooks/block_autonomous_git.py\""
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}/agent-hooks/spec_first_guard.py\""
          }
        ]
      }
    ]
  }
}
```

- **Through the interpreter.** It runs via `python3`, so the script does not need its execute bit. Per Sam, the sync script resets file modes to 644; the script is 644 in this repository.
- **Absolute path.** The path uses `${CLAUDE_PROJECT_DIR}`, the project root, so the hook still works after the agent `cd`s into a subdirectory. A relative path would make `python3` fail with exit code 2 from any other directory, which would block every Bash call.
- **Shell form.** With no `args` field the command runs through `sh -c`. `${CLAUDE_PROJECT_DIR}` works there both as Claude Code's path placeholder and as an environment variable.

Claude Code reference: <https://code.claude.com/docs/en/hooks>. Run `/hooks` in a session to see which hooks are loaded.

## Testing

From the repository root:

```
python3 -m unittest discover -s agent-hooks/tests -v
```

The tests run the hook as a subprocess with a PreToolUse JSON payload on stdin, the way Claude Code calls it, and check the exit code and stderr. The `spec-first-guard` tests use a fixture spec under `tests/fixtures/` in a temporary project, plus one test that checks all eight operations of the real `openapi.yaml`. The git-hook tests cover every denied command, the allowed commands, chained, nested and prefixed forms, false-positive traps, untokenizable commands, and fail-closed handling of bad input and internal errors.
