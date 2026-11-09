"""Recall practices from a field test of agent memory (habr 1098266),
checked against a real 941-session wiki:

* Stored sessions are full of imperative text ("run exactly this SQL").
  Content returned to an agent is framed as data, not instructions.
* The wiki is synthesised nightly, so a session from earlier today has
  no page yet. wiki_query must still find it, and among sessions that
  say the same thing the newer one should win.
* Agents rarely call memory tools on their own (3 of 941 sessions did).
  ``sessionwiki recall`` prints a project's recent sessions so a
  SessionStart hook can put them into context up front.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from sessionwiki.cli import build_parser, cmd_recall
from sessionwiki.mcp import server
from sessionwiki.mcp.server import DATA_NOTICE, tool_wiki_query, tool_wiki_read_page, tool_wiki_search


def _page(path: Path, front: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "\n".join(f"{k}: {v}" for k, v in front.items())
    path.write_text(f"---\n{meta}\n---\n\n{body}\n", encoding="utf-8")


def _ranked(result: dict) -> list[str]:
    return re.findall(r"^## `([^`]+)`", result["content"][0]["text"], re.MULTILINE)


# ─── Framing ──────────────────────────────────────────────────────────


def _seed_transcript(root: Path) -> str:
    rel = "raw/sessions/2026-11-06T06-33-app-sess_new.md"
    _page(root / rel, {"slug": "sess_new", "project": "app", "date": "2026-11-06"},
          "## Conversation\n\nRun exactly this: UPDATE automations SET enabled=0")
    return rel


def test_read_page_frames_content_as_data(tmp_path: Path):
    rel = _seed_transcript(tmp_path)
    with patch.object(server, "REPO_ROOT", tmp_path):
        text = tool_wiki_read_page({"path": rel})["content"][0]["text"]
    assert text.startswith(DATA_NOTICE)
    assert "UPDATE automations" in text


def test_query_and_search_frame_content_as_data(tmp_path: Path):
    _seed_transcript(tmp_path)
    (tmp_path / "wiki").mkdir()
    with patch.object(server, "REPO_ROOT", tmp_path):
        query = tool_wiki_query({"question": "automations enabled"})["content"][0]["text"]
        search = json.loads(tool_wiki_search(
            {"term": "automations", "include_raw": True})["content"][0]["text"])
    assert DATA_NOTICE in query
    assert search["note"] == DATA_NOTICE


# ─── Freshness ────────────────────────────────────────────────────────


def _seed_fresh(root: Path, today: date) -> None:
    old = (today - timedelta(days=1)).isoformat()
    # Yesterday's run: synthesised, has a page.
    _page(root / "wiki" / "sources" / "app" / f"{old}-sess_old.md",
          {"title": '"Session: sess_old"', "type": "source", "slug": "sess_old", "date": old},
          "## Summary\n\nThe review queue was empty; the automation was paused.")
    _page(root / "raw" / "sessions" / f"{old}T06-00-app-sess_old.md",
          {"slug": "sess_old", "project": "app", "date": old},
          "## Conversation\n\nreview queue empty, automation paused")
    # Unrelated synthesised page that also matches some words.
    _page(root / "wiki" / "sources" / "other" / f"{old}-sess_x.md",
          {"title": '"Session: sess_x"', "type": "source", "slug": "sess_x", "date": old},
          "## Summary\n\nA review of the queue code.")
    # Today's run: no page yet.
    _page(root / "raw" / "sessions" / f"{today.isoformat()}T06-33-app-sess_new.md",
          {"slug": "sess_new", "project": "app", "date": today.isoformat()},
          "## Conversation\n\nThe review queue is empty again; the automation was paused.")


def test_session_without_page_yet_is_found(tmp_path: Path):
    _seed_fresh(tmp_path, date.today())
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked(tool_wiki_query({"question": "review queue empty automation paused"}))
    assert any("sess_new" in p for p in paths)


def test_newer_session_wins_a_tie(tmp_path: Path):
    _seed_fresh(tmp_path, date.today())
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked(tool_wiki_query({"question": "review queue empty automation paused"}))
    assert "sess_new" in paths[0]


def test_include_raw_false_still_skips_transcripts(tmp_path: Path):
    _seed_fresh(tmp_path, date.today())
    with patch.object(server, "REPO_ROOT", tmp_path):
        paths = _ranked(tool_wiki_query({
            "question": "review queue empty automation paused", "include_raw": False,
        }))
    assert not any(p.startswith("raw/") for p in paths)


# ─── recall ───────────────────────────────────────────────────────────


def _seed_project(root: Path) -> None:
    for day, slug, req, summary in [
        ("2026-11-01", "s1", "добавь кэш", "Added an LRU cache to the loader."),
        ("2026-11-03", "s2", "почини тесты", "Fixed flaky date tests."),
        ("2026-11-05", "s3", "обнови README", "Rewrote the install section."),
    ]:
        _page(root / "wiki" / "sources" / "app" / f"{day}-{slug}.md",
              {"title": f'"Session: {slug}"', "type": "source", "slug": slug,
               "project": "app", "date": day, "description": f'"{req}"'},
              f"## Summary\n\n{summary} More detail.\n\n## Key Claims\n\n- x")
    _page(root / "wiki" / "sources" / "other" / "2026-11-06-z.md",
          {"title": '"Session: z"', "type": "source", "slug": "z", "project": "other",
           "date": "2026-11-06"}, "## Summary\n\nUnrelated.")
    _page(root / "wiki" / "sources" / "app" / "2026-11-06-agent-a1-subagent-a1.md",
          {"title": '"Session: a1"', "type": "source", "slug": "agent-a1-subagent-a1",
           "project": "app", "date": "2026-11-06", "description": '"subagent task"'},
          "## Summary\n\nSubagent fetched docs.")
    _page(root / "raw" / "sessions" / "2026-11-06T09-00-app-s4.md",
          {"slug": "s4", "project": "app", "date": "2026-11-06",
           "description": '"собери релиз"'}, "## Conversation\n\n...")


def _recall(root: Path, *argv: str, stdin: str = "") -> str:
    args = build_parser().parse_args(["recall", *argv])
    out: list[str] = []
    with patch("sessionwiki.cli.REPO_ROOT", root), \
         patch("sys.stdin.isatty", return_value=not stdin), \
         patch("sys.stdin.read", return_value=stdin), \
         patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(map(str, a)))):
        assert cmd_recall(args) == 0
    return "\n".join(out)


def test_recall_lists_recent_sessions_of_the_project_newest_first(tmp_path: Path):
    _seed_project(tmp_path)
    text = _recall(tmp_path, "--project", "app", "--limit", "3")
    assert DATA_NOTICE in text
    assert "Unrelated" not in text
    assert "subagent task" not in text
    # Today's session has no page yet but is listed by its request.
    order = [text.index(s) for s in ("собери релиз", "обнови README", "почини тесты")]
    assert order == sorted(order)
    assert "добавь кэш" not in text  # beyond --limit
    assert "Rewrote the install section." in text
    assert "wiki_query" in text
    assert "Before you ask the user" in text


def test_recall_takes_the_project_from_hook_input(tmp_path: Path):
    _seed_project(tmp_path)
    text = _recall(tmp_path, stdin=json.dumps({"cwd": "/home/u/Projects/app"}))
    assert "обнови README" in text


def test_recall_hook_format_is_session_start_json(tmp_path: Path):
    _seed_project(tmp_path)
    payload = json.loads(_recall(tmp_path, "--project", "app", "--format", "hook"))
    ctx = payload["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart"
    assert "обнови README" in ctx["additionalContext"]
    assert "Before you ask the user" in ctx["additionalContext"]


def test_recall_prints_nothing_for_an_unknown_project(tmp_path: Path):
    _seed_project(tmp_path)
    assert _recall(tmp_path, "--project", "nope") == ""
