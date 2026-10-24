"""week_start_date in every draft and finding must load as a YAML date, not a quoted string.

The shape check in /new-finding step 2 exists only as instructions in the workflow file, so this
test enforces the same rule on the files themselves.
"""

import datetime
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
FILES = sorted(
    [*(REPO_ROOT / "content" / "drafts").glob("*.yaml"), *(REPO_ROOT / "content" / "findings").glob("*.yaml")]
)


def date_problem(text: str) -> str | None:
    value = yaml.safe_load(text)["week_start_date"]
    if type(value) is not datetime.date:
        return f"week_start_date loaded as {type(value).__name__}: {value!r}"
    return None


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_week_start_date_is_a_yaml_date(path):
    assert date_problem(path.read_text(encoding="utf-8")) is None


def test_files_were_found():
    assert len(FILES) >= 10


def test_quoted_date_is_rejected():
    assert date_problem('week_start_date: "2022-08-06"\n') is not None
    assert date_problem("week_start_date: 2022-08-06\n") is None
