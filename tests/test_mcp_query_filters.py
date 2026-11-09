"""Filters for ``wiki_query`` and ``sessionwiki query`` (card 20).

Five frontmatter filters narrow the ranked search: ``project``, ``type``,
``tag``, ``date_from`` and ``date_to``. A page that fails them is skipped
before it is collected, before it is registered as a raw target and before
it enters the link graph, so the one-hop neighbour bonus cannot pull it
back in.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from sessionwiki import cli
from sessionwiki.cli import build_parser
from sessionwiki.mcp import server
from sessionwiki.mcp.server import rank_query, tool_wiki_query

SHARED = "SharedTopic"
ALPHA = "wiki/sources/app/2026-11-01-alpha.md"
WIDGETRY = "wiki/concepts/Widgetry.md"
WIDGET_TOOLS = "wiki/concepts/WidgetTools.md"
OTHER = "wiki/concepts/OtherThing.md"


def _page(path: Path, front: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "\n".join(f"{k}: {v}" for k, v in front.items())
    path.write_text(f"---\n{meta}\n---\n\n{body}\n", encoding="utf-8")


def _seed(root: Path) -> None:
    """Two projects, two dates, two tags, and one page only the hop finds.

    ``OtherThing`` belongs to ``other`` and links to the name both ``app``
    hits carry: without filters it enters through the graph hop, with a
    ``project`` filter it must not. The filler pages keep the link name
    below ``_GRAPH_MAX_DF_SHARE`` so the hop stays active in the fixture.
    """
    _page(root / "wiki" / "index.md", {"title": "Index", "type": "navigation"},
          "- [Widgetry](concepts/Widgetry.md)")
    _page(root / "wiki" / "overview.md", {"title": "Overview", "type": "synthesis"},
          "The wiki of a small demo project.")
    _page(root / "wiki" / "sources" / "app" / "2026-11-01-alpha.md",
          {"title": "Session alpha", "type": "source", "slug": "alpha",
           "project": "app", "tags": "[zcode, session-transcript]",
           "date": "2026-11-01"},
          "## Summary\n\nThe session wired the widget pipeline for app.\n\n"
          f"## Connections\n\n- [[{SHARED}]] — the app session's topic.")
    _page(root / "wiki" / "concepts" / "Widgetry.md",
          {"title": "Widgetry", "type": "concept", "project": "app",
           "tags": "[zcode]", "date": "2026-11-03"},
          "## Summary\n\nWidgetry is the widget abstraction.\n\n"
          f"## Connections\n\n- [[{SHARED}]] — shared with the app session.")
    _page(root / "wiki" / "concepts" / "WidgetTools.md",
          {"title": "WidgetTools", "type": "concept", "project": "app",
           "tags": "[claude-code]", "date": "2026-11-04"},
          "## Summary\n\nWidgetTools wraps the widget for another agent.")
    _page(root / "wiki" / "concepts" / "OtherThing.md",
          {"title": "OtherThing", "type": "concept", "project": "other",
           "tags": "[claude-code]", "date": "2026-11-05"},
          f"## Summary\n\nUnrelated page.\n\n## Connections\n\n- [[{SHARED}]]")
    for n in range(60):
        _page(root / "wiki" / "concepts" / f"Filler{n}.md",
              {"title": f"Filler {n}", "type": "concept", "project": "filler",
               "tags": "[misc]", "date": "2026-10-01"},
              "## Summary\n\nA page about nothing in particular.")


def _paths(result: dict) -> list[str]:
    return [hit["path"] for hit in result["hits"]]


def test_project_filter_returns_only_that_project(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("widget", include_raw=False, filters={"project": "app"})
    assert set(_paths(result)) == {ALPHA, WIDGETRY, WIDGET_TOOLS}


def test_tag_filter_keeps_only_pages_with_the_tag(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("widget", include_raw=False, filters={"tag": "zcode"})
    assert set(_paths(result)) == {ALPHA, WIDGETRY}


def test_type_filter_keeps_only_that_page_type(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("widget", include_raw=False, filters={"type": "source"})
    assert set(_paths(result)) == {ALPHA}


def test_date_filters_keep_the_range_inclusive(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        both_bounds = rank_query(
            "widget", include_raw=False,
            filters={"date_from": "2026-11-01", "date_to": "2026-11-03"},
        )
        upper_only = rank_query(
            "widget", include_raw=False, filters={"date_to": "2026-11-02"},
        )
    # 11-01 and 11-03 are both boundaries and both stay.
    assert set(_paths(both_bounds)) == {ALPHA, WIDGETRY}
    assert set(_paths(upper_only)) == {ALPHA}


def test_a_bad_date_is_ignored_not_an_error(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        plain = rank_query("widget", include_raw=False)
        bad = rank_query(
            "widget", include_raw=False,
            filters={"date_from": "last week", "date_to": "2026-13-45"},
        )
    assert _paths(bad) == _paths(plain)


def test_filtered_page_does_not_enter_through_the_graph_hop(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        plain = rank_query("widget", include_raw=False)
        filtered = rank_query("widget", include_raw=False, filters={"project": "app"})
    via = {hit["path"]: hit["via"] for hit in plain["hits"]}
    assert via.get(OTHER) == SHARED
    assert OTHER not in _paths(filtered)
    assert set(_paths(filtered)) == {ALPHA, WIDGETRY, WIDGET_TOOLS}


def test_no_filters_is_the_previous_result(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        plain = rank_query("widget", include_raw=False)
        empty = rank_query("widget", include_raw=False, filters={})
        blanks = rank_query(
            "widget", include_raw=False,
            filters={"project": "", "tag": "", "bogus": "x"},
        )
    assert plain["hits"] == empty["hits"] == blanks["hits"]


def test_tool_wiki_query_passes_the_filters(tmp_path: Path):
    _seed(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        out = tool_wiki_query(
            {"question": "widget", "include_raw": False, "project": "app"}
        )
    text = out["content"][0]["text"]
    assert "Widgetry" in text
    assert "OtherThing" not in text


def test_raw_transcripts_are_filtered_too(tmp_path: Path):
    _seed(tmp_path)
    raw = tmp_path / "raw" / "sessions" / "2026-11-02-other-raw.md"
    _page(raw,
          {"title": "Raw other", "type": "source", "slug": "raw-other",
           "project": "other", "tags": "[claude-code]", "date": "2026-11-02"},
          "## Turn 1\n\nThe widget idea came up here too.")
    raw_path = "raw/sessions/2026-11-02-other-raw.md"
    with patch.object(server, "REPO_ROOT", tmp_path):
        all_hits = rank_query("widget", include_raw=True)
        app_hits = rank_query("widget", include_raw=True, filters={"project": "app"})
    assert raw_path in _paths(all_hits)
    assert raw_path not in _paths(app_hits)


def test_cli_exposes_all_five_filters(tmp_path: Path, capsys):
    _seed(tmp_path)
    argv = [
        "query", "widget", "--json",
        "--project", "app", "--type", "concept", "--tag", "zcode",
        "--date-from", "2026-11-01", "--date-to", "2026-11-03",
    ]
    args = build_parser().parse_args(argv)
    with patch.object(cli, "REPO_ROOT", tmp_path), \
         patch.object(server, "REPO_ROOT", tmp_path):
        rc = args.func(args)
        out = capsys.readouterr().out
    assert rc == 0
    assert [hit["path"] for hit in json.loads(out)["hits"]] == [WIDGETRY]
