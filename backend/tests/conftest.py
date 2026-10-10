import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def snapshot_copy(tmp_path: Path) -> Path:
    """A writable copy of the fixture snapshot (the real data/snapshot/ is never touched)."""
    dest = tmp_path / "snapshot"
    shutil.copytree(FIXTURES / "snapshot", dest)
    return dest


@pytest.fixture
def content_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "content"
    shutil.copytree(FIXTURES / "content", dest)
    return dest
