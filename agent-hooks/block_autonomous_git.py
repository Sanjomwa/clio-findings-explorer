"""PreToolUse hook: block-autonomous-git.

Enforces AGENTS.md hard rule 1 (no git writes by the agent). Claude Code runs
this before every Bash tool call and passes the call as JSON on stdin. Exit 0
lets the command run; exit 2 blocks it and the stderr text is shown to the
agent as the reason.

The hook fails closed: if its input cannot be read, or the hook itself errors,
it exits 2. Standard library only. See agent-hooks/README.md.
"""

import json
import re
import shlex
import sys

# git subcommands the agent may never run, in any form (AGENTS.md hard rule 1).
DENIED_GIT_SUBCOMMANDS = frozenset({
    "commit", "push", "pull", "tag", "merge", "rebase", "reset",
    "cherry-pick", "revert", "am", "update-ref", "commit-tree",
})

# `git branch` is allowed except for deletion.
BRANCH_DELETE_LONG = frozenset({"--delete"})

# gh actions the agent may never run, by command group. `new` is gh's alias
# for `create`. The only gh writes left open are `issue create`, `issue
# comment` and `label create`. A value of ALL denies every action in the group.
ALL = "*"
DENIED_GH_ACTIONS = {
    "issue": frozenset({
        "close", "reopen", "edit", "delete", "transfer", "lock", "unlock",
        "pin", "unpin", "develop",
    }),
    "label": frozenset({"edit", "delete", "clone"}),
    "repo": frozenset({
        "create", "new", "edit", "delete", "archive", "unarchive", "rename",
        "fork", "sync", "set-default",
    }),
    "workflow": frozenset({"run", "enable", "disable"}),
    "run": frozenset({"cancel", "rerun", "delete"}),
    "secret": frozenset({"set", "delete"}),
    "variable": frozenset({"set", "delete"}),
    "release": ALL,
}
# pr: every action is denied except these read-only ones.
ALLOWED_GH_PR_ACTIONS = frozenset({"list", "view", "diff", "checks", "status"})
# Denied whatever follows: `gh api` can write anything.
DENIED_GH_GROUPS = frozenset({"api"})

# git global options that take their value as the next word.
GIT_GLOBAL_OPTS_WITH_VALUE = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--super-prefix", "--config-env",
})

# gh global flags that take their value as the next word.
GH_FLAGS_WITH_VALUE = frozenset({"-R", "--repo", "--hostname"})

