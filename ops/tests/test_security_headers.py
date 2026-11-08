"""The frontend's nginx config keeps its browser security headers and its API rate limit.

Reads frontend/index.html and the nginx files (no nginx needed) and checks:
  - the CSP script-src hash equals sha256 of the inline theme script, so editing that script
    without updating the hash fails here;
  - every required header is in the include file with `always`, and that file is included in the
    server block and in every location that has its own add_header (nginx drops inherited
    add_header lines in such a location);
  - /api/ has limit_req, `limit_req_status 429` is set, and rejections are logged below the
    image's error_log level (notice), so client addresses are not written;
  - the Dockerfile copies the include file to the path the template includes.

Run from the repository root:
    python3 -m unittest discover -s ops/tests -v
"""

import base64
import hashlib
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
INDEX = (REPO / "frontend" / "index.html").read_text(encoding="utf-8")
TEMPLATE = (REPO / "frontend" / "nginx" / "default.conf.template").read_text(encoding="utf-8")
HEADERS = (REPO / "frontend" / "nginx" / "security-headers.conf").read_text(encoding="utf-8")
DOCKERFILE = (REPO / "frontend" / "Dockerfile").read_text(encoding="utf-8")

INCLUDE_PATH = "/etc/nginx/snippets/security-headers.conf"
INCLUDE_LINE = f"include {INCLUDE_PATH};"
REQUIRED = [
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Cross-Origin-Opener-Policy",
]


def strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] if line.lstrip().startswith("#") else line
                     for line in text.splitlines())


def block_body(text: str, opener: str) -> str:
    """Text inside the braces that follow `opener` (brace matching)."""
    start = text.index(opener)
    i = text.index("{", start) + 1
    depth, j = 1, i
    while depth:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
    return text[i : j - 1]


def locations(server: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"^\s*location\s+([^{]+?)\s*\{", server, re.M):
        out[m.group(1)] = block_body(server, m.group(0).strip())
    return out


class SecurityHeadersTest(unittest.TestCase):
    def setUp(self):
        self.template = strip_comments(TEMPLATE)
        self.server = block_body(self.template, "server")
        self.locations = locations(self.server)

    def test_csp_hash_matches_inline_theme_script(self):
        scripts = re.findall(r"<script>(.*?)</script>", INDEX, re.S)
        self.assertEqual(len(scripts), 1, "expected exactly one inline <script> in index.html")
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode()
        self.assertIn(f"'sha256-{digest}'", HEADERS, "update the CSP hash in security-headers.conf")

    def test_no_other_inline_script_or_style(self):
        self.assertEqual(len(re.findall(r"<script(?![^>]*\bsrc=)", INDEX)), 1)
        self.assertNotRegex(INDEX, r"<style|\sstyle=")

    def test_every_required_header_has_always(self):
        for name in REQUIRED:
            lines = [ln for ln in HEADERS.splitlines() if ln.startswith(f"add_header {name} ")]
            self.assertEqual(len(lines), 1, name)
            self.assertTrue(lines[0].rstrip().endswith("always;"), name)

    def test_csp_is_strict(self):
        csp = next(ln for ln in HEADERS.splitlines() if "Content-Security-Policy" in ln and ln.startswith("add_header"))
        for needle in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'none'"):
            self.assertIn(needle, csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)

    def test_no_hsts(self):
        self.assertNotIn("Strict-Transport-Security", strip_comments(HEADERS))
        self.assertNotIn("Strict-Transport-Security", self.template)

    def test_server_block_includes_headers(self):
        top = re.sub(r"location[^{]*\{[^{}]*\}", "", self.server)
        self.assertIn(INCLUDE_LINE, top)

    def test_every_location_with_add_header_includes_headers(self):
        self.assertTrue(self.locations)
        for name, body in self.locations.items():
            if "add_header" in body or name == "/api/":
                self.assertIn(INCLUDE_LINE, body, f"location {name}")

    def test_api_is_rate_limited_and_static_is_not(self):
        self.assertIn("limit_req zone=", self.locations["/api/"])
        for name, body in self.locations.items():
            if name != "/api/":
                self.assertNotIn("limit_req ", body, f"location {name}")
        self.assertRegex(self.template, r"limit_req_zone\s+\$server_name\s+zone=\w+:\w+\s+rate=")

    def test_rate_limit_status_429(self):
        self.assertRegex(self.server, r"limit_req_status\s+429;")

    def test_rejections_are_not_logged(self):
        # The nginx image logs errors at `notice`; a rejection logged at `info` is not written.
        self.assertRegex(self.server, r"limit_req_log_level\s+info;")

    def test_access_log_has_no_client_address(self):
        fmt = re.search(r"log_format\s+\w+\s+(.*?);", self.template, re.S).group(1)
        self.assertNotIn("remote_addr", fmt)
        self.assertNotIn("forwarded", fmt)

    def test_dockerfile_copies_include_to_included_path(self):
        self.assertIn(f"COPY nginx/security-headers.conf {INCLUDE_PATH}", DOCKERFILE)


if __name__ == "__main__":
    unittest.main()
