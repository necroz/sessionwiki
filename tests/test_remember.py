"""`remember` stores a fact as a reviewable candidate (card 27).

The command is the explicit "remember this" path.  A fact never enters a
trusted folder: it lands in ``wiki/candidates/concepts/`` with
``status: candidate`` and ``origin: human``, and a human promotes it with
``sessionwiki candidates``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sessionwiki._frontmatter import parse_frontmatter
from sessionwiki.candidates import list_candidates
from sessionwiki.cli import main


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("sessionwiki.cli.REPO_ROOT", tmp_path)
    return tmp_path


def _concepts_dir(repo: Path) -> Path:
    return repo / "wiki" / "candidates" / "concepts"


def _meta(path: Path) -> dict:
    return parse_frontmatter(path.read_text(encoding="utf-8"))[0]


def test_writes_a_candidate_with_status_and_origin(repo: Path, capsys):
    rc = main(
        [
            "remember",
            "The pipeline uses a widget queue.",
            "--title",
            "Widget queue",
            "--project",
            "demo",
        ]
    )

    assert rc == 0
    path = _concepts_dir(repo) / "WidgetQueue.md"
    assert path.is_file()
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["title"] == "Widget queue"
    assert meta["type"] == "concept"
    assert meta["status"] == "candidate"
    assert meta["origin"] == "human"
    assert meta["project"] == "demo"
    assert meta["tags"] == ["remembered", "demo"]
    assert meta["sources"] == []
    assert "The pipeline uses a widget queue." in body
    assert "- [[Demo]] — project" in body

    out = capsys.readouterr().out
    assert "wiki/candidates/concepts/WidgetQueue.md" in out
    assert "review with: sessionwiki candidates list" in out
    # Never straight into the trusted wiki.
    assert not (repo / "wiki" / "concepts" / "WidgetQueue.md").exists()


def test_candidates_list_shows_the_fact(repo: Path):
    main(["remember", "The vault keeps secrets.", "--project", "demo"])

    items = list_candidates(repo / "wiki")

    assert [c["slug"] for c in items] == ["TheVaultKeepsSecrets"]
    assert items[0]["kind"] == "concepts"
    assert items[0]["title"] == "The vault keeps secrets."
    assert items[0]["created"] == datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_second_call_with_the_same_title_adds_a_suffix(repo: Path):
    for _ in range(2):
        rc = main(
            [
                "remember",
                "Same fact.",
                "--title",
                "Same fact",
                "--project",
                "demo",
            ]
        )
        assert rc == 0

    names = sorted(p.name for p in _concepts_dir(repo).glob("*.md"))
    assert names == ["SameFact-2.md", "SameFact.md"]


def test_cyrillic_fact_gets_a_cyrillic_name(repo: Path):
    rc = main(
        [
            "remember",
            "В проекте используется очередь виджетов.",
            "--project",
            "demo",
        ]
    )

    assert rc == 0
    path = _concepts_dir(repo) / "ВПроектеИспользуетсяОчередьВиджетов.md"
    assert path.is_file()
    assert _meta(path)["title"] == "В проекте используется очередь виджетов."


def test_title_defaults_to_the_first_eight_words(repo: Path):
    rc = main(
        [
            "remember",
            "one two three four five six seven eight nine ten",
            "--project",
            "demo",
        ]
    )

    assert rc == 0
    path = _concepts_dir(repo) / "OneTwoThreeFourFiveSixSevenEight.md"
    assert path.is_file()
    assert _meta(path)["title"] == "one two three four five six seven eight"


def test_project_defaults_to_the_current_folder(repo: Path, monkeypatch: pytest.MonkeyPatch):
    work = repo / "demo-folder"
    work.mkdir()
    monkeypatch.chdir(work)

    rc = main(["remember", "A fact.", "--title", "A fact"])

    assert rc == 0
    assert _meta(_concepts_dir(repo) / "AFact.md")["project"] == "demo-folder"
