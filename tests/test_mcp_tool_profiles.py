"""MCP tool profiles: ``SESSIONWIKI_MCP_TOOLS=read|full``.

Usage data from three agents showed four read tools carry nearly every
call, while sync, export and the three write tools were never called.
The default ``read`` profile lists only the read-only tools, so the
unused definitions stop costing tokens in every session; ``full``
restores the whole surface.
"""

from __future__ import annotations

import pytest

from sessionwiki.mcp import server

READ_TOOLS = {
    "wiki_query", "wiki_search", "wiki_list_sources", "wiki_read_page",
    "wiki_dashboard", "wiki_lint",
}


def _listed() -> set[str]:
    return {t["name"] for t in server.handle_tools_list({})["tools"]}


def test_default_profile_lists_read_tools_only(monkeypatch):
    monkeypatch.delenv("SESSIONWIKI_MCP_TOOLS", raising=False)
    assert _listed() == READ_TOOLS


def test_read_profile_tools_are_all_read_only(monkeypatch):
    monkeypatch.setenv("SESSIONWIKI_MCP_TOOLS", "read")
    for tool in server.handle_tools_list({})["tools"]:
        assert tool["annotations"]["readOnlyHint"] is True, tool["name"]


def test_full_profile_lists_every_tool(monkeypatch):
    monkeypatch.setenv("SESSIONWIKI_MCP_TOOLS", "full")
    assert _listed() == {t["name"] for t in server.TOOLS}


@pytest.mark.parametrize("value", ["FULL", " full "])
def test_profile_value_ignores_case_and_spaces(monkeypatch, value):
    monkeypatch.setenv("SESSIONWIKI_MCP_TOOLS", value)
    assert len(_listed()) == len(server.TOOLS)


def test_unknown_profile_falls_back_to_read(monkeypatch):
    monkeypatch.setenv("SESSIONWIKI_MCP_TOOLS", "everything")
    assert _listed() == READ_TOOLS


def test_hidden_tool_call_names_the_switch(monkeypatch):
    monkeypatch.delenv("SESSIONWIKI_MCP_TOOLS", raising=False)
    result = server.handle_tools_call({"name": "wiki_sync", "arguments": {}})
    assert result["isError"] is True
    assert "SESSIONWIKI_MCP_TOOLS=full" in result["content"][0]["text"]


def test_instructions_mention_write_tools_only_in_full(monkeypatch):
    monkeypatch.delenv("SESSIONWIKI_MCP_TOOLS", raising=False)
    assert "wiki_write_page" not in server.handle_initialize({})["instructions"]
    monkeypatch.setenv("SESSIONWIKI_MCP_TOOLS", "full")
    assert "wiki_write_page" in server.handle_initialize({})["instructions"]
