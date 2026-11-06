"""Search quality of the MCP read tools (wiki_query, wiki_search).

Measured on a real 901-page wiki (2026-11-06): English questions found
the right session in the top 3 for 13 of 17 questions, Russian ones for
0 of 5, and 12 of 21 top-3 slots on the misses went to service or hub
pages. These tests pin the three causes on a synthetic corpus:

1. Service pages (``type: navigation`` / ``type: context``) are not
   answers and must not be ranked.
2. Project hub pages mention everything; they rank below the session
   page that actually holds the answer.
3. Wiki pages are synthesised in English. The user's own wording lives
   in the page's ``description`` (copied from the transcript), so the
   wiki alone answers; transcripts are only a fallback when no page
   matches, or on request with ``include_raw=true``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_query, tool_wiki_search


def _page(path: Path, front: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "\n".join(f"{k}: {v}" for k, v in front.items())
    path.write_text(f"---\n{meta}\n---\n\n{body}\n", encoding="utf-8")


def _ranked_paths(result: dict) -> list[str]:
    return re.findall(r"^## `([^`]+)`", result["content"][0]["text"], re.MULTILINE)


def _seed(root: Path) -> None:
    wiki = root / "wiki"
    # The session page that answers the question.
    _page(
        wiki / "sources" / "shop" / "2026-07-25-sess_aaa.md",
        {"title": '"Session: sess_aaa"', "type": "source", "slug": "sess_aaa"},
        "Fixed the store filter that was lost when navigating to room layouts.",
    )
    # A service page that happens to contain the same words.
    _page(
        wiki / "sources" / "_context.md",
        {"title": '"Sources folder"', "type": "context"},
        "Session pages, e.g. the store filter lost when navigating to room layouts.",
    )
    _page(
        wiki / "hints.md",
        {"title": '"Hints"', "type": "navigation"},
        "store filter room layouts navigating lost",
    )
    # A long project hub page that mentions everything.
    _page(
        wiki / "projects" / "shop.md",
        {"title": '"shop"', "type": "entity", "entity_type": "project"},
        "Overview. " + "store filter lost when navigating to room layouts. " * 3,
    )
    # An English page that keeps the user's Russian request.
    _page(
        wiki / "sources" / "car" / "2026-10-26-sess_bbb.md",
        {"title": '"Session: sess_bbb"', "type": "source", "slug": "sess_bbb",
         "description": '"Как поменять лампу ближнего света на поло седан?"'},
        "Replaced a burnt-out low-beam headlight bulb on a 2018 sedan.",
    )
    # An English page whose Russian wording only the transcript has.
    _page(
        wiki / "sources" / "pc" / "2026-10-27-sess_ddd.md",
        {"title": '"Session: sess_ddd"', "type": "source", "slug": "sess_ddd"},
        "Diagnosed a laptop fan that runs at full speed.",
    )
    _page(
        root / "raw" / "sessions" / "2026-10-27T10-00-pc-sess_ddd.md",
        {"title": '"Session: sess_ddd"', "type": "source", "slug": "sess_ddd", "project": "pc"},
        "## Conversation\n\nПочему вентилятор ноутбука гудит на полной скорости?",
    )
    _page(
        root / "raw" / "sessions" / "2026-10-26T10-00-car-sess_bbb.md",
        {"title": '"Session: sess_bbb"', "type": "source", "slug": "sess_bbb", "project": "car"},
        "## Conversation\n\nКак поменять лампу ближнего света на поло седан?",
    )
    # A transcript with no wiki page yet.
    _page(
        root / "raw" / "sessions" / "2026-11-01T10-00-misc-sess_ccc.md",
        {"title": '"Session: sess_ccc"', "type": "source", "slug": "sess_ccc", "project": "misc"},
        "## Conversation\n\nСколько калорий сжигается при подъёме на пять этажей?",
    )


def test_service_pages_are_not_ranked(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(tool_wiki_query({"question": "store filter lost room layouts"}))
    assert "wiki/sources/_context.md" not in paths
    assert "wiki/hints.md" not in paths


def test_session_page_outranks_project_hub(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(tool_wiki_query({"question": "store filter lost room layouts"}))
    assert paths[0] == "wiki/sources/shop/2026-07-25-sess_aaa.md"
    assert "wiki/projects/shop.md" in paths


def test_question_in_users_language_finds_the_page_by_its_description(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(
            tool_wiki_query({"question": "как поменять лампу ближнего света на поло седан"})
        )
    assert paths[0] == "wiki/sources/car/2026-10-26-sess_bbb.md"


def test_include_raw_true_credits_transcript_hits_to_the_session_page(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(tool_wiki_query({
            "question": "почему вентилятор ноутбука гудит", "include_raw": True,
        }))
    assert paths[0] == "wiki/sources/pc/2026-10-27-sess_ddd.md"


def test_transcripts_of_synthesised_sessions_are_not_read_in_full(tmp_path: Path):
    """While the wiki has an answer, a transcript whose session already
    has a page is skipped after its frontmatter; only sessions without a
    page yet are read in full (see test_mcp_recall.py for freshness)."""
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path), \
         patch.object(server, "_read_capped", wraps=server._read_capped) as reads:
        tool_wiki_query({"question": "store filter lost room layouts"})
    read = [str(call.args[0]) for call in reads.call_args_list]
    assert not any("sess_bbb" in p or "sess_ddd" in p for p in read if "/raw/" in p)


def test_falls_back_to_transcript_without_wiki_page(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(
            tool_wiki_query({"question": "сколько калорий сжигается при подъёме на пять этажей"})
        )
    assert paths[0] == "raw/sessions/2026-11-01T10-00-misc-sess_ccc.md"


def test_include_raw_false_keeps_query_on_wiki_pages(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(
            tool_wiki_query({"question": "сколько калорий пять этажей", "include_raw": False})
        )
    assert not any(p.startswith("raw/") for p in paths)


def test_search_reports_when_the_byte_budget_cut_the_scan(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path), \
         patch.object(server, "_MCP_SCAN_AGGREGATE_BYTES", 200):
        payload = json.loads(
            tool_wiki_search({"term": "zzz-not-there", "include_raw": True})["content"][0]["text"]
        )
    assert payload["scan_incomplete"] is True
    assert payload["files_scanned"] < payload["files_total"]


def test_search_reports_a_complete_scan(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        payload = json.loads(
            tool_wiki_search({"term": "zzz-not-there", "include_raw": True})["content"][0]["text"]
        )
    assert payload["scan_incomplete"] is False
    assert payload["files_scanned"] == payload["files_total"]


def test_rare_word_outweighs_common_words(tmp_path: Path):
    """BM25-style IDF: a page with the one rare query word beats a page
    with two words that every page contains."""
    wiki = tmp_path / "wiki"
    for i in range(6):
        _page(
            wiki / "sources" / "p" / f"2026-01-0{i + 1}-sess_c{i}.md",
            {"title": f'"Session {i}"', "type": "source"},
            "как сделать дома что-нибудь полезное",
        )
    _page(
        wiki / "sources" / "p" / "2026-02-01-sess_rare.md",
        {"title": '"Session rare"', "type": "source"},
        "панариций на пальце",
    )
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked_paths(tool_wiki_query({"question": "как дома лечить панариций"}))
    assert paths[0] == "wiki/sources/p/2026-02-01-sess_rare.md"
