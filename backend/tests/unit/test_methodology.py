"""The methodology reader and its response models (no database)."""

import pytest
import yaml
from pydantic import ValidationError

from app.routers.methodology import REPO_ROOT, load_curated_definitions
from app.schemas import FamilyDefinition


def test_reader_returns_families_when_present(tmp_path, monkeypatch):
    (tmp_path / "methodology.yaml").write_text(
        "families:\n  - {family: suppression, definition: test-only}\n"
    )
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path))
    curated = load_curated_definitions()
    assert [FamilyDefinition.model_validate(f).family for f in curated["families"]] == [
        "suppression"
    ]


def test_absent_families_key_gives_empty_list(tmp_path, monkeypatch):
    (tmp_path / "methodology.yaml").write_text("regime_states: []\n")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path))
    assert load_curated_definitions().get("families", []) == []


def test_unknown_family_name_fails():
    with pytest.raises(ValidationError):
        FamilyDefinition.model_validate({"family": "internet", "definition": "test-only"})


def test_real_methodology_file_parses_with_expected_counts():
    data = yaml.safe_load((REPO_ROOT / "content" / "methodology.yaml").read_text("utf-8"))
    assert [len(data[k]) for k in ("families", "regime_states", "confidence_levels", "family_bands")] == [3, 7, 4, 4]
    for f in data["families"]:
        FamilyDefinition.model_validate(f)
