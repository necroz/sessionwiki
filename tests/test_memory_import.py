"""`import-memory` mirrors Claude Code auto memory into ``wiki/notes`` (card 26).

Claude Code writes ``~/.claude/projects/<dir>/memory/*.md``.  The mirror keeps
those files out of the immutable ``raw/`` tree, marks every page
``origin: human`` and never overwrites a page the import does not own.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sessionwiki._frontmatter import parse_frontmatter
from sessionwiki.mcp import server
from sessionwiki.memory_import import import_claude_memory

PROJECT_DIR = "-Users-USER-Desktop-demo"
PROJECT = "demo"
DEST = Path("notes") / "claude-memory" / PROJECT
SECRET = "ghp_" + "A" * 30


def _seed(store: Path) -> None:
    memory = store / PROJECT_DIR / "memory"
    memory.mkdir(parents=True)
    (memory / "MEMORY.md").write_text(
        "---\n"
        "name: Main memory\n"
        "description: How this project is wired\n"
        "metadata:\n"
        "  type: project\n"
        "---\n\n"
        "The project uses a widget pipeline.\n",
        encoding="utf-8",
    )
    (memory / "topic.md").write_text(
        "Flutter screens call the kumquat endpoint.\n", encoding="utf-8"
    )


def _import(store: Path, wiki: Path, **kwargs):
    return import_claude_memory(store, wiki, {}, **kwargs)


def _meta(path: Path) -> dict:
    return parse_frontmatter(path.read_text(encoding="utf-8"))[0]


def test_mirrors_memory_files_with_origin_human(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)

    result = _import(store, wiki)

    assert sorted(result["written"]) == [
        "notes/claude-memory/demo/MEMORY.md",
        "notes/claude-memory/demo/topic.md",
    ]
    assert result["unchanged"] == 0
    for name in ("MEMORY.md", "topic.md"):
        text = (wiki / DEST / name).read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        assert meta["type"] == "note"
        assert meta["origin"] == "human"
        assert meta["project"] == PROJECT
        assert "- [[Demo]] — project" in body

    assert _meta(wiki / DEST / "MEMORY.md")["description"] == (
        "How this project is wired"
    )


def test_source_path_is_home_relative(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)

    _import(store, wiki)

    source_path = _meta(wiki / DEST / "MEMORY.md")["source_path"]
    assert source_path == (
        f"~/.claude/projects/{PROJECT_DIR}/memory/MEMORY.md"
    )
    assert source_path.startswith("~/.claude/projects/")


def test_second_run_is_unchanged(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)

    _import(store, wiki)
    again = _import(store, wiki)

    assert again["unchanged"] == 2
    assert again["written"] == []


def test_changed_memory_file_is_rewritten(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)
    _import(store, wiki)

    (store / PROJECT_DIR / "memory" / "topic.md").write_text(
        "New Flutter note.\n", encoding="utf-8"
    )
    result = _import(store, wiki)

    assert result["written"] == ["notes/claude-memory/demo/topic.md"]
    text = (wiki / DEST / "topic.md").read_text(encoding="utf-8")
    assert "New Flutter note." in text
    assert "kumquat" not in text


def test_a_destination_without_origin_human_is_skipped(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)
    dest = wiki / DEST
    dest.mkdir(parents=True)
    foreign = dest / "MEMORY.md"
    foreign.write_text(
        "---\ntitle: Mine\ntype: note\norigin: agent\n---\n\nKeep me.\n",
        encoding="utf-8",
    )

    result = _import(store, wiki)

    assert result["written"] == ["notes/claude-memory/demo/topic.md"]
    assert [item["path"] for item in result["skipped"]] == [
        "notes/claude-memory/demo/MEMORY.md"
    ]
    assert foreign.read_text(encoding="utf-8").endswith("Keep me.\n")


def test_secrets_are_redacted_from_body_and_description(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)
    (store / PROJECT_DIR / "memory" / "MEMORY.md").write_text(
        "---\n"
        f"description: token {SECRET} in the description\n"
        "---\n\n"
        f"The body holds {SECRET} too.\n",
        encoding="utf-8",
    )

    _import(store, wiki)

    text = (wiki / DEST / "MEMORY.md").read_text(encoding="utf-8")
    assert SECRET not in text
    assert "<REDACTED>" in text


def test_dry_run_writes_nothing(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)

    result = _import(store, wiki, dry_run=True)

    assert len(result["written"]) == 2
    assert not (wiki / "notes").exists()


def test_missing_store_is_empty(tmp_path: Path):
    result = import_claude_memory(tmp_path / "nope", tmp_path / "wiki", {})

    assert result == {"written": [], "unchanged": 0, "skipped": []}


def test_wiki_query_finds_the_imported_body(tmp_path: Path):
    store, wiki = tmp_path / "store", tmp_path / "wiki"
    _seed(store)
    _import(store, wiki)

    with patch.object(server, "REPO_ROOT", tmp_path):
        result = server.rank_query("kumquat", include_raw=False)

    paths = [hit["path"] for hit in result["hits"]]
    assert "wiki/notes/claude-memory/demo/topic.md" in paths
