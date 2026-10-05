# Demo: block-autonomous-git blocks an agent commit

**Date:** 2026-10-05, 14:36 EAT (+03:00)
**Agent:** Claude Code, Claude Opus 5.5
**Hook:** [`agent-hooks/block_autonomous_git.py`](../../agent-hooks/block_autonomous_git.py), registered in [`.claude/settings.json`](../../.claude/settings.json) as a PreToolUse hook on Bash
**Rule enforced:** AGENTS.md hard rule 1 (no git writes by the agent)

## Setup

The hook and its registration were created in Part B. Sam restarted the Claude Code session and confirmed with `/hooks` that the PreToolUse / Bash entry was listed. The repository had no commits at the start of the demo.

Registration as loaded:

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

## 1. The agent tries to commit

Command sent through the Bash tool:

```
git commit --allow-empty -m "hook test"
```

Result returned to the agent (the command did not run):

```
PreToolUse:Bash hook error: [python3 "${CLAUDE_PROJECT_DIR}/agent-hooks/block_autonomous_git.py"]: Blocked by block-autonomous-git: `git commit` is not allowed (AGENTS.md hard rule 1: the agent never runs git writes). Leave the working tree exactly as it is for human review. Do not retry, rephrase or work around this command; stop and report what you were about to do. Sam commits, pushes, tags, merges and releases.
```

## 2. Read commands still work, and no commit was made

```
$ git status; echo "exit=$?"; git log 2>&1; echo "exit=$?"
On branch main

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.claude/
	.env.example
	.gitignore
	AGENTS.md
	CLAUDE.md
	LICENSE
	README.md
	agent-hooks/
	docs/
	openapi.yaml
	product-spec.md

nothing added to commit but untracked files present (use "git add" to track)
exit=0
fatal: your current branch 'main' does not have any commits yet
exit=128
```

`git status` ran normally (exit 0). `git log` still reports no commits, so the empty commit was never created. The `git log` exit code 128 is git's normal response on a branch with no commits, not a hook block.

## What this shows and does not show

- It shows the registered hook is loaded in a fresh session and blocks a plain `git commit` on the Bash tool before it runs, while allowing read commands.
- The other blocked forms (chained, prefixed, `git -C`, `gh pr merge` and so on) are covered by the unit tests in `agent-hooks/tests/`, not by this live demo.
- Known gaps (`sh -c`, `eval`, scripts, subprocesses, git aliases) are listed in [`agent-hooks/README.md`](../../agent-hooks/README.md). AGENTS.md hard rule 1 applies whether or not the hook catches a command.
