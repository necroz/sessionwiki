"""``recall --prompt-hook``: a UserPromptSubmit hook that pushes related
past work into context when the user sends a prompt (card 29).

The hook runs on **every** prompt, so it is opt-in
(``SESSIONWIKI_PROMPT_RECALL=1``) and silent on every error path. A broken
hook must never block the user's prompt.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from sessionwiki.cli import build_parser, cmd_recall
from sessionwiki.mcp import server
from sessionwiki.mcp.server import DATA_NOTICE

_PROMPT = "how did we chunk large sessions in synthesis"
_TARGET = "wiki/sources/app/2026-11-05-cache.md"


def _page(path: Path, front: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = "\n".join(f"{k}: {v}" for k, v in front.items())
    path.write_text(f"---\n{meta}\n---\n\n{body}\n", encoding="utf-8")


def _seed(root: Path) -> None:
    """The same words in two projects; only ``app`` may reach the context."""
    for project, slug, parent in [
        ("app", "cache", "app"),
        ("other", "cache-other", "other"),
    ]:
        _page(
            root / "wiki" / "sources" / parent / f"2026-11-05-{slug}.md",
            {
                "title": f'"Session: {slug}"',
                "type": "source",
                "slug": slug,
                "project": project,
                "date": "2026-11-05",
                "description": f'"{_PROMPT}"',
            },
            "## Summary\n\nChunked large sessions by token budget before synthesis.",
        )


def _hook(
    root: Path,
    monkeypatch,
    *,
    stdin: str = "",
    enabled: bool = True,
    rank_query=None,
    min_score: float = 0.0,
) -> tuple[str, int]:
    """Run ``recall --prompt-hook`` against a seeded wiki; return (out, rc).

    The threshold is pinned low by default: the production value is
    calibrated on real sessions and is not what these tests check.
    """
    if enabled:
        monkeypatch.setenv("SESSIONWIKI_PROMPT_RECALL", "1")
    else:
        monkeypatch.delenv("SESSIONWIKI_PROMPT_RECALL", raising=False)
    args = build_parser().parse_args(["recall", "--prompt-hook"])
    out: list[str] = []
    with (
        patch("sessionwiki.cli._PROMPT_RECALL_MIN_SCORE", min_score),
        patch("sessionwiki.cli.REPO_ROOT", root),
        patch.object(server, "REPO_ROOT", root),
        patch("sys.stdin.read", return_value=stdin),
        patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(map(str, a)))),
    ):
        if rank_query is None:
            rc = cmd_recall(args)
        else:
            with patch.object(server, "rank_query", rank_query):
                rc = cmd_recall(args)
    return "\n".join(out), rc


def test_without_the_env_var_prints_nothing(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    out, rc = _hook(
        tmp_path, monkeypatch, stdin=json.dumps({"prompt": _PROMPT, "cwd": "/home/u/Projects/app"}), enabled=False
    )
    assert (out, rc) == ("", 0)


def test_short_prompt_and_slash_command_print_nothing(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    for prompt in ("chunk", "/wiki-query chunk large sessions in synthesis"):
        out, rc = _hook(tmp_path, monkeypatch, stdin=json.dumps({"prompt": prompt, "cwd": "/home/u/Projects/app"}))
        assert (out, rc) == ("", 0)


def test_matching_prompt_emits_user_prompt_submit_json(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    out, rc = _hook(tmp_path, monkeypatch, stdin=json.dumps({"prompt": _PROMPT, "cwd": "/home/u/Projects/app"}))
    assert rc == 0
    payload = json.loads(out)
    ctx = payload["hookSpecificOutput"]
    assert ctx["hookEventName"] == "UserPromptSubmit"
    assert _TARGET in ctx["additionalContext"]
    assert DATA_NOTICE in ctx["additionalContext"]
    assert "wiki_read_page" in ctx["additionalContext"]


def test_pages_of_another_project_are_not_included(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    out, rc = _hook(tmp_path, monkeypatch, stdin=json.dumps({"prompt": _PROMPT, "cwd": "/home/u/Projects/app"}))
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert _TARGET in ctx
    assert "wiki/sources/other/" not in ctx


def test_hits_below_the_threshold_print_nothing(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    out, rc = _hook(
        tmp_path, monkeypatch, stdin=json.dumps({"prompt": _PROMPT, "cwd": "/home/u/Projects/app"}), min_score=1e9
    )
    assert (out, rc) == ("", 0)


def test_broken_stdin_json_prints_nothing(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    for stdin in ("{not json", json.dumps(["not", "a", "dict"])):
        out, rc = _hook(tmp_path, monkeypatch, stdin=stdin)
        assert (out, rc) == ("", 0)


def test_rank_query_failure_prints_nothing(tmp_path: Path, monkeypatch):
    _seed(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("ranking exploded")

    out, rc = _hook(
        tmp_path, monkeypatch, stdin=json.dumps({"prompt": _PROMPT, "cwd": "/home/u/Projects/app"}), rank_query=_boom
    )
    assert (out, rc) == ("", 0)
