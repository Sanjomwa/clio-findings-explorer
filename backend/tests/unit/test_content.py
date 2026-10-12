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


def test_citations_valid_list_kept_in_order(content_copy):
    items = [
        {"claim": "B claim", "citation": "Pub, Title B, 2000-01-02", "url": "https://example.org/b"},
        {"claim": "A claim", "citation": "Pub, Title A, 2000-01-01", "url": "https://example.org/a"},
    ]
    mutate(content_copy, lambda d: d.update(citations=items))
    docs = load_content(content_copy)
    assert docs[0].citations == items


def test_citations_empty_list_is_valid(content_copy):
    assert load_content(content_copy)[0].citations == []


def test_citations_missing_key(content_copy):
    path = mutate(content_copy, lambda d: d.pop("citations"))
    with pytest.raises(SeedError, match=r"missing keys \['citations'\]"):
        parse_finding(path)


def test_citations_must_be_a_list(content_copy):
    path = mutate(content_copy, lambda d: d.update(citations="https://example.org/x"))
    with pytest.raises(SeedError, match="citations must be a list"):
        parse_finding(path)


GOOD = {"claim": "c", "citation": "Pub, Title, 2000-01-01", "url": "https://example.org/x"}


@pytest.mark.parametrize("url", ["http://example.org/x", "example.org/x", "ftp://example.org/x"])
def test_citation_url_must_be_https(content_copy, url):
    path = mutate(content_copy, lambda d: d.update(citations=[{**GOOD, "url": url}]))
    with pytest.raises(SeedError, match="url must start with https://"):
        parse_finding(path)


def test_citation_extra_key(content_copy):
    path = mutate(content_copy, lambda d: d.update(citations=[{**GOOD, "note": "x"}]))
    with pytest.raises(SeedError, match=r"citations\[1\]: keys must be exactly"):
        parse_finding(path)


def test_citation_missing_key(content_copy):
    bad = {k: v for k, v in GOOD.items() if k != "claim"}
    path = mutate(content_copy, lambda d: d.update(citations=[bad]))
    with pytest.raises(SeedError, match="keys must be exactly"):
        parse_finding(path)


@pytest.mark.parametrize("key", ["claim", "citation", "url"])
@pytest.mark.parametrize("value", ["", "   ", None, 5])
def test_citation_blank_value(content_copy, key, value):
    path = mutate(content_copy, lambda d: d.update(citations=[{**GOOD, key: value}]))
    with pytest.raises(SeedError, match=f"{key} must be a non-blank string"):
        parse_finding(path)


def test_citation_item_must_be_mapping(content_copy):
    path = mutate(content_copy, lambda d: d.update(citations=["https://example.org/x"]))
    with pytest.raises(SeedError, match="must be a mapping"):
        parse_finding(path)


def test_legacy_sources_key_is_rejected_with_rename_message(content_copy):
    path = mutate(content_copy, lambda d: d.update(sources=[]))
    with pytest.raises(SeedError, match="renamed to `citations`"):
        parse_finding(path)
