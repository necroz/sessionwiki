"""Compact ``wiki_search`` output and lenient boolean arguments.

Real ZCode calls with include_raw=true returned a median of 22.7k chars,
and up to a fifth of the snippets did not contain the term: the snippet
was the first 200 chars of a long transcript line. Hits are now grouped
per file, snippets are centred on the match, and newer transcripts come
first.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_query, tool_wiki_search


def _search(root: Path, **args) -> dict:
    with patch.object(server, "REPO_ROOT", root):
        result = tool_wiki_search(args)
    assert result["isError"] is False, result["content"][0]["text"]
    return json.loads(result["content"][0]["text"])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_snippet_is_centred_on_a_late_match(tmp_path: Path):
    _write(tmp_path / "wiki" / "p.md", "x" * 500 + " needle " + "y" * 500 + "\n")
    data = _search(tmp_path, term="needle")
    snippet = data["files"][0]["lines"][0][1]
    assert "needle" in snippet
    assert len(snippet) <= 202  # 200 chars plus the two ellipsis marks


def test_hits_are_grouped_per_file_with_a_line_cap(tmp_path: Path):
    _write(tmp_path / "wiki" / "a.md", "\n".join(f"needle {i}" for i in range(10)))
    _write(tmp_path / "wiki" / "b.md", "needle once\n")
    data = _search(tmp_path, term="needle")
    assert data["match_count"] == 11
    by_path = {f["path"]: f for f in data["files"]}
    assert by_path["wiki/a.md"]["hits"] == 10
    assert len(by_path["wiki/a.md"]["lines"]) == 3
    assert by_path["wiki/a.md"]["lines"][0] == [1, "needle 0"]
    assert by_path["wiki/b.md"]["hits"] == 1


def test_file_list_is_capped_and_reports_the_rest(tmp_path: Path):
    for n in range(server._SEARCH_FILES_SHOWN + 5):
        _write(tmp_path / "wiki" / f"p{n:03d}.md", "needle\n")
    data = _search(tmp_path, term="needle")
    assert len(data["files"]) == server._SEARCH_FILES_SHOWN
    assert data["more_files"] == 5
    assert data["match_count"] == server._SEARCH_FILES_SHOWN + 5


def test_output_is_compact_json(tmp_path: Path):
    _write(tmp_path / "wiki" / "p.md", "needle\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        text = tool_wiki_search({"term": "needle"})["content"][0]["text"]
    assert "\n" not in text


def test_newest_transcripts_are_searched_first(tmp_path: Path):
    raw = tmp_path / "raw" / "sessions"
    _write(raw / "2026-01-01T10-00-proj-old.md", "needle\n")
    _write(raw / "2026-11-01T10-00-proj-new.md", "needle\n")
    (tmp_path / "wiki").mkdir()
    data = _search(tmp_path, term="needle", include_raw=True)
    paths = [f["path"] for f in data["files"]]
    assert paths == [
        "raw/sessions/2026-11-01T10-00-proj-new.md",
        "raw/sessions/2026-01-01T10-00-proj-old.md",
    ]


# ─── boolean arguments sent as strings ───────────────────────────────


@pytest.mark.parametrize("value, expected", [
    (True, True), (False, False), (None, None),
    ("true", True), ("True", True), ("1", True), ("yes", True),
    ("false", False), ("FALSE", False), ("0", False), ("no", False),
    ("maybe", None), (1, True), (0, False),
])
def test_bool_arg(value, expected):
    assert server._bool_arg(value) is expected


def test_search_string_false_keeps_raw_out(tmp_path: Path):
    _write(tmp_path / "wiki" / "p.md", "nothing here\n")
    _write(tmp_path / "raw" / "sessions" / "s.md", "needle\n")
    data = _search(tmp_path, term="needle", include_raw="false")
    assert data["match_count"] == 0


def test_query_string_false_keeps_transcripts_out(tmp_path: Path):
    _write(tmp_path / "wiki" / "concepts" / "P.md",
           "---\ntitle: P\ntype: concept\n---\n\nnothing relevant\n")
    _write(tmp_path / "raw" / "sessions" / "s.md",
           "---\nslug: s\n---\n\nneedle in a transcript\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = tool_wiki_query({"question": "needle", "include_raw": "false"})
    assert "raw/sessions/s.md" not in result["content"][0]["text"]
