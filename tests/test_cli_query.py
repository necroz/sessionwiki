"""`sessionwiki query` answers with the MCP ranking (card 17).

The CLI used to call the optional graphify engine and failed with
"graphify not installed" on a default install, while MCP ``wiki_query``
answered the same question with the ranked lexical search. The CLI now
shares ``rank_query`` with the MCP tool; ``--graph`` keeps the old path.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from sessionwiki import cli
from sessionwiki.cli import build_parser
from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_query

_RANKED_RE = re.compile(r"^## `([^`]+)`", re.MULTILINE)


def _page(path: Path, front: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "\n".join(f"{k}: {v}" for k, v in front.items())
    path.write_text(f"---\n{meta}\n---\n\n{body}\n", encoding="utf-8")


def _seed_wiki(root: Path) -> None:
    """Two concept pages and one source page that mention chunking."""
    _page(root / "wiki" / "index.md", {"title": "Index", "type": "navigation"},
          "- [Chunking](concepts/Chunking.md)")
    _page(root / "wiki" / "overview.md", {"title": "Overview", "type": "synthesis"},
          "The wiki of a small demo project.")
    _page(root / "wiki" / "concepts" / "Chunking.md",
          {"title": "Chunking", "type": "concept", "date": "2026-11-01"},
          "## Summary\n\nChunking splits a large session into map-reduce pieces.")
    _page(root / "wiki" / "concepts" / "Retrieval.md",
          {"title": "Retrieval", "type": "concept", "date": "2026-11-01"},
          "## Summary\n\nRetrieval ranks the pages that mention chunking.")
    _page(root / "wiki" / "sources" / "demo" / "2026-11-01-sess_a.md",
          {"title": "Session sess_a", "type": "source", "slug": "sess_a",
           "date": "2026-11-01"},
          "## Summary\n\nThe session explained chunking of large inputs.")


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    """Parse argv as the real CLI would, run the command, return (rc, out, err)."""
    args = build_parser().parse_args(["query", *argv])
    rc = args.func(args)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_json_returns_the_mcp_paths_in_the_same_order(tmp_path: Path, capsys):
    _seed_wiki(tmp_path)
    with patch.object(cli, "REPO_ROOT", tmp_path), patch.object(server, "REPO_ROOT", tmp_path):
        rc, out, _ = _run(["chunking", "large", "sessions", "--json", "--limit", "3"], capsys)
        mcp = tool_wiki_query({"question": "chunking large sessions", "max_pages": 3})
    assert rc == 0
    data = json.loads(out)
    assert [hit["path"] for hit in data["hits"]] == _RANKED_RE.findall(
        mcp["content"][0]["text"]
    )
    assert "index" not in data and "overview" not in data


def test_json_works_without_graphify(tmp_path: Path, capsys):
    _seed_wiki(tmp_path)
    with patch.object(cli, "REPO_ROOT", tmp_path), \
         patch.object(server, "REPO_ROOT", tmp_path), \
         patch("sessionwiki.graphify_bridge.is_available", return_value=False):
        rc, out, err = _run(["chunking", "--json"], capsys)
    assert rc == 0
    assert json.loads(out)["hits"]
    assert err == ""


def test_limit_one_returns_one_hit(tmp_path: Path, capsys):
    _seed_wiki(tmp_path)
    with patch.object(cli, "REPO_ROOT", tmp_path), patch.object(server, "REPO_ROOT", tmp_path):
        rc, out, _ = _run(["chunking", "--limit", "1"], capsys)
    assert rc == 0
    assert len(_RANKED_RE.findall(out)) == 1


def test_text_mode_uses_the_mcp_header_format(tmp_path: Path, capsys):
    _seed_wiki(tmp_path)
    with patch.object(cli, "REPO_ROOT", tmp_path), patch.object(server, "REPO_ROOT", tmp_path):
        rc, out, _ = _run(["chunking", "large", "sessions", "--limit", "3"], capsys)
    assert rc == 0
    assert re.search(r"^## `wiki/concepts/Chunking\.md` \(score: \d+\.\d+\)$", out, re.MULTILINE)
    assert "## Overview context" in out


def test_graph_without_graphify_returns_2(tmp_path: Path, capsys):
    _seed_wiki(tmp_path)
    with patch.object(cli, "REPO_ROOT", tmp_path), \
         patch("sessionwiki.graphify_bridge.is_available", return_value=False):
        rc, _, err = _run(["chunking", "--graph"], capsys)
    assert rc == 2
    assert "graphify not installed" in err


def test_lifecycle_flag_filters_pages(tmp_path: Path, capsys):
    _page(tmp_path / "wiki" / "concepts" / "Draft.md",
          {"title": "Draft chunking", "type": "concept", "lifecycle": "draft"},
          "## Summary\n\nChunking draft page.")
    _page(tmp_path / "wiki" / "concepts" / "Reviewed.md",
          {"title": "Reviewed chunking", "type": "concept", "lifecycle": "reviewed"},
          "## Summary\n\nChunking reviewed page.")
    with patch.object(cli, "REPO_ROOT", tmp_path), patch.object(server, "REPO_ROOT", tmp_path):
        rc, out, _ = _run(["chunking", "--lifecycle", "reviewed", "--json"], capsys)
    assert rc == 0
    paths = [hit["path"] for hit in json.loads(out)["hits"]]
    assert paths == ["wiki/concepts/Reviewed.md"]
