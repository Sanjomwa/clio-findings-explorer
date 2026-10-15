"""Load and strictly validate content/findings/*.yaml, then sync it into the database."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Connection, delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import CAVEAT_SEVERITIES, SLUG_PATTERN, Finding, FindingCaveat, RegimeWeek
from app.seed import SeedError

FINDING_KEYS = {
    "slug", "week_start_date", "iso2", "position", "title", "teaser", "summary_md",
    "published_at", "caveats", "citations",
}  # fmt: skip
OPTIONAL_FINDING_KEYS = {"key_phrase"}
CAVEAT_KEYS = {"severity", "caveat_md"}
CITATION_KEYS = {"claim", "citation", "url"}


@dataclass(frozen=True)
class FindingDoc:
    slug: str
    iso2: str
    week_start_date: date
    position: int
    title: str
    teaser: str
    summary_md: str
    published_at: datetime
    caveats: list[dict[str, str]]
    citations: list[dict[str, str]]
    key_phrase: str | None = None


def _text(where: str, mapping: dict[str, Any], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        raise SeedError(f"{where}: {key} must be a non-blank string")
    return value


def parse_finding(path: Path) -> FindingDoc:
    where = str(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SeedError(f"{where}: invalid YAML ({exc})") from exc
    if not isinstance(raw, dict):
        raise SeedError(f"{where}: top level must be a mapping")
    if "sources" in raw:
        raise SeedError(
            f"{where}: the key `sources` was renamed to `citations` (public sources for "
            "real-world event statements); rename it"
        )
    unknown = set(raw) - FINDING_KEYS - OPTIONAL_FINDING_KEYS
    missing = FINDING_KEYS - set(raw)
    if unknown:
        raise SeedError(f"{where}: unknown keys {sorted(unknown)}")
    if missing:
        raise SeedError(f"{where}: missing keys {sorted(missing)}")

    slug = _text(where, raw, "slug")
    if not re.fullmatch(SLUG_PATTERN, slug):
        raise SeedError(f"{where}: slug {slug!r} does not match {SLUG_PATTERN}")
    if path.name != f"{slug}.yaml":
        raise SeedError(f"{where}: file name must be {slug}.yaml")

    week = raw["week_start_date"]
    if not isinstance(week, date) or isinstance(week, datetime):
        raise SeedError(f"{where}: week_start_date must be a YYYY-MM-DD date")
    published = raw["published_at"]
    if not isinstance(published, datetime) or published.tzinfo is None:
        raise SeedError(f"{where}: published_at must be an ISO 8601 timestamp with a timezone")
    position = raw["position"]
    if isinstance(position, bool) or not isinstance(position, int) or position < 1:
        raise SeedError(f"{where}: position must be an integer >= 1")

    caveats = raw["caveats"]
    if not isinstance(caveats, list) or not caveats:
        raise SeedError(f"{where}: caveats must be a non-empty list (a finding needs a caveat)")
    parsed_caveats = []
    for index, caveat in enumerate(caveats, start=1):
        label = f"{where}: caveats[{index}]"
        if not isinstance(caveat, dict):
            raise SeedError(f"{label} must be a mapping")
        if set(caveat) != CAVEAT_KEYS:
            raise SeedError(
                f"{label}: keys must be exactly {sorted(CAVEAT_KEYS)}, got {sorted(caveat)}"
            )
        if caveat["severity"] not in CAVEAT_SEVERITIES:
            raise SeedError(f"{label}: severity must be one of {list(CAVEAT_SEVERITIES)}")
        parsed_caveats.append(
            {"severity": caveat["severity"], "caveat_md": _text(label, caveat, "caveat_md")}
        )

    citations = raw["citations"]
    if not isinstance(citations, list):
        raise SeedError(f"{where}: citations must be a list (it may be empty)")
    parsed_citations = []
    for index, item in enumerate(citations, start=1):
        label = f"{where}: citations[{index}]"
        if not isinstance(item, dict):
            raise SeedError(f"{label} must be a mapping")
        if set(item) != CITATION_KEYS:
            raise SeedError(
                f"{label}: keys must be exactly {sorted(CITATION_KEYS)}, got {sorted(item)}"
            )
        parsed = {key: _text(label, item, key) for key in ("claim", "citation", "url")}
        if not parsed["url"].startswith("https://"):
            raise SeedError(f"{label}: url must start with https://")
        parsed_citations.append(parsed)

    teaser = _text(where, raw, "teaser")
    key_phrase = raw.get("key_phrase")
    if key_phrase is not None:
        if not isinstance(key_phrase, str) or not key_phrase.strip():
            raise SeedError(f"{where}: {slug}: key_phrase must be a non-blank string when present")
        if key_phrase not in teaser:
            raise SeedError(f"{where}: {slug}: key_phrase is not an exact substring of teaser")

    return FindingDoc(
        slug=slug,
        iso2=_text(where, raw, "iso2"),
        week_start_date=week,
        position=position,
        title=_text(where, raw, "title"),
        teaser=teaser,
        key_phrase=key_phrase,
        summary_md=_text(where, raw, "summary_md"),
        published_at=published,
        caveats=parsed_caveats,
        citations=parsed_citations,
    )


def load_content(content_dir: Path) -> list[FindingDoc] | None:
    """Return all findings, or None when content/ (or content/findings/) does not exist."""
    findings_dir = content_dir / "findings"
    if not findings_dir.is_dir():
        return None
    docs = [parse_finding(p) for p in sorted(findings_dir.glob("*.yaml"))]
    for field in ("slug", "position"):
        seen: set[Any] = set()
        for doc in docs:
            value = getattr(doc, field)
            if value in seen:
                raise SeedError(f"duplicate {field} {value!r} across content/findings files")
            seen.add(value)
    return docs


def sync_findings(conn: Connection, docs: list[FindingDoc]) -> int:
    """Upsert findings, replace their caveats, delete findings whose files are gone."""
    weeks = {
        (r.iso2, r.week_start_date)
        for r in conn.execute(select(RegimeWeek.iso2, RegimeWeek.week_start_date))
    }
    for doc in docs:
        if (doc.iso2, doc.week_start_date) not in weeks:
            raise SeedError(f"{doc.slug}: no regime week for {doc.iso2} {doc.week_start_date}")

    slugs = [d.slug for d in docs]
    conn.execute(delete(Finding).where(Finding.slug.not_in(slugs)))
    # Park remaining positions below zero so reordering never trips the UNIQUE constraint.
    conn.execute(text("UPDATE findings SET position = -position"))
    for doc in docs:
        values = {
            "slug": doc.slug, "iso2": doc.iso2, "week_start_date": doc.week_start_date,
            "title": doc.title, "teaser": doc.teaser, "summary_md": doc.summary_md,
            "published_at": doc.published_at, "position": doc.position,
            "citations": doc.citations, "key_phrase": doc.key_phrase,
        }  # fmt: skip
        stmt = pg_insert(Finding).values(values)
        conn.execute(
            stmt.on_conflict_do_update(
                index_elements=[Finding.slug],
                set_={k: v for k, v in values.items() if k != "slug"},
            )
        )
    conn.execute(delete(FindingCaveat).where(FindingCaveat.finding_slug.in_(slugs)))
    rows = [
        {
            "finding_slug": d.slug,
            "position": i,
            "severity": c["severity"],
            "caveat_md": c["caveat_md"],
        }
        for d in docs
        for i, c in enumerate(d.caveats, start=1)
    ]
    if rows:
        conn.execute(insert(FindingCaveat), rows)
    return len(docs)
