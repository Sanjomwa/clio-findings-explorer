"""PreToolUse hook: spec-first-guard.

Enforces AGENTS.md hard rule 2 (spec first). Claude Code runs this before every
Write, Edit and MultiEdit call and passes the call as JSON on stdin. Exit 0
lets the call run; exit 2 blocks it and the stderr text is shown to the agent.

For a .py file under backend/app/routers/ the hook rebuilds the file as it
would be after the edit, extracts every (METHOD, path) route with `ast`, and
checks each against the operations declared in openapi.yaml. Any other file is
allowed without reading the spec.

Fails closed: unreadable input, an edit that cannot be applied, a file that
does not parse, a non-literal path, or any unexpected error exits 2.
Needs PyYAML (imported only when a router file is checked). See
agent-hooks/README.md.
"""

import ast
import json
import os
import sys
from pathlib import Path

ROUTERS_REL = ("backend", "app", "routers")
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})


class Block(Exception):
    """Raised to block the call; the message goes to stderr."""


def project_dir():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def is_router_file(file_path, root):
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    p = Path(os.path.normpath(p))
    if p.suffix != ".py":
        return False
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    return rel.parts[:3] == ROUTERS_REL and len(rel.parts) > 3


def apply_edit(text, old, new, replace_all, label):
    if not isinstance(old, str) or not isinstance(new, str):
        raise Block(f"spec-first-guard: {label} has no usable old_string/new_string.")
    if old == "":
        raise Block(f"spec-first-guard: {label} has an empty old_string.")
    count = text.count(old)
    if count == 0:
        raise Block(f"spec-first-guard: {label}: old_string not found, so the resulting file cannot be built to check its routes.")
    if count > 1 and not replace_all:
        raise Block(f"spec-first-guard: {label}: old_string matches {count} times and replace_all is not set.")
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def read_current(file_path, root, label):
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise Block(f"spec-first-guard: {label}: cannot read {p} to rebuild the edited file ({e}).")


def reconstruct(tool_name, tool_input, root):
    file_path = tool_input["file_path"]
    if tool_name == "Write":
        content = tool_input.get("content")
        if not isinstance(content, str):
            raise Block("spec-first-guard: Write has no string content.")
        return content
    if tool_name == "Edit":
        text = read_current(file_path, root, "Edit")
        return apply_edit(text, tool_input.get("old_string"), tool_input.get("new_string"),
                          bool(tool_input.get("replace_all")), "Edit")
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list) or not edits:
            raise Block("spec-first-guard: MultiEdit has no edits list.")
        text = read_current(file_path, root, "MultiEdit")
        for i, e in enumerate(edits, 1):
            if not isinstance(e, dict):
                raise Block(f"spec-first-guard: MultiEdit edit {i} is not an object.")
            text = apply_edit(text, e.get("old_string"), e.get("new_string"),
                              bool(e.get("replace_all")), f"MultiEdit edit {i}")
        return text
    raise Block(f"spec-first-guard: unexpected tool {tool_name!r}.")


def literal_str(node, what, lineno):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise Block(f"spec-first-guard: line {lineno}: {what} is not a string literal. "
                "Routers must use literal paths (and a literal APIRouter prefix) so the guard can check them.")


def is_apirouter_call(node):
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Name) and f.id == "APIRouter") or \
           (isinstance(f, ast.Attribute) and f.attr == "APIRouter")


def extract_routes(source):
    """Return a sorted list of (METHOD, full_path) declared by decorators."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise Block(f"spec-first-guard: the resulting file does not parse (line {e.lineno}: {e.msg}), so its routes cannot be checked.")

    prefixes = {}  # router variable name -> prefix
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and is_apirouter_call(node.value):
            prefix = ""
            for kw in node.value.keywords:
                if kw.arg == "prefix":
                    prefix = literal_str(kw.value, "the APIRouter prefix", node.lineno)
            for t in node.targets:
                if isinstance(t, ast.Name):
                    prefixes[t.id] = prefix
        elif isinstance(node, ast.AnnAssign) and node.value is not None \
                and is_apirouter_call(node.value) and isinstance(node.target, ast.Name):
            prefix = ""
            for kw in node.value.keywords:
                if kw.arg == "prefix":
                    prefix = literal_str(kw.value, "the APIRouter prefix", node.lineno)
            prefixes[node.target.id] = prefix

    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name)):
                continue
            attr = dec.func.attr
            if attr not in HTTP_METHODS and attr != "api_route":
                continue
            router = dec.func.value.id
            prefix = prefixes.get(router, "")
            path_node = dec.args[0] if dec.args else None
            if path_node is None:
                for kw in dec.keywords:
                    if kw.arg == "path":
                        path_node = kw.value
            if path_node is None:
                raise Block(f"spec-first-guard: line {dec.lineno}: @{router}.{attr} has no path argument.")
            path = literal_str(path_node, "the route path", dec.lineno)
            if attr == "api_route":
                methods_node = next((kw.value for kw in dec.keywords if kw.arg == "methods"), None)
                if methods_node is None:
                    raise Block(f"spec-first-guard: line {dec.lineno}: @{router}.api_route has no methods= list; "
                                "routes must declare literal methods so the guard can check them.")
                if not isinstance(methods_node, (ast.List, ast.Tuple, ast.Set)):
                    raise Block(f"spec-first-guard: line {dec.lineno}: methods= is not a literal list. "
                                "Routers must use literal methods so the guard can check them.")
                methods = [literal_str(m, "a methods= entry", dec.lineno).upper() for m in methods_node.elts]
            else:
                methods = [attr.upper()]
            for m in methods:
                routes.append((m, prefix + path))
    return sorted(set(routes))


def declared_operations(spec_path):
    try:
        import yaml
    except ImportError as e:
        raise Block(f"spec-first-guard: PyYAML is not available to this interpreter ({e}); cannot read openapi.yaml.")
    try:
        with open(spec_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise Block(f"spec-first-guard: cannot read {spec_path} ({e}).")
    paths = spec.get("paths") if isinstance(spec, dict) else None
    if not isinstance(paths, dict):
        raise Block(f"spec-first-guard: {spec_path} has no 'paths' mapping.")
    ops = set()
    for path, item in paths.items():
        if isinstance(item, dict):
            for key in item:
                if key.lower() in HTTP_METHODS:
                    ops.add((key.upper(), path))
    return ops


def check(data):
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("file_path"), str):
        raise Block("spec-first-guard: input has no tool_input.file_path.")
    root = project_dir()
    if not is_router_file(tool_input["file_path"], root):
        return  # fast path: do not load the spec
    source = reconstruct(tool_name, tool_input, root)
    routes = extract_routes(source)
    if not routes:
        return
    spec_path = str(root / "openapi.yaml")
    declared = declared_operations(spec_path)
    missing = [r for r in routes if r not in declared]
    if missing:
        listing = "\n".join(f"  {m} {p}" for m, p in missing)
        raise Block(
            "spec-first-guard: BLOCKED. These routes are not declared in openapi.yaml:\n"
            f"{listing}\n"
            "AGENTS.md hard rule 2: edit openapi.yaml first, then STOP so Sam can commit that edit "
            "separately. Do not write the router until the operation is in the committed spec."
        )


def main():
    try:
        data = json.loads(sys.stdin.read())
        if not isinstance(data, dict):
            raise ValueError("input is not a JSON object")
    except Exception as e:
        print(f"spec-first-guard: cannot read hook input ({e}); failing closed.", file=sys.stderr)
        return 2
    try:
        check(data)
    except Block as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:
        print(f"spec-first-guard: unexpected error ({type(e).__name__}: {e}); failing closed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
