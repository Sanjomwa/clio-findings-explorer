"""Every relative link in AGENTS.md, README.md and docs/*.md must resolve (issue #9).

Checks, with the file and the link named in the failure message:
  - a relative link or image points at a file or folder that exists;
  - a #anchor (alone, or after a Markdown file) matches a heading in that file, using GitHub's slug rules;
  - every top-level docs/*.md is linked from AGENTS.md ("Where things are documented").

External links (http, https, mailto) are not fetched. Links inside code fences and inline code are ignored.

Run from the repository root:
    python3 -m unittest discover -s ops/tests -v
"""

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parent.parent.parent
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
HTML_SRC = re.compile(r"""(?:src|href)=["']([^"']+)["']""")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|//)", re.I)


def doc_files() -> list[Path]:
    return [REPO / "AGENTS.md", REPO / "README.md", *sorted((REPO / "docs").glob("*.md"))]


def prose_lines(text: str) -> list[tuple[int, str]]:
    """(line number, line) outside code fences, with inline code spans blanked out."""
    out, fenced = [], False
    for number, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if not fenced:
            out.append((number, re.sub(r"`[^`\n]*`", "``", line)))
    return out


def slug(heading: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)  # links keep their text
    text = text.replace("`", "").replace("*", "").replace("~", "")
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, line in prose_lines(path.read_text(encoding="utf-8")):
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def links(path: Path) -> list[tuple[int, str]]:
    found = []
    for number, line in prose_lines(path.read_text(encoding="utf-8")):
        for match in LINK.finditer(line):
            found.append((number, match.group(1).strip("<>")))
        for match in HTML_SRC.finditer(line):
            found.append((number, match.group(1)))
    return found


def check(path: Path, root: Path = REPO) -> list[str]:
    """Problems in one file, each naming the file, the line and the link."""
    problems = []
    shown = path.relative_to(root) if path.is_relative_to(root) else path
    for number, link in links(path):
        if EXTERNAL.match(link):
            continue
        target, _, fragment = link.partition("#")
        target = unquote(target.split("?", 1)[0])
        resolved = path if target == "" else (path.parent / target).resolve()
        if target and not resolved.exists():
            problems.append(f"{shown}:{number}: broken link '{link}' (no such file or folder: {target})")
            continue
        if fragment and resolved.is_file() and resolved.suffix == ".md":
            if unquote(fragment).lower() not in anchors(resolved):
                problems.append(f"{shown}:{number}: broken anchor '{link}' (no heading '{fragment}' in "
                                f"{resolved.name})")
    return problems


class DocsLinks(unittest.TestCase):
    def test_every_relative_link_resolves(self) -> None:
        problems = [p for path in doc_files() for p in check(path)]
        self.assertEqual(problems, [], "broken links:\n" + "\n".join(problems))

    def test_every_top_level_doc_is_linked_from_agents_md(self) -> None:
        linked = {(REPO / "AGENTS.md").parent.joinpath(unquote(link.partition("#")[0])).resolve()
                  for _, link in links(REPO / "AGENTS.md") if not EXTERNAL.match(link) and link}
        missing = [f"docs/{p.name}" for p in sorted((REPO / "docs").glob("*.md")) if p.resolve() not in linked]
        self.assertEqual(missing, [], "AGENTS.md ('Where things are documented') does not link: "
                         + ", ".join(missing))


class CheckerCatchesBreakage(unittest.TestCase):
    """The checker itself: it must fail, and say where, on a bad link."""

    def setUp(self) -> None:
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "other.md").write_text("# Other doc\n\n## Same\n\n## Same\n", encoding="utf-8")

    def problems(self, text: str) -> list[str]:
        page = self.root / "page.md"
        page.write_text(text, encoding="utf-8")
        return check(page, self.root)

    def test_missing_file_names_file_line_and_link(self) -> None:
        (problem,) = self.problems("ok\n\nSee [x](missing.md).\n")
        self.assertEqual(problem.split(" (")[0], "page.md:3: broken link 'missing.md'")

    def test_missing_anchor_in_same_and_other_file(self) -> None:
        found = self.problems("# Title\n[a](#title) [b](#nope) [c](other.md#other-doc) [d](other.md#gone)\n")
        self.assertEqual(len(found), 2)
        self.assertIn("'#nope'", found[0])
        self.assertIn("'other.md#gone'", found[1])

    def test_duplicate_headings_get_numbered_anchors(self) -> None:
        self.assertEqual(self.problems("[a](other.md#same) [b](other.md#same-1) [c](other.md#same-2)\n").__len__(), 1)

    def test_external_code_and_fences_are_ignored(self) -> None:
        text = "[web](https://example.com/x) [m](mailto:a@b.c)\n`[no](nowhere.md)`\n```\n[no](nowhere.md)\n```\n"
        self.assertEqual(self.problems(text), [])

    def test_images_and_html_sources_are_checked(self) -> None:
        found = self.problems('![alt](pic.png)\n<img src="also-missing.svg">\n')
        self.assertEqual(len(found), 2)

    def test_slug_rules(self) -> None:
        self.assertEqual(slug("How it was built: the agent team and process"),
                         "how-it-was-built-the-agent-team-and-process")
        self.assertEqual(slug("`ops/oncall/actor.py` and [link](x.md)"), "opsoncallactorpy-and-link")
        self.assertEqual(slug("Escalation demo (for Sam to run; not run by the agent)"),
                         "escalation-demo-for-sam-to-run-not-run-by-the-agent")


if __name__ == "__main__":
    unittest.main()
