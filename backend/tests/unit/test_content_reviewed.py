"""Every content/findings/<slug>.yaml needs a clean verdict log at docs/reviews/<slug>.md.

Resolution marker: the word RESOLVED (uppercase) in the evidence cell of a verdict-table row.
A person adds it after fixing the draft (CORRECTED) or attaching a source (EXTERNAL, NO SOURCE);
/new-finding never adds it. An UNSUPPORTED row can never be resolved by the marker: the
assertion has to leave the finding and the review has to be re-run.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "content_reviews"
VERDICTS = {"VERIFIED", "CORRECTED", "UNSUPPORTED", "EXTERNAL"}
COUNT_ORDER = ["VERIFIED", "CORRECTED", "UNSUPPORTED", "EXTERNAL"]
MARKER = re.compile(r"\bRESOLVED\b")
COUNTED = re.compile(
    r"^Counted: (\d+) VERIFIED, (\d+) CORRECTED, (\d+) UNSUPPORTED, (\d+) EXTERNAL"
    r" \((\d+) without source\)\.$",
    re.M,
)


def table_rows(text: str) -> list[tuple[str, str, str]]:
    """(row number, verdict, evidence) for each data row of the verdict table."""
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        verdict = re.sub(r"[`*_ ]", "", cells[2]).upper()
        rows.append((cells[0], verdict, "|".join(cells[3:])))
    return rows


def counted_problems(name: str, text: str) -> list[str]:
    """A log with a `Counted:` line must have counts equal to its table; one without passes."""
    lines = [line for line in text.splitlines() if line.startswith("Counted:")]
    if not lines:
        return []
    match = COUNTED.match(lines[0]) if len(lines) == 1 else None
    if not match:
        return [f"{name}: malformed or repeated Counted line"]
    rows = table_rows(text)
    expected = [sum(v == verdict for _, v, _ in rows) for verdict in COUNT_ORDER]
    expected.append(sum(v == "EXTERNAL" and "NO SOURCE" in e for _, v, e in rows))
    got = [int(g) for g in match.groups()]
    if got != expected:
        return [f"{name}: Counted line {got} does not match the table {expected}"]
    return []


def review_problems(review: Path) -> list[str]:
    """Return what is wrong with a review log; an empty list means it is clean."""
    if not review.is_file():
        return [f"{review.name} does not exist"]
    rows = table_rows(review.read_text(encoding="utf-8"))
    if not rows:
        return [f"{review.name}: no verdict table rows"]
    problems = counted_problems(review.name, review.read_text(encoding="utf-8"))
    for number, verdict, evidence in rows:
        resolved = bool(MARKER.search(evidence))
        if verdict not in VERDICTS:
            problems.append(f"{review.name} row {number}: unknown verdict {verdict!r}")
        elif verdict == "UNSUPPORTED":
            problems.append(f"{review.name} row {number}: UNSUPPORTED")
        elif verdict == "CORRECTED" and not resolved:
            problems.append(f"{review.name} row {number}: CORRECTED and not marked RESOLVED")
        elif verdict == "EXTERNAL" and "NO SOURCE" in evidence and not resolved:
            problems.append(f"{review.name} row {number}: EXTERNAL with NO SOURCE, not RESOLVED")
    return problems


def finding_problems(findings_dir: Path, reviews_dir: Path) -> list[str]:
    return [
        problem
        for path in sorted(findings_dir.glob("*.yaml"))
        for problem in review_problems(reviews_dir / f"{path.stem}.md")
    ]


def test_every_finding_has_a_clean_review():
    problems = finding_problems(REPO_ROOT / "content" / "findings", REPO_ROOT / "docs" / "reviews")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    "name",
    ["ok-verified", "ok-external-sourced", "ok-corrected-resolved", "ok-external-resolved", "ok-counted"],
)
def test_clean_reviews_pass(name):
    assert review_problems(FIXTURES / f"{name}.md") == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("bad-unsupported", "UNSUPPORTED"),
        ("bad-unsupported-resolved", "UNSUPPORTED"),
        ("bad-corrected-unresolved", "CORRECTED and not marked RESOLVED"),
        ("bad-external-nosource", "EXTERNAL with NO SOURCE"),
        ("bad-empty", "no verdict table rows"),
        ("bad-counted-mismatch", "does not match the table"),
        ("bad-counted-malformed", "malformed or repeated Counted line"),
    ],
)
def test_bad_reviews_fail(name, expected):
    problems = review_problems(FIXTURES / f"{name}.md")
    assert len(problems) == 1 and expected in problems[0], problems


def test_missing_review_fails(tmp_path):
    (tmp_path / "findings").mkdir()
    (tmp_path / "findings" / "no-review-here.yaml").write_text("slug: no-review-here\n")
    problems = finding_problems(tmp_path / "findings", tmp_path / "reviews")
    assert problems == ["no-review-here.md does not exist"]


def test_logs_without_a_counted_line_still_pass():
    text = (FIXTURES / "ok-verified.md").read_text(encoding="utf-8")
    assert "Counted:" not in text and counted_problems("x.md", text) == []


def test_the_counting_command_in_new_finding_matches_the_test_logic():
    """Run the command given in the workflow over a fixture and compare with the table."""
    import subprocess
    import sys

    text = (REPO_ROOT / "agent-capabilities" / "new-finding.md").read_text(encoding="utf-8")
    command = re.search(r"^python3 -c '(.*)' docs/reviews/<slug>\.md$", text, re.M).group(1)
    fixture = FIXTURES / "ok-external-sourced.md"
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", command, str(fixture)], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert COUNTED.match(out), out
    assert counted_problems("x.md", fixture.read_text(encoding="utf-8") + out + "\n") == []
