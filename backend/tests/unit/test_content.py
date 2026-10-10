import pytest
import yaml

from app.seed import SeedError
from app.seed.content import load_content, parse_finding

FILE = "findings/fixture-finding.yaml"


def mutate(content_copy, edit, name="fixture-finding"):
    path = content_copy / "findings" / "fixture-finding.yaml"
    data = yaml.safe_load(path.read_text())
    edit(data)
    target = content_copy / "findings" / f"{name}.yaml"
    target.write_text(yaml.safe_dump(data))
    if target != path:
        path.unlink()
    return target


def test_valid_file(content_copy):
    docs = load_content(content_copy)
    assert [d.slug for d in docs] == ["fixture-finding"]
    assert [c["severity"] for c in docs[0].caveats] == ["limitation", "do_not_conclude"]
    assert docs[0].published_at.tzinfo is not None


def test_missing_content_dir_returns_none(tmp_path):
    assert load_content(tmp_path / "content") is None


def test_unknown_key(content_copy):
    path = mutate(content_copy, lambda d: d.update(extra="x"))
    with pytest.raises(SeedError, match="unknown keys"):
        parse_finding(path)


def test_missing_key(content_copy):
    path = mutate(content_copy, lambda d: d.pop("teaser"))
    with pytest.raises(SeedError, match="missing keys"):
        parse_finding(path)


def test_empty_caveats(content_copy):
    path = mutate(content_copy, lambda d: d.update(caveats=[]))
    with pytest.raises(SeedError, match="non-empty list"):
        parse_finding(path)


def test_bad_severity(content_copy):
    path = mutate(content_copy, lambda d: d["caveats"][0].update(severity="warning"))
    with pytest.raises(SeedError, match="severity"):
        parse_finding(path)


def test_blank_caveat(content_copy):
    path = mutate(content_copy, lambda d: d["caveats"][0].update(caveat_md="  "))
    with pytest.raises(SeedError, match="caveat_md"):
        parse_finding(path)


def test_caveat_unknown_key(content_copy):
    path = mutate(content_copy, lambda d: d["caveats"][0].update(extra=1))
    with pytest.raises(SeedError, match="keys must be exactly"):
        parse_finding(path)


def test_file_name_must_match_slug(content_copy):
    path = mutate(content_copy, lambda d: None, name="other-name")
    with pytest.raises(SeedError, match="file name must be"):
        parse_finding(path)


def test_bad_slug(content_copy):
    path = mutate(content_copy, lambda d: d.update(slug="Bad_Slug"), name="Bad_Slug")
    with pytest.raises(SeedError, match="slug"):
        parse_finding(path)


def test_naive_timestamp(content_copy):
    path = mutate(content_copy, lambda d: d.update(published_at="2026-10-20T00:00:00"))
    with pytest.raises(SeedError, match="published_at"):
        parse_finding(path)


def test_duplicate_position_across_files(content_copy):
    src = content_copy / "findings" / "fixture-finding.yaml"
    data = yaml.safe_load(src.read_text())
    data["slug"] = "second-finding"
    (content_copy / "findings" / "second-finding.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(SeedError, match="duplicate position"):
        load_content(content_copy)
