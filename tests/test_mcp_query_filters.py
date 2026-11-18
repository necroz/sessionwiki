"""Filters for ``wiki_query`` and ``sessionwiki query`` (card 20).

Five frontmatter filters narrow the ranked search: ``project``, ``type``,
``tag``, ``date_from`` and ``date_to``. A page that fails them is skipped
before it is collected, before it is registered as a raw target and before
it enters the link graph, so the one-hop neighbour bonus cannot pull it
back in.

The last two tests cover the ranking weight for ``stale`` and ``archived``
pages (card 21): retired answers sink but stay in the results.
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


# ── Lifecycle weight (card 21) ────────────────────────────────────────
# A page marked ``stale`` or ``archived`` ranks lower but is never removed:
# the weight shrinks its score, it does not filter the page out.

FRESH_TWIN = "wiki/concepts/PipelineAnswer.md"
STALE_TWIN = "wiki/concepts/PipelineAnswerStale.md"
BETTER_ARCHIVED = "wiki/concepts/PipelineAnswerArchived.md"


def test_a_stale_page_ranks_below_its_fresh_twin(tmp_path: Path):
    body = "## Summary\n\nThe widget pipeline answer lives here."
    _page(tmp_path / FRESH_TWIN,
          {"title": "Pipeline answer", "type": "concept",
           "date": "2026-11-01"}, body)
    _page(tmp_path / STALE_TWIN,
          {"title": "Pipeline answer", "type": "concept",
           "date": "2026-11-01", "lifecycle": "stale"}, body)
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("widget pipeline", include_raw=False)
    paths = _paths(result)
    # Same words, same date: only the lifecycle weight separates them.
    assert set(paths) == {FRESH_TWIN, STALE_TWIN}
    assert paths[0] == FRESH_TWIN
    scores = {hit["path"]: hit["score"] for hit in result["hits"]}
    assert scores[FRESH_TWIN] > scores[STALE_TWIN]


def test_a_better_match_archived_page_is_lower_not_removed(tmp_path: Path):
    _page(tmp_path / FRESH_TWIN,
          {"title": "Widget pipeline", "type": "concept",
           "date": "2026-11-01"},
          "## Summary\n\nThe widget pipeline answer.")
    # The archived page matches every word the fresh one does, plus a rare
    # "connectors": a strictly better lexical match that still sinks.
    _page(tmp_path / BETTER_ARCHIVED,
          {"title": "Widget pipeline connectors", "type": "concept",
           "date": "2026-11-01", "lifecycle": "archived"},
          "## Summary\n\nThe widget pipeline connectors answer.")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("widget pipeline", include_raw=False)
    paths = _paths(result)
    assert BETTER_ARCHIVED in paths
    assert paths[0] == FRESH_TWIN
    scores = {hit["path"]: hit["score"] for hit in result["hits"]}
    assert scores[FRESH_TWIN] > scores[BETTER_ARCHIVED]


def _lifecycle_page(root: Path, slug: str, state: str) -> None:
    front = {"title": slug, "type": "concept"}
    if state:
        front["lifecycle"] = state
    _page(root / "wiki" / "concepts" / f"{slug}.md", front,
          "## Summary\n\nWidget lifecycle states.")


def test_lifecycle_filter_keeps_only_the_listed_states(tmp_path: Path):
    for slug, state in [("draft-page", "draft"), ("reviewed-page", "reviewed"),
                        ("verified-page", "verified"), ("no-state-page", "")]:
        _lifecycle_page(tmp_path, slug, state)
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query(
            "widget", include_raw=False, filters={"lifecycle": "reviewed,verified"},
        )
    assert {Path(p).stem for p in _paths(result)} == {"reviewed-page", "verified-page"}


def test_lifecycle_filter_ignores_case_and_spaces(tmp_path: Path):
    _lifecycle_page(tmp_path, "reviewed-page", "reviewed")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query(
            "widget", include_raw=False, filters={"lifecycle": " Reviewed , VERIFIED "},
        )
    assert {Path(p).stem for p in _paths(result)} == {"reviewed-page"}


# ─── canonical-parser regressions (MCP surface refactor, Task 3) ─────


def test_query_tag_filter_matches_block_list_tags(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "BlockTags.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: BlockTags\ntype: concept\ntags:\n  - blocktag\n---\n\nBlock list tags page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("block", include_raw=False, filters={"tag": "blocktag"})
    assert "wiki/concepts/BlockTags.md" in _paths(result)


def test_query_filter_sees_bom_prefixed_page(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "BomPage.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\ufeff---\ntitle: BomPage\ntype: concept\nproject: bomproj\n---\n\nBom page body.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("bom", include_raw=False, filters={"project": "bomproj"})
    assert "wiki/concepts/BomPage.md" in _paths(result)


def test_query_tag_filter_boolish_tags_stay_strings(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "BoolTags.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: BoolTags\ntype: concept\ntags: [no, yes]\n---\n\nBool tags body.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("bool", include_raw=False, filters={"tag": "no"})
    assert "wiki/concepts/BoolTags.md" in _paths(result)


def test_raw_fallback_merges_bom_transcript_by_slug(tmp_path: Path):
    w = tmp_path / "wiki" / "sources" / "BomRaw.md"
    w.parent.mkdir(parents=True, exist_ok=True)
    w.write_text("---\ntitle: BomRaw\ntype: source\nslug: bomraw\n---\n\nCompiled page.\n")
    r = tmp_path / "raw" / "sessions" / "bom.md"
    r.parent.mkdir(parents=True, exist_ok=True)
    r.write_text("\ufeff---\nslug: bomraw\n---\n\nuniquequerytoken in the transcript.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("uniquequerytoken")  # no wiki hit -> raw fallback
    assert "wiki/sources/BomRaw.md" in _paths(result)
    assert "raw/sessions/bom.md" not in _paths(result)


# ─── scalar bool-looking values keep their YAML spelling (review fix) ─


def test_query_tag_filter_matches_scalar_boolish_tag(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "NoTag.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: NoTag\ntype: concept\ntags: no\n---\n\nNorwegian language page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("norwegian", include_raw=False, filters={"tag": "no"})
    assert "wiki/concepts/NoTag.md" in _paths(result)


def test_query_project_filter_matches_boolish_scalar_no(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "NoProject.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: NoProject\ntype: concept\nproject: no\n---\n\nBoolish project page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("boolish", include_raw=False, filters={"project": "no"})
    assert "wiki/concepts/NoProject.md" in _paths(result)


def test_query_project_filter_true_keeps_yaml_spelling(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "TrueProject.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: TrueProject\ntype: concept\nproject: true\n---\n\nTrue project page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("true project", include_raw=False, filters={"project": "true"})
    assert "wiki/concepts/TrueProject.md" in _paths(result)


def test_status_line_keeps_boolish_scalar_spelling(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "YesConf.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: YesConf\ntype: concept\nconfidence: yes\n---\n\nStatus spelling page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = tool_wiki_query({"question": "status spelling"})
    assert "confidence=yes" in result["content"][0]["text"]


# ─── numeric-looking scalars keep their YAML spelling (review fix) ───


def test_query_project_filter_matches_zero_padded_number(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "Bond.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Bond\ntype: concept\nproject: 007\n---\n\nAgent page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("agent", include_raw=False, filters={"project": "007"})
    assert "wiki/concepts/Bond.md" in _paths(result)


def test_status_line_keeps_float_spelling(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "Conf.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: Conf\ntype: concept\nconfidence: 0.70\n---\n\nFloat spelling page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = tool_wiki_query({"question": "float spelling"})
    assert "confidence=0.70" in result["content"][0]["text"]


def test_query_tag_filter_matches_zero_indent_block_list(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "FlatTags.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: FlatTags\ntype: concept\ntags:\n- flattag\n---\n\nFlat list page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("flat", include_raw=False, filters={"tag": "flattag"})
    assert "wiki/concepts/FlatTags.md" in _paths(result)


def test_query_type_survives_dashes_in_title(tmp_path: Path):
    p = tmp_path / "wiki" / "concepts" / "Dashes.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntitle: before---after\ntype: concept\n---\n\nDash title page.\n")
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = rank_query("dash", include_raw=False, filters={"type": "concept"})
    assert "wiki/concepts/Dashes.md" in _paths(result)
