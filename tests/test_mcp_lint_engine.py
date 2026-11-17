"""wiki_lint delegates to the canonical lint engine (MCP surface refactor).

The old inline pass false-positived on #section anchors, system pages
and archived links, and described only 2 of the structural rules. These
tests pin the engine-backed behaviour and the CLI-aligned report shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_lint


def _page(root: Path, rel: str, body: str, title: str = "T", ptype: str = "concept") -> None:
    p = root / "wiki" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {title}\ntype: {ptype}\n---\n\n{body}\n", encoding="utf-8")


def _lint_report(tmp_path: Path) -> dict:
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = tool_wiki_lint({})
    assert result["isError"] is False, result["content"][0]["text"]
    return json.loads(result["content"][0]["text"])


def test_section_anchor_link_not_broken(tmp_path):
    _page(tmp_path, "A.md", "See [[B#section]] for details.")
    _page(tmp_path, "B.md", "Target page.")
    data = _lint_report(tmp_path)
    assert not any(
        i["rule"] == "link_integrity" and i["page"].endswith("A.md")
        for i in data["issues"]
    )


def test_system_pages_not_orphans(tmp_path):
    _page(tmp_path, "hot.md", "Recent sessions.", ptype="context")
    _page(tmp_path, "sources/_context.md", "Context.", ptype="context")
    _page(tmp_path, "A.md", "A regular page.")
    data = _lint_report(tmp_path)
    pages = {i["page"] for i in data["issues"] if i["rule"] == "orphan_detection"}
    assert "hot.md" not in pages and "sources/_context.md" not in pages


def test_link_to_archived_page_resolves(tmp_path):
    _page(tmp_path, "archive/old.md", "Retired page.")
    _page(tmp_path, "A.md", "Still references [[old]].")
    data = _lint_report(tmp_path)
    assert not any(
        i["rule"] == "link_integrity" and "old" in i["message"]
        for i in data["issues"]
    )


def test_report_shape_and_cap(tmp_path):
    _page(tmp_path, "A.md", "Lonely page.")
    data = _lint_report(tmp_path)
    assert set(data) == {"total_pages", "summary", "issue_count", "issues", "truncated"}
    assert len(data["issues"]) <= 200
    assert data["issue_count"] >= len(data["issues"])


def test_llm_rules_not_run(tmp_path):
    _page(tmp_path, "A.md", "Some claim.")
    data = _lint_report(tmp_path)
    assert all(
        i["rule"] not in {"contradiction_detection", "claim_verification", "summary_accuracy"}
        for i in data["issues"]
    )


def test_empty_wiki_reports_zero_pages(tmp_path):
    (tmp_path / "wiki").mkdir()
    data = _lint_report(tmp_path)
    assert data["total_pages"] == 0 and data["issues"] == []


def test_missing_wiki_is_error(tmp_path):
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = tool_wiki_lint({})
    assert result["isError"] and "wiki/" in result["content"][0]["text"]
