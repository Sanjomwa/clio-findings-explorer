"""Reject causal or targeting wording in curated content (product spec section 9.2, AGENTS.md rule 6).

Scans every content/findings/*.yaml and content/methodology.yaml. With no content this passes
trivially; the inline and fixture cases below prove the scan catches what it is meant to catch.
The deny list necessarily contains the words it forbids; it is the one place they may appear.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "content_language"

# One constant. Each entry is a regex matched case-insensitively on word boundaries.
DENY_LIST = (
    r"caused", r"causing", r"led to", r"resulted in", r"in response to", r"because of",
    r"triggered", r"targeted", r"targeting", r"retaliat\w*", r"crackdown on", r"due to",
    r"as a result of", r"prompted",
)  # fmt: skip
DENY_RE = re.compile(r"(?<![\w-])(?:" + "|".join(DENY_LIST) + r")(?![\w-])", re.IGNORECASE)


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line number, matched phrase) for every deny-list hit."""
    return [
        (number, m.group(0))
        for number, line in enumerate(text.splitlines(), start=1)
        for m in DENY_RE.finditer(line)
    ]


def content_files() -> list[Path]:
    content = REPO_ROOT / "content"
    files = sorted((content / "findings").glob("*.yaml"))
    methodology = content / "methodology.yaml"
    return files + ([methodology] if methodology.is_file() else [])


def test_no_causal_or_targeting_wording_in_content():
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{line}: {phrase!r}"
        for path in content_files()
        for line, phrase in scan_text(path.read_text(encoding="utf-8"))
    ]
    assert not hits, "causal or targeting wording found:\n" + "\n".join(hits)


@pytest.mark.parametrize("phrase", [p.replace(r"\w*", "ion") for p in DENY_LIST])
def test_every_deny_list_entry_is_caught(phrase):
    sentence = f"The week saw an anomaly, {phrase.upper()} something."
    assert scan_text(sentence), phrase


def test_inline_bad_example_is_caught_with_line_and_phrase():
    text = "Fine first line.\nThe outage was Caused By the protests.\n"
    assert scan_text(text) == [(2, "Caused")]


def test_bad_fixture_file_is_caught():
    hits = scan_text((FIXTURES / "bad_finding.yaml").read_text(encoding="utf-8"))
    assert {phrase.lower() for _, phrase in hits} == {"caused", "targeted", "retaliation"}


def test_clean_fixture_file_passes():
    assert scan_text((FIXTURES / "clean_finding.yaml").read_text(encoding="utf-8")) == []
