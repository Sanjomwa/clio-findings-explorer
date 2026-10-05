# Agent hooks

Claude Code hooks that enforce rules from [AGENTS.md](../AGENTS.md). Standard library Python only.

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

## Registration

Registered as a project hook in [`.claude/settings.json`](../.claude/settings.json):

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

The tests run the hook as a subprocess with a PreToolUse JSON payload on stdin, the way Claude Code calls it, and check the exit code and stderr. They cover every denied command, the allowed commands, chained, nested and prefixed forms, false-positive traps, untokenizable commands, and fail-closed handling of bad input and internal errors.
