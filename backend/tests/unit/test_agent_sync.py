"""The Claude Code copies of the reviewer and the workflow must match their canonical files.

The Claude Code docs confirm symlinks only for skill directories, not for agent or command
files, so .claude/ holds copies. Edit the canonical file, then copy it.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PAIRS = [
    ("custom-agent/evidence-reviewer/evidence-reviewer.md", ".claude/agents/evidence-reviewer.md"),
    ("agent-capabilities/new-finding.md", ".claude/commands/new-finding.md"),
]
REVIEWER_TOOLS = {
    "mcp__findings-explorer-tools__query_snapshot", "Read", "Grep", "Glob",
}  # fmt: skip


def differs(a: Path, b: Path) -> bool:
    return not b.is_file() or a.read_bytes() != b.read_bytes()


@pytest.mark.parametrize(("canonical", "copy"), PAIRS)
def test_copy_matches_canonical(canonical, copy):
    assert not differs(REPO_ROOT / canonical, REPO_ROOT / copy), f"{copy} differs from {canonical}"


def test_differs_detects_a_difference(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("one\n")
    assert differs(a, b)  # missing copy
    b.write_text("two\n")
    assert differs(a, b)  # changed copy
    b.write_text("one\n")
    assert not differs(a, b)


def test_reviewer_frontmatter_is_read_only_allowlist():
    text = (REPO_ROOT / PAIRS[0][0]).read_text(encoding="utf-8")
    front = yaml.safe_load(re.match(r"---\n(.*?)\n---\n", text, re.S).group(1))
    tools = {t.strip() for t in front["tools"].split(",")}
    assert tools == REVIEWER_TOOLS
    assert front["name"] == "evidence-reviewer" and front["model"] == "opus"
    assert not tools & {"Write", "Edit", "MultiEdit", "Bash", "WebFetch", "WebSearch", "Agent"}
