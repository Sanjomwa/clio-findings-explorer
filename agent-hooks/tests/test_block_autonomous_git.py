"""Tests for agent-hooks/block_autonomous_git.py.

Each case runs the hook as a subprocess with a PreToolUse JSON payload on
stdin, exactly as Claude Code does, and checks the exit code and stderr.

Run from the repository root:
    python3 -m unittest discover -s agent-hooks/tests -v
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "block_autonomous_git.py"


def run_hook(stdin_text):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )


def payload(command, tool_name="Bash"):
    return json.dumps({
        "session_id": "test",
        "cwd": "/tmp",
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"command": command, "description": "test"},
    })


class HookTestCase(unittest.TestCase):
    def assertBlocked(self, command):
        result = run_hook(payload(command))
        self.assertEqual(result.returncode, 2, f"expected block: {command!r}\nstderr: {result.stderr}")
        self.assertIn("AGENTS.md hard rule 1", result.stderr)
        self.assertIn("Leave the working tree exactly as it is for human review", result.stderr)
        return result

    def assertAllowed(self, command):
        result = run_hook(payload(command))
        self.assertEqual(result.returncode, 0, f"expected allow: {command!r}\nstderr: {result.stderr}")
        self.assertEqual(result.stderr, "")


class TestBlockedGitCommands(HookTestCase):
    """Every entry in AGENTS.md hard rule 1."""

    def test_every_denied_subcommand(self):
        for command in [
            'git commit -m "x"',
            "git commit --allow-empty -m 'hook test'",
            "git push",
            "git push origin main --force",
            "git pull",
            "git pull --rebase",
            "git tag v1.0",
            "git tag -l",
            "git merge feature",
            "git rebase main",
            "git reset --hard",
            "git reset HEAD~1",
            "git reset --soft HEAD~1",
            "git reset",
            "git cherry-pick abc123",
            "git revert HEAD",
            "git am patch.mbox",
            "git update-ref refs/heads/main abc123",
            "git commit-tree abc123 -m x",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_branch_delete(self):
        for command in [
            "git branch -d old",
            "git branch -D old",
            "git branch --delete old",
            "git branch -df old",
            "git branch -vD old",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_message_names_the_command(self):
        result = self.assertBlocked("git status && git push origin main")
        self.assertIn("`git push`", result.stderr)


class TestBlockedGhCommands(HookTestCase):
    def test_every_denied_gh_command(self):
        for command in [
            "gh pr create --fill",
            "gh pr new --fill",
            "gh pr merge 3 --squash",
            "gh pr merge --merge 3",
            "gh -R owner/repo pr merge 3",
            "gh --repo=owner/repo pr create",
            "gh release create v1.0",
            "gh release new v1.0",
            "gh release list",
            "gh release view v1",
            "gh release delete v1",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_issue_writes_other_than_create_and_comment(self):
        for action in [
            "close", "reopen", "edit", "delete", "transfer", "lock", "unlock",
            "pin", "unpin", "develop",
        ]:
            with self.subTest(action=action):
                self.assertBlocked(f"gh issue {action} 7")

    def test_label_repo_workflow_run_secret_variable_writes(self):
        for command in [
            "gh label edit bug --color fff",
            "gh label delete bug",
            "gh label clone owner/repo",
            "gh repo create x",
            "gh repo edit --visibility private",
            "gh repo delete x --yes",
            "gh repo archive x",
            "gh repo unarchive x",
            "gh repo rename y",
            "gh repo fork",
            "gh repo sync",
            "gh repo set-default owner/repo",
            "gh workflow run ci.yml",
            "gh workflow enable ci.yml",
            "gh workflow disable ci.yml",
            "gh run cancel 1",
            "gh run rerun 1",
            "gh run delete 1",
            "gh secret set X",
            "gh secret delete X",
            "gh variable set X",
            "gh variable delete X",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_pr_actions_other_than_read_only(self):
        for command in [
            "gh pr close 3",
            "gh pr comment 3 --body x",
            "gh pr edit 3",
            "gh pr ready 3",
            "gh pr review 3 --approve",
            "gh pr checkout 3",
            "gh pr reopen 3",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_gh_api_is_always_blocked(self):
        for command in [
            "gh api repos/o/r/issues",
            "gh api -X DELETE repos/o/r",
            "gh -R o/r api graphql -f query=x",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_gh_denials_inside_chains_substitution_and_env(self):
        for command in [
            "gh issue list && gh issue close 7",
            "echo $(gh issue close 7)",
            "env GH_TOKEN=x gh issue close 7",
            "env gh api repos/o/r",
            "ls; gh repo delete x",
            "echo 'unterminated && gh issue close 7",
            "echo 'unterminated && gh api repos/o/r",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)


class TestChainedAndNestedForms(HookTestCase):
    def test_separators(self):
        for command in [
            "git status && git commit -m x",
            "git status || git commit -m x",
            "git status; git commit -m x",
            "git status | git commit -F -",
            "sleep 1 & git push",
            "git status\ngit commit -m x",
            "git status\n\ngit tag v1",
            "ls -la && git add . && git commit -m x && git push",
            "echo ok;git push",
            "true&&git push",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_subshells_and_substitution(self):
        for command in [
            "(cd frontend && git commit -m x)",
            "echo $(git commit -m x)",
            "echo `git commit -m x`",
            "{ git commit -m x; }",
            "cat <(git pull)",
            "if git push; then echo ok; fi",
            "! git merge feature",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_line_continuations(self):
        for command in [
            "git status && \\\ngit commit -m x",
            "git \\\n  commit -m x",
            "git -C /d \\\n  push",
            "FOO=1 \\\n  git push",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)
        self.assertAllowed("git status \\\n  --short")

    def test_redirections_do_not_hide_the_command(self):
        for command in [
            "git commit -m x > /dev/null 2>&1",
            "2>/dev/null git push",
            "ls 2>&1 | git merge feature",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)


class TestPrefixedForms(HookTestCase):
    def test_env_and_wrapper_prefixes(self):
        for command in [
            "GIT_AUTHOR_NAME=x git commit -m x",
            "FOO=1 BAR=2 git push",
            "env FOO=1 git commit -m x",
            "env -u HOME git push",
            "command git commit -m x",
            "exec git push",
            "nohup git push",
            "time git commit -m x",
            "sudo git push",
            "sudo -u sam git push",
            "nice -n 5 git push",
            "echo msg | xargs git commit -m",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_git_global_options(self):
        for command in [
            "git -C /some/dir commit -m x",
            "git -C . push",
            "git -c user.name=x commit -m x",
            "git --git-dir=.git commit -m x",
            "git --git-dir .git --work-tree . commit -m x",
            "git --no-pager commit -m x",
            "git -C a -c k=v --no-pager push",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_program_paths(self):
        for command in [
            "/usr/bin/git commit -m x",
            "git.exe commit -m x",
            "GIT.EXE push",
            "/mnt/c/Program\\ Files/Git/cmd/git.exe push",
            "gh.exe pr merge 3",
        ]:
            with self.subTest(command=command):
                self.assertBlocked(command)


class TestAllowedCommands(HookTestCase):
    def test_allowed_git_commands(self):
        for command in [
            "git status",
            "git status --short",
            "git diff",
            "git diff --staged",
            "git log --oneline -5",
            "git log --grep=push",
            "git log --merge",
            "git show HEAD",
            "git show HEAD:merge.md",
            "git fetch",
            "git fetch origin",
            "git add .",
            "git add AGENTS.md docs/",
            "git restore --staged AGENTS.md",
            "git branch",
            "git branch -a",
            "git branch --list",
            "git -C /some/dir status",
            "git --no-pager log",
            "git check-ignore -v .env",
            "git commit-graph verify",
            "git rev-parse HEAD",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_allowed_gh_commands(self):
        for command in [
            "gh pr view 3",
            "gh pr list",
            "gh pr status",
            "gh pr diff 3",
            "gh pr checks 3",
            "gh issue create --title x",
            "gh issue new --title x",
            "gh issue comment 7 --body-file notes.md",
            "gh issue view 7 --comments",
            "gh issue list --state all",
            "gh issue status",
            "gh label create agent-task --description x",
            "gh label list",
            "gh auth status",
            "gh repo view o/r --json visibility",
            "gh run list",
            "gh -R o/r issue view 7",
            "env GH_PAGER= gh issue comment 7 --body-file f",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_false_positive_traps(self):
        for command in [
            'echo "git commit"',
            "echo 'git push origin main'",
            'grep -r "git push" docs/',
            "git add commit.py reset.py",
            "git add tag",
            "ls merge/ rebase/",
            "python3 -m unittest discover -s agent-hooks/tests -v",
            "cat docs/ai-workflow-log.md",
            "digit commit",
            "legit push",
            "mygit commit",
            "echo it's fine",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_quoted_heredoc_body_is_not_a_command(self):
        self.assertAllowed("cat <<'EOF' > notes.md\nRun git commit later; Sam's job.\nEOF\necho done")
        self.assertAllowed('cat <<"EOF" > notes.md\ngit push\nEOF')

    def test_command_after_quoted_heredoc_is_checked(self):
        self.assertBlocked("cat <<'EOF' > notes.md\ntext\nEOF\ngit commit -m x")

    def test_other_commands(self):
        for command in ["ls -la", "npm test", "uv --version", "pwd", ""]:
            with self.subTest(command=command):
                self.assertAllowed(command)


class TestUntokenizableCommands(HookTestCase):
    """A command shlex cannot split falls back to a conservative text scan."""

    def test_untokenizable_with_denied_operation_is_blocked(self):
        result = self.assertBlocked("echo 'unterminated && git commit -m x")
        self.assertIn("could not be parsed", result.stderr)

    def test_unquoted_heredoc_with_denied_operation_is_blocked(self):
        # The body of an unquoted heredoc is expanded by the shell, so $( )
        # inside it runs; the body is checked, not skipped.
        self.assertBlocked("cat <<EOF\nit's $(git push)\nEOF")

    def test_untokenizable_without_denied_operation_is_allowed(self):
        self.assertAllowed("echo it's 'unbalanced")


class TestInputFaultsFailClosed(unittest.TestCase):
    def assertFailClosed(self, stdin_text):
        result = run_hook(stdin_text)
        self.assertEqual(result.returncode, 2, f"stdin: {stdin_text!r}")
        self.assertIn("could not read the hook input", result.stderr)
        self.assertIn("Leave the working tree exactly as it is for human review", result.stderr)

    def test_malformed_json(self):
        self.assertFailClosed("{not json")

    def test_empty_stdin(self):
        self.assertFailClosed("")

    def test_json_not_an_object(self):
        self.assertFailClosed("[1, 2]")

    def test_missing_tool_input(self):
        self.assertFailClosed(json.dumps({"tool_name": "Bash"}))

    def test_missing_command(self):
        self.assertFailClosed(json.dumps({"tool_name": "Bash", "tool_input": {}}))

    def test_non_string_command(self):
        self.assertFailClosed(json.dumps({"tool_name": "Bash", "tool_input": {"command": ["git", "push"]}}))

    def test_other_tool_is_allowed(self):
        result = run_hook(payload("git push", tool_name="Read"))
        self.assertEqual(result.returncode, 0)

    def test_internal_error_fails_closed(self):
        # Simulate a bug in the hook: an uncaught exception would exit 1,
        # which Claude Code does not treat as a block.
        script = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "import block_autonomous_git as h;"
            "h.find_violation = lambda command: 1 / 0;"
            "h.entrypoint()"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(HOOK.parent)],
            input=payload("ls"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("the hook failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
