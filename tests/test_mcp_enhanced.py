"""Tests for the v1.0 enhanced MCP surface (#159) after the 15 -> 11 cut.

The four consumer-less listing tools (wiki_confidence, wiki_lifecycle,
wiki_entity_search, wiki_category_browse) were removed; wiki_dashboard
stays. Their 13 tests went with them; the surface-wide definition tests
(TDQS) remain and pin the 11-tool contract.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


from sessionwiki.mcp.server import (
    TOOLS,
    TOOL_IMPLS,
    handle_tools_call,
    tool_wiki_dashboard,
)


# ─── Registration ─────────────────────────────────────────────────────


def test_all_tools_registered():
    assert len(TOOLS) == 11
    names = {t["name"] for t in TOOLS}
    assert names == {"wiki_query", "wiki_search", "wiki_list_sources",
                     "wiki_read_page", "wiki_lint", "wiki_sync", "wiki_export",
                     "wiki_dashboard", "wiki_write_page",
                     "wiki_update_frontmatter", "wiki_archive_page"}


def test_removed_tools_answer_unknown_tool():
    for name in ("wiki_confidence", "wiki_lifecycle", "wiki_entity_search", "wiki_category_browse"):
        result = handle_tools_call({"name": name, "arguments": {}})
        assert result["isError"] and "Unknown tool" in result["content"][0]["text"]


def test_all_tools_have_impl():
    for tool in TOOLS:
        assert tool["name"] in TOOL_IMPLS


# ─── wiki_dashboard ──────────────────────────────────────────────────


def test_dashboard_counts_by_type(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntype: concept\n---\n', encoding="utf-8"
    )
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "entity" in text
    assert "concept" in text


def test_dashboard_confidence_buckets(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "high.md").write_text(
        '---\ntitle: "H"\ntype: entity\nconfidence: 0.95\n---\n', encoding="utf-8"
    )
    (wiki / "low.md").write_text(
        '---\ntitle: "L"\ntype: entity\nconfidence: 0.2\n---\n', encoding="utf-8"
    )
    (wiki / "none.md").write_text(
        '---\ntitle: "N"\ntype: entity\n---\n', encoding="utf-8"
    )
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "high" in text
    assert "low" in text


def test_dashboard_handles_empty_wiki(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "0 pages" in text


# ─── Tool definitions for agents and directories (TDQS) ──────────────


_HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def test_every_tool_has_title_and_behaviour_annotations():
    for tool in TOOLS:
        assert tool["title"], tool["name"]
        annotations = tool["annotations"]
        assert annotations["title"] == tool["title"]
        for hint in _HINTS:
            assert isinstance(annotations[hint], bool), (tool["name"], hint)
        assert annotations["destructiveHint"] is (
            tool["name"] in {"wiki_write_page", "wiki_update_frontmatter"}
        )
        assert annotations["openWorldHint"] is False


def test_write_tools_are_marked():
    writers = {t["name"] for t in TOOLS if not t["annotations"]["readOnlyHint"]}
    assert writers == {
        "wiki_sync", "wiki_write_page", "wiki_update_frontmatter",
        "wiki_archive_page",
    }


def test_every_description_points_to_a_sibling_tool():
    """Agents pick between 11 similar tools from the descriptions alone,
    so each one names at least one alternative."""
    names = {t["name"] for t in TOOLS}
    for tool in TOOLS:
        others = names - {tool["name"]}
        assert any(other in tool["description"] for other in others), tool["name"]


def test_export_description_covers_every_format():
    (export,) = [t for t in TOOLS if t["name"] == "wiki_export"]
    for fmt in export["inputSchema"]["properties"]["format"]["enum"]:
        assert f"'{fmt}'" in export["description"], fmt


def test_lint_description_claims_only_what_it_checks():
    (lint,) = [t for t in TOOLS if t["name"] == "wiki_lint"]
    assert "orphan" in lint["description"]
    assert "no LLM" in lint["description"]
    assert "contradiction" not in lint["description"].lower()