# Words that can precede the real command in a segment. The value is the set
# of that wrapper's flags that take a separate argument.
WRAPPERS = {
    "env": frozenset({"-u", "--unset", "-C", "--chdir"}),
    "command": frozenset(),
    "builtin": frozenset(),
    "exec": frozenset({"-a"}),
    "nohup": frozenset(),
    "time": frozenset({"-f", "--format", "-o", "--output"}),
    "sudo": frozenset({"-u", "--user", "-g", "--group", "-h", "--host"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "xargs": frozenset({"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s"}),
}
SHELL_KEYWORDS = frozenset({
    "if", "then", "else", "elif", "do", "while", "until", "!", "{", "}",
})

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Characters shlex returns as operator tokens instead of word characters.
PUNCTUATION = ";&|()<>`\n"

# Heredoc with a quoted delimiter (<<'EOF' or <<"EOF"): the body is literal
# text that the shell does not expand, so it is not checked as commands.
QUOTED_HEREDOC = re.compile(r"(?<!<)<<(-?)[ \t]*(['\"])([^'\"\s]+)\2")

# Backslash-newline line continuation (not preceded by an escaped backslash).
# The shell deletes the pair; shlex would keep the newline inside a word.
LINE_CONTINUATION = re.compile(r"(?<!\\)((?:\\\\)*)\\\n")

# Fallback scan for commands that cannot be tokenized.
FALLBACK_GIT = re.compile(r"(?:^|[^\w.-])git(?:\.exe)?(?![\w.-])(?P<rest>[^\n;&|]*)", re.IGNORECASE)
FALLBACK_GH = re.compile(r"(?:^|[^\w.-])gh(?:\.exe)?(?![\w.-])(?P<rest>[^\n;&|]*)", re.IGNORECASE)

RULE = "AGENTS.md hard rule 1: the agent never runs git writes"
LEAVE_TREE = (
    "Leave the working tree exactly as it is for human review. Do not retry, "
    "rephrase or work around this command; stop and report what you were "
    "about to do. Sam commits, pushes, tags, merges and releases."
)


def strip_quoted_heredocs(command):
    """Remove the bodies of quoted heredocs. Returns the command unchanged if
    a heredoc is never closed."""
    out = []
    pending = []
    for line in command.split("\n"):
        if pending:
            strip_tabs, delimiter = pending[0]
            candidate = line.lstrip("\t") if strip_tabs else line
            if candidate == delimiter:
                pending.pop(0)
            continue
        out.append(line)
        pending = [(m.group(1) == "-", m.group(3)) for m in QUOTED_HEREDOC.finditer(line)]
    if pending:
        return command
    return "\n".join(out)


def split_segments(command):
    """Split a shell command into simple-command word lists.

    Splits on ; & && | || newlines, ( ), $( ), backticks and process
    substitution. Redirection targets are dropped. Raises ValueError when the
    command cannot be tokenized (for example an unbalanced quote).
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""

    segments = [[]]
    skip_next = False
    for token in lexer:
        is_operator = token != "" and all(c in PUNCTUATION for c in token)
        if is_operator:
            is_separator = any(c in ";|()`\n" for c in token) or (
                "&" in token and not any(c in "<>" for c in token)
            )
            if is_separator:
                segments.append([])
                skip_next = False
            else:
                # Redirection: a preceding fd number (the 2 in 2>) belongs to
                # it, and the next word is its target.
                if segments[-1] and segments[-1][-1].isdigit():
                    segments[-1].pop()
                skip_next = True
            continue
        if skip_next:
            skip_next = False
            continue
        segments[-1].append(token)
    return [s for s in segments if s]


def program_name(word):
    """Basename of a command word, with a Windows .exe suffix removed."""
    name = re.split(r"[\\/]", word)[-1]
    if name.lower().endswith(".exe"):
        name = name[:-4].lower()
    return name


def strip_prefixes(words):
    """Drop env assignments, shell keywords and wrapper commands from the
    front of a segment, returning the words from the real program onward."""
    i = 0
    while i < len(words):
        word = words[i]
        if ENV_ASSIGNMENT.match(word) or word in SHELL_KEYWORDS:
            i += 1
            continue
        wrapper = program_name(word)
        if wrapper in WRAPPERS:
            takes_value = WRAPPERS[wrapper]
            i += 1
            while i < len(words):
                arg = words[i]
                if wrapper == "env" and ENV_ASSIGNMENT.match(arg):
                    i += 1
                elif arg.startswith("-") and arg != "-":
                    i += 2 if arg in takes_value else 1
                else:
                    break
            continue
        break
    return words[i:]


def git_violation(args):
    """Return the denied git subcommand in `args` (words after `git`), or None."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in GIT_GLOBAL_OPTS_WITH_VALUE:
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            break
    if i >= len(args):
        return None
    subcommand = args[i]
    if subcommand in DENIED_GIT_SUBCOMMANDS:
        return subcommand
    if subcommand == "branch":
        for arg in args[i + 1:]:
            if arg == "--":
                break
            if arg in BRANCH_DELETE_LONG:
                return "branch --delete"
            if arg.startswith("-") and not arg.startswith("--") and (
                "d" in arg or "D" in arg
            ):
                return f"branch {arg}"
    return None


def gh_violation(args):
    """Return the denied gh command in `args` (words after `gh`), or None."""
    positionals = []
    i = 0
    while i < len(args) and len(positionals) < 2:
        arg = args[i]
        if arg in GH_FLAGS_WITH_VALUE:
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            positionals.append(arg)
            i += 1
    if not positionals:
        return None
    group = positionals[0]
    if group in DENIED_GH_GROUPS:
        return group
    action = positionals[1] if len(positionals) > 1 else None
    if group == "pr":
        if action is not None and action not in ALLOWED_GH_PR_ACTIONS:
            return f"pr {action}"
        return None
    denied = DENIED_GH_ACTIONS.get(group)
    if denied == ALL:
        return " ".join(positionals)
    if denied and action in denied:
        return f"{group} {action}"
    return None


def fallback_violation(command):
    """Conservative scan for a command that cannot be tokenized: report any
    mention of a denied operation."""
    for match in FALLBACK_GIT.finditer(command):
        words = re.findall(r"[\w.-]+", match.group("rest"))
        for word in words:
            if word in DENIED_GIT_SUBCOMMANDS:
                return f"git {word}"
        if "branch" in words and re.search(r"(?:^|\s)(-[A-Za-z]*[dD][A-Za-z]*|--delete)\b", match.group("rest")):
            return "git branch delete"
    for match in FALLBACK_GH.finditer(command):
        words = re.findall(r"[\w.-]+", match.group("rest"))
        if "api" in words:
            return "gh api"
        for first, second in zip(words, words[1:], strict=False):
            found = gh_violation([first, second])
            if found:
                return f"gh {found}"
        if "release" in words:
            return "gh release"
    return None


def find_violation(command):
    """Return (description, tokenized) for the first denied operation in a
    shell command, or None if the command is allowed."""
    try:
        joined = LINE_CONTINUATION.sub(r"\1", strip_quoted_heredocs(command))
        segments = split_segments(joined)
    except ValueError:
        found = fallback_violation(command)
        return (found, False) if found else None
    for words in segments:
        words = strip_prefixes(words)
        if not words:
            continue
        name = program_name(words[0])
        if name == "git":
            found = git_violation(words[1:])
            if found:
                return (f"git {found}", True)
        elif name == "gh":
            found = gh_violation(words[1:])
            if found:
                return (f"gh {found}", True)
    return None


def block(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
        if payload.get("tool_name", "Bash") != "Bash":
            return 0
        command = payload["tool_input"]["command"]
        if not isinstance(command, str):
            raise ValueError("tool_input.command is not a string")
    except Exception as exc:  # fail closed on any unreadable input
        block(
            f"Blocked by block-autonomous-git: could not read the hook input ({exc!r}), "
            f"so the command is blocked by default ({RULE}). {LEAVE_TREE}"
        )

    result = find_violation(command)
    if result is None:
        return 0
    found, tokenized = result
    if tokenized:
        block(f"Blocked by block-autonomous-git: `{found}` is not allowed ({RULE}). {LEAVE_TREE}")
    block(
        f"Blocked by block-autonomous-git: the command could not be parsed and it "
        f"mentions `{found}`, so it is blocked by default ({RULE}). {LEAVE_TREE}"
    )


def entrypoint():
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # fail closed on any bug in the hook itself
        print(
            f"Blocked by block-autonomous-git: the hook failed ({exc!r}), so the command "
            f"is blocked by default ({RULE}). {LEAVE_TREE}",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    entrypoint()
