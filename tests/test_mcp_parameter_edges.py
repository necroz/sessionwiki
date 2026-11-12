"""Edge cases for MCP parameters that the schemas cannot enforce.

MCP clients may ignore JSON Schema bounds, so the server must guard
`max_pages` itself. A binary page is a normal failure, not an internal
error.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from sessionwiki.mcp.server import (
    tool_wiki_category_browse,
    tool_wiki_confidence,
    tool_wiki_query,
    tool_wiki_read_page,
    tool_wiki_write_page,
)


def _hit_paths(text: str) -> list[str]:
    return re.findall(r"^## `([^`]+)` \(score:", text, re.MULTILINE)


def _wiki_with_pages(tmp_path: Path, count: int) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for i in range(count):
        (wiki / f"page-{i:02d}.md").write_text(
            f"---\ntitle: \"Page {i}\"\ntype: concept\n---\n\nalpha\n",
            encoding="utf-8",
        )


def test_query_clamps_max_pages_below_one(tmp_path: Path):
    _wiki_with_pages(tmp_path, 3)
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_query({"question": "alpha", "max_pages": 0})
    assert not result["isError"]
    assert len(_hit_paths(result["content"][0]["text"])) == 1


def test_query_clamps_max_pages_above_fifty(tmp_path: Path):
    _wiki_with_pages(tmp_path, 60)
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_query({"question": "alpha", "max_pages": 999})
    assert not result["isError"]
    assert len(_hit_paths(result["content"][0]["text"])) == 50


def test_query_rejects_non_numeric_max_pages(tmp_path: Path):
    _wiki_with_pages(tmp_path, 1)
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_query({"question": "alpha", "max_pages": "many"})
    assert result["isError"]
    assert "max_pages" in result["content"][0]["text"]


def test_read_page_reports_binary_file_as_a_clean_error(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "binary.md").write_bytes(b"\xff\xfe\x00\x80")
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_read_page({"path": "wiki/binary.md"})
    text = result["content"][0]["text"]
    assert result["isError"]
    assert "UTF-8" in text
    assert "Internal error" not in text


def test_query_tag_filter_matches_whole_tag_ignoring_case(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        "---\ntitle: \"A\"\ntype: concept\ntags: [claude-code]\n---\n\nalpha\n",
        encoding="utf-8",
    )
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        whole = tool_wiki_query({"question": "alpha", "tag": "Claude-Code"})
        part = tool_wiki_query({"question": "alpha", "tag": "claude"})
    assert _hit_paths(whole["content"][0]["text"]) == ["wiki/a.md"]
    assert _hit_paths(part["content"][0]["text"]) == []


def test_read_page_rejects_absolute_path_inside_repo(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    page = wiki / "a.md"
    page.write_text("# A\n", encoding="utf-8")
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_read_page({"path": str(page)})
    assert result["isError"]
    assert "absolute" in result["content"][0]["text"]


def test_write_page_rejects_absolute_path_inside_repo(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    target = tmp_path / "wiki" / "new.md"
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_write_page({
            "path": str(target),
            "content": "---\ntitle: New\ntype: concept\n---\n\nbody\n",
            "confirm": True,
        })
    assert result["isError"]
    assert not target.exists()


def test_confidence_rejects_non_numeric_bounds(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        low = tool_wiki_confidence({"min_confidence": "low"})
        high = tool_wiki_confidence({"max_confidence": None})
    assert low["isError"] and "min_confidence" in low["content"][0]["text"]
    assert high["isError"] and "max_confidence" in high["content"][0]["text"]


def test_category_browse_rejects_non_integer_min_count(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    with patch("sessionwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({"min_count": "x"})
    assert result["isError"]
    assert "min_count" in result["content"][0]["text"]
