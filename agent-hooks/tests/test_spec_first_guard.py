"""Tests for agent-hooks/spec_first_guard.py.

Each case runs the hook as a subprocess with a PreToolUse JSON payload on
stdin. CLAUDE_PROJECT_DIR points at a temporary project that holds a copy of a
small fixture spec (or none), so the hook never reads the real openapi.yaml
except in the test that checks the real contract.

Run from the repository root:
    python3 -m unittest discover -s agent-hooks/tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "spec_first_guard.py"
FIXTURE_SPEC = Path(__file__).resolve().parent / "fixtures" / "openapi.yaml"
REAL_SPEC = Path(__file__).resolve().parents[2] / "openapi.yaml"


def router_source(*decorators, prefix=None):
    ctor = f'APIRouter(prefix="{prefix}")' if prefix is not None else "APIRouter()"
    lines = ["from fastapi import APIRouter", "", f"router = {ctor}", ""]
    for i, d in enumerate(decorators):
        lines += [d, f"def f{i}():", "    return {}", ""]
    return "\n".join(lines)


class GuardTestCase(unittest.TestCase):
    spec = FIXTURE_SPEC

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "backend" / "app" / "routers").mkdir(parents=True)
        if self.spec is not None:
            shutil.copy(self.spec, self.root / "openapi.yaml")

    def run_hook(self, stdin_text):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        return subprocess.run([sys.executable, str(HOOK)], input=stdin_text,
                              capture_output=True, text=True, timeout=30, env=env)

    def call(self, tool_name, tool_input):
        return self.run_hook(json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}))

    def router_path(self, name="items.py"):
        return str(self.root / "backend" / "app" / "routers" / name)

    def write(self, source, name="items.py"):
        return self.call("Write", {"file_path": self.router_path(name), "content": source})

    def existing(self, source, name="items.py"):
        Path(self.router_path(name)).write_text(source)

    def assertAllowed(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)

    def assertBlocked(self, r, *needles):
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        for n in needles:
            self.assertIn(n, r.stderr)


class TestFastPath(GuardTestCase):
    spec = None  # no spec on disk: proves it is not read

    def test_non_router_python_allowed_without_spec(self):
        r = self.call("Write", {"file_path": str(self.root / "backend" / "app" / "main.py"),
                                "content": router_source('@router.get("/api/nope")')})
        self.assertAllowed(r)

    def test_non_python_in_routers_allowed(self):
        r = self.call("Write", {"file_path": self.router_path("notes.md"), "content": "x"})
        self.assertAllowed(r)

    def test_outside_project_allowed(self):
        r = self.call("Write", {"file_path": "/elsewhere/backend/app/routers/a.py", "content": "x ="})
        self.assertAllowed(r)

    def test_router_file_without_spec_is_blocked(self):
        r = self.write(router_source('@router.get("/api/health")'))
        self.assertBlocked(r, "openapi.yaml")

    def test_router_file_without_routes_allowed_without_spec(self):
        self.assertAllowed(self.write("x = 1\n"))


class TestWrite(GuardTestCase):
    def test_declared_route_allowed(self):
        self.assertAllowed(self.write(router_source('@router.get("/api/health")')))

    def test_declared_with_prefix_and_param(self):
        src = router_source('@router.get("/{slug}")', '@router.put("/{slug}")', '@router.get("")',
                            prefix="/api/items")
        self.assertAllowed(self.write(src))

    def test_undeclared_path_blocked(self):
        r = self.write(router_source('@router.get("/api/undeclared")'))
        self.assertBlocked(r, "GET /api/undeclared", "edit openapi.yaml first", "Sam")

    def test_undeclared_with_prefix_blocked(self):
        r = self.write(router_source('@router.get("/other")', prefix="/api/items"))
        self.assertBlocked(r, "GET /api/items/other")

    def test_wrong_method_blocked(self):
        r = self.write(router_source('@router.post("/api/health")'))
        self.assertBlocked(r, "POST /api/health")

    def test_only_undeclared_listed(self):
        r = self.write(router_source('@router.get("/api/health")', '@router.delete("/api/health")'))
        self.assertBlocked(r, "DELETE /api/health")
        self.assertNotIn("GET /api/health", r.stderr)

    def test_api_route_declared_allowed(self):
        src = router_source('@router.api_route("/api/items/{slug}", methods=["GET", "PUT"])')
        self.assertAllowed(self.write(src))

    def test_api_route_wrong_method_blocked(self):
        src = router_source('@router.api_route("/api/health", methods=["GET", "POST"])')
        self.assertBlocked(self.write(src), "POST /api/health")

    def test_api_route_without_methods_blocked(self):
        self.assertBlocked(self.write(router_source('@router.api_route("/api/health")')), "methods")

    def test_api_route_nonliteral_methods_blocked(self):
        src = "from fastapi import APIRouter\nM = ['GET']\nrouter = APIRouter()\n" \
              "@router.api_route('/api/health', methods=M)\ndef f(): pass\n"
        self.assertBlocked(self.write(src), "literal")

    def test_nonliteral_path_blocked(self):
        src = "from fastapi import APIRouter\nP = '/api/health'\nrouter = APIRouter()\n" \
              "@router.get(P)\ndef f(): pass\n"
        self.assertBlocked(self.write(src), "literal")

    def test_fstring_path_blocked(self):
        src = "from fastapi import APIRouter\nrouter = APIRouter()\n" \
              "@router.get(f'/api/{1}')\ndef f(): pass\n"
        self.assertBlocked(self.write(src), "literal")

    def test_nonliteral_prefix_blocked(self):
        src = "from fastapi import APIRouter\nPFX = '/api'\nrouter = APIRouter(prefix=PFX)\n" \
              "@router.get('/health')\ndef f(): pass\n"
        self.assertBlocked(self.write(src), "prefix")

    def test_syntax_error_blocked(self):
        self.assertBlocked(self.write("def broken(:\n"), "does not parse")

    def test_async_def_checked(self):
        src = "from fastapi import APIRouter\nrouter = APIRouter()\n" \
              "@router.get('/api/nope')\nasync def f(): pass\n"
        self.assertBlocked(self.write(src), "GET /api/nope")

    def test_non_router_decorators_ignored(self):
        src = "import functools\n@functools.cache\ndef f(): pass\n@app.get.thing\ndef g(): pass\n"
        self.assertAllowed(self.write(src))

    def test_nested_router_file_checked(self):
        r = self.write(router_source('@router.get("/api/nope")'), name="sub/x.py")
        self.assertBlocked(r, "GET /api/nope")


class TestEdit(GuardTestCase):
    def test_edit_to_undeclared_blocked(self):
        self.existing(router_source('@router.get("/api/health")'))
        r = self.call("Edit", {"file_path": self.router_path(), "old_string": "/api/health",
                               "new_string": "/api/nope"})
        self.assertBlocked(r, "GET /api/nope")

    def test_edit_to_declared_allowed(self):
        self.existing(router_source('@router.get("/api/nope")'))
        r = self.call("Edit", {"file_path": self.router_path(), "old_string": "/api/nope",
                               "new_string": "/api/health"})
        self.assertAllowed(r)

    def test_replace_all(self):
        self.existing(router_source('@router.get("/api/x")', '@router.get("/api/x")'))
        one = {"file_path": self.router_path(), "old_string": "/api/x", "new_string": "/api/health"}
        # Without replace_all the string matches twice: the edit itself is ambiguous.
        self.assertBlocked(self.call("Edit", one), "replace_all")
        r = self.call("Edit", dict(one, replace_all=True))
        self.assertAllowed(r)

    def test_replace_all_leaves_undeclared_otherwise(self):
        self.existing(router_source('@router.get("/api/x")', '@router.get("/api/y")'))
        r = self.call("Edit", {"file_path": self.router_path(), "old_string": "/api/x",
                               "new_string": "/api/health"})
        self.assertBlocked(r, "GET /api/y")

    def test_old_string_not_found_blocked(self):
        self.existing(router_source('@router.get("/api/health")'))
        r = self.call("Edit", {"file_path": self.router_path(), "old_string": "absent", "new_string": "x"})
        self.assertBlocked(r, "not found")

    def test_missing_file_blocked(self):
        r = self.call("Edit", {"file_path": self.router_path("ghost.py"), "old_string": "a", "new_string": "b"})
        self.assertBlocked(r, "cannot read")


class TestMultiEdit(GuardTestCase):
    def test_applied_in_order(self):
        self.existing(router_source('@router.get("/api/a")'))
        edits = [{"old_string": "/api/a", "new_string": "/api/b"},
                 {"old_string": "/api/b", "new_string": "/api/health"}]
        self.assertAllowed(self.call("MultiEdit", {"file_path": self.router_path(), "edits": edits}))

    def test_undeclared_result_blocked(self):
        self.existing(router_source('@router.get("/api/health")'))
        edits = [{"old_string": "/api/health", "new_string": "/api/b"}]
        self.assertBlocked(self.call("MultiEdit", {"file_path": self.router_path(), "edits": edits}),
                           "GET /api/b")

    def test_later_edit_not_found_blocked(self):
        self.existing(router_source('@router.get("/api/health")'))
        edits = [{"old_string": "/api/health", "new_string": "/api/c"},
                 {"old_string": "/api/health", "new_string": "/api/d"}]
        self.assertBlocked(self.call("MultiEdit", {"file_path": self.router_path(), "edits": edits}),
                           "edit 2", "not found")

    def test_missing_edits_blocked(self):
        self.existing("x = 1\n")
        self.assertBlocked(self.call("MultiEdit", {"file_path": self.router_path()}), "edits")


class TestBadInput(GuardTestCase):
    def test_malformed_json(self):
        self.assertBlocked(self.run_hook("not json"), "failing closed")

    def test_empty_stdin(self):
        self.assertBlocked(self.run_hook(""), "failing closed")

    def test_non_object(self):
        self.assertBlocked(self.run_hook("[1]"), "failing closed")

    def test_missing_file_path(self):
        self.assertBlocked(self.call("Write", {"content": "x"}), "file_path")

    def test_missing_content(self):
        self.assertBlocked(self.call("Write", {"file_path": self.router_path()}), "content")

    def test_unexpected_error_fails_closed(self):
        # A spec whose 'paths' is not a mapping.
        (self.root / "openapi.yaml").write_text("paths: []\n")
        self.assertBlocked(self.write(router_source('@router.get("/api/health")')), "paths")

    def test_invalid_yaml_blocked(self):
        (self.root / "openapi.yaml").write_text("paths: [unclosed\n")
        self.assertBlocked(self.write(router_source('@router.get("/api/health")')), "cannot read")


class TestRealSpec(GuardTestCase):
    spec = REAL_SPEC

    def test_all_eight_operations_accepted(self):
        import yaml
        spec = yaml.safe_load(REAL_SPEC.read_text())
        pairs = [(m.upper(), p) for p, item in spec["paths"].items()
                 for m in item if m in ("get", "post", "put", "patch", "delete", "head", "options")]
        self.assertEqual(len(pairs), 8)
        for method, path in pairs:
            with self.subTest(method=method, path=path):
                self.assertAllowed(self.write(router_source(f'@router.{method.lower()}("{path}")')))
                prefix, _, tail = path.rpartition("/")
                src = router_source(f'@router.{method.lower()}("/{tail}")', prefix=prefix)
                self.assertAllowed(self.write(src))

    def test_undeclared_against_real_spec(self):
        self.assertBlocked(self.write(router_source('@router.get("/api/undeclared")')), "/api/undeclared")


if __name__ == "__main__":
    unittest.main()
