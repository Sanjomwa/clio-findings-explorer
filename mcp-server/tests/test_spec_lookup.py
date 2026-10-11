"""Tests for spec_lookup, called directly against the real openapi.yaml.

Run: uv run --directory mcp-server pytest -v
"""

import server


def test_lists_eight_operations():
    r = server.spec_lookup()
    assert len(r["operations"]) == 8
    assert {"method", "path", "operationId", "summary"} <= set(r["operations"][0])
    assert ("GET", "/api/health") in {(o["method"], o["path"]) for o in r["operations"]}


def test_version_is_0_4_1():
    assert server.spec_lookup()["version"] == "0.4.1"


def test_path_filter():
    r = server.spec_lookup(path="/api/findings/{slug}")
    assert r["found"] is True
    (op,) = r["operations"]
    assert op["operationId"] == "getFinding"
    assert op["parameters"] == [{"name": "slug", "in": "path", "required": True, "schema": "string"}]
    statuses = {x["status"]: x["schema"] for x in op["responses"]}
    assert statuses["200"] == "FindingDetailResponse"
    assert {"404", "422"} <= set(statuses)


def test_method_filter():
    r = server.spec_lookup(path="/api/health", method="get")
    assert [o["operationId"] for o in r["operations"]] == ["getHealth"]
    r = server.spec_lookup(method="GET")
    assert len(r["operations"]) == 8


def test_undeclared_path_does_not_raise():
    r = server.spec_lookup(path="/api/undeclared")
    assert r["found"] is False
    assert "/api/health" in r["declared_paths"]
    assert len(r["declared_paths"]) == 8


def test_undeclared_method():
    r = server.spec_lookup(path="/api/health", method="post")
    assert r["found"] is False
    assert "/api/health" in r["declared_paths"]


def test_tool_registered():
    import asyncio
    tools = asyncio.run(server.mcp.list_tools())
    assert sorted(t.name for t in tools) == sorted(["spec_lookup", "query_snapshot"])
