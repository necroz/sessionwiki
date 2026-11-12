"""Card 30: guarded MCP write tools and the frontmatter writer."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from sessionwiki._frontmatter import (
    format_frontmatter_value,
    parse_frontmatter,
    set_frontmatter_fields,
)
from sessionwiki.mcp import server

GOOD_PAGE = '---\ntitle: "New page"\ntype: concept\n---\n\nBody text.\n'
UPDATE_PAGE = (
    '---\ntitle: "A"\ntype: concept\ntags: [old]\nlifecycle: draft\n---\n'
    "Body stays.\n"
)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "wiki").mkdir()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    return tmp_path


def _payload(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


def _error(result: dict) -> str:
    assert result.get("isError") is True, result
    return result["content"][0]["text"]


# ─── format_frontmatter_value / set_frontmatter_fields ─────────────────


def test_round_trip_title_tags_confidence_lifecycle():
    text = '---\ntitle: "Old"\n---\nbody\n'
    fields = {
        "title": 'Why: "quoted"',
        "tags": ["alpha", "beta-2"],
        "confidence": 0.85,
        "lifecycle": "draft",
    }
    meta, body = parse_frontmatter(set_frontmatter_fields(text, fields))
    assert meta["title"] == fields["title"]
    assert meta["tags"] == ["alpha", "beta-2"]
    assert meta["confidence"] == 0.85
    assert meta["lifecycle"] == "draft"
    assert body == "body\n"


def test_existing_block_list_becomes_inline():
    text = (
        '---\ntitle: "A"\ntags:\n  - old1\n  - old2\nlifecycle: draft\n---\n'
        "body\n"
    )
    new = set_frontmatter_fields(text, {"tags": ["new1", "new2"]})
    assert "tags: [new1, new2]" in new
    assert "- old1" not in new
    assert parse_frontmatter(new)[0]["tags"] == ["new1", "new2"]


def test_missing_key_is_appended():
    text = '---\ntitle: "A"\n---\nbody\n'
    new = set_frontmatter_fields(text, {"type": "concept"})
    assert new == '---\ntitle: "A"\ntype: "concept"\n---\nbody\n'


def test_text_without_frontmatter_gets_a_block():
    new = set_frontmatter_fields("plain text\n", {"title": "X"})
    assert new == '---\ntitle: "X"\n---\nplain text\n'


def test_body_is_byte_identical_with_crlf():
    text = '---\r\ntitle: "A"\r\n---\r\nLine 1\r\nLine 2\r\n'
    old_body = parse_frontmatter(text)[1]
    new = set_frontmatter_fields(text, {"tags": ["a"]})
    assert parse_frontmatter(new)[1] == old_body
    assert new.endswith(old_body)
    assert "\n" not in new.replace("\r\n", "")


def test_format_rejects_newline_in_value():
    with pytest.raises(ValueError):
        format_frontmatter_value("a\nb")
    with pytest.raises(ValueError):
        set_frontmatter_fields('---\ntitle: "A"\n---\n', {"title": "a\nb"})


def test_format_rejects_comma_in_tag():
    with pytest.raises(ValueError):
        format_frontmatter_value(["a,b"])


def test_format_rejects_both_quote_characters():
    with pytest.raises(ValueError):
        format_frontmatter_value('a"b\'c')


# ─── wiki_write_page ──────────────────────────────────────────────────


def test_write_page_preview_creates_nothing(repo: Path):
    result = server.tool_wiki_write_page({
        "path": "wiki/candidates/concepts/Fact.md",
        "content": GOOD_PAGE,
    })
    data = _payload(result)
    assert data["written"] is False
    assert data["action"] == "create"
    assert not (repo / "wiki" / "candidates").exists()


def test_write_page_create_with_confirm(repo: Path):
    (repo / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    result = server.tool_wiki_write_page({
        "path": "wiki/notes/New.md",
        "content": GOOD_PAGE,
        "confirm": True,
    })
    data = _payload(result)
    assert data["written"] is True
    assert data["path"] == "wiki/notes/New.md"
    page = repo / "wiki" / "notes" / "New.md"
    meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["origin"] == "agent"
    assert meta["last_updated"] == date.today().isoformat()
    assert meta["title"] == "New page"
    assert body == "\nBody text.\n"
    log = (repo / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "edit | wiki/notes/New.md (wiki_write_page: create)" in log


def test_write_page_create_refuses_existing(repo: Path):
    page = repo / "wiki" / "page.md"
    page.write_text('---\ntitle: "Old"\ntype: concept\n---\nold\n', encoding="utf-8")
    message = _error(server.tool_wiki_write_page({
        "path": "wiki/page.md", "content": GOOD_PAGE, "confirm": True,
    }))
    assert "mode='replace'" in message
    assert "old" in page.read_text(encoding="utf-8")


def test_write_page_replace_overwrites(repo: Path):
    page = repo / "wiki" / "page.md"
    page.write_text('---\ntitle: "Old"\ntype: concept\n---\nold\n', encoding="utf-8")
    result = server.tool_wiki_write_page({
        "path": "wiki/page.md",
        "content": GOOD_PAGE,
        "mode": "replace",
        "confirm": True,
    })
    assert _payload(result)["written"] is True
    meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["title"] == "New page"
    assert "old\n" not in body


def test_write_page_replace_refuses_missing(repo: Path):
    message = _error(server.tool_wiki_write_page({
        "path": "wiki/page.md",
        "content": GOOD_PAGE,
        "mode": "replace",
        "confirm": True,
    }))
    assert "mode='create'" in message


@pytest.mark.parametrize("rel", [
    "../x.md",
    "raw/sessions/a.md",
    "docs/a.md",
    "wiki/index.md",
    "wiki/sub/log.md",
    "wiki/a.txt",
    "wiki/.hidden/a.md",
    "wiki/archive/a.md",
])
def test_write_page_refuses_bad_paths(repo: Path, rel: str):
    _error(server.tool_wiki_write_page({
        "path": rel, "content": GOOD_PAGE, "confirm": True,
    }))


def test_write_page_refuses_symlink(repo: Path):
    target = repo / "outside.md"
    target.write_text(GOOD_PAGE, encoding="utf-8")
    (repo / "wiki" / "link.md").symlink_to(target)
    _error(server.tool_wiki_write_page({
        "path": "wiki/link.md",
        "content": GOOD_PAGE,
        "mode": "replace",
        "confirm": True,
    }))
    assert target.read_text(encoding="utf-8") == GOOD_PAGE


def test_write_page_requires_title(repo: Path):
    _error(server.tool_wiki_write_page({
        "path": "wiki/x.md",
        "content": "---\ntype: concept\n---\nbody\n",
        "confirm": True,
    }))
    assert not (repo / "wiki" / "x.md").exists()


def test_write_page_refuses_oversize_content(repo: Path):
    content = '---\ntitle: "X"\ntype: concept\n---\n' + "x" * (1024 * 1024)
    _error(server.tool_wiki_write_page({
        "path": "wiki/big.md", "content": content, "confirm": True,
    }))
    assert not (repo / "wiki" / "big.md").exists()


def test_write_page_never_changes_human_page(repo: Path):
    page = repo / "wiki" / "hand.md"
    original = '---\ntitle: "Hand"\ntype: concept\norigin: human\n---\nhand\n'
    page.write_text(original, encoding="utf-8")
    for mode in ("create", "replace"):
        message = _error(server.tool_wiki_write_page({
            "path": "wiki/hand.md",
            "content": GOOD_PAGE,
            "mode": mode,
            "confirm": True,
        }))
        assert "origin: human" in message
        assert page.read_text(encoding="utf-8") == original


def test_write_page_creates_candidate_pages(repo: Path):
    result = server.tool_wiki_write_page({
        "path": "wiki/candidates/concepts/Fact.md",
        "content": GOOD_PAGE,
        "confirm": True,
    })
    assert _payload(result)["written"] is True
    assert (repo / "wiki" / "candidates" / "concepts" / "Fact.md").is_file()


# ─── wiki_update_frontmatter ─────────────────────────────────────────


def test_update_replaces_tags(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    result = server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md",
        "fields": {"tags": ["one", "two"]},
        "confirm": True,
    })
    assert _payload(result)["written"] is True
    meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["tags"] == ["one", "two"]
    assert body == "Body stays.\n"
    assert meta["last_updated"] == date.today().isoformat()


def test_update_adds_and_removes_tags(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md",
        "add_tags": ["new", "old"],
        "remove_tags": ["old"],
        "confirm": True,
    })
    meta, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["tags"] == ["new"]


def test_update_keeps_block_list_tags(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(
        '---\ntitle: "A"\ntags:\n  - one\n  - two\n---\nbody\n', encoding="utf-8"
    )
    server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "add_tags": ["three"], "confirm": True,
    })
    meta, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["tags"] == ["one", "two", "three"]


@pytest.mark.parametrize("args, needle", [
    ({"fields": {"bogus": "x"}}, "allowed"),
    ({"fields": {"lifecycle": "gone"}}, "lifecycle"),
    ({"fields": {"confidence": 1.5}}, "confidence"),
    ({"fields": {"title": "bad\nvalue"}}, "newline"),
])
def test_update_rejects_bad_fields(repo: Path, args: dict, needle: str):
    page = repo / "wiki" / "a.md"
    original = UPDATE_PAGE
    page.write_text(original, encoding="utf-8")
    message = _error(server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "confirm": True, **args,
    }))
    assert needle in message.lower()
    assert page.read_text(encoding="utf-8") == original


def test_update_requires_a_change(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    _error(server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "confirm": True,
    }))


def test_update_preview_shows_changes_and_writes_nothing(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    before = page.read_text(encoding="utf-8")
    data = _payload(server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "fields": {"title": "B"},
    }))
    assert data["written"] is False
    assert data["changes"]["title"] == ["A", "B"]
    assert page.read_text(encoding="utf-8") == before


def test_update_confidence_stamps_measurement_provenance(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    data = _payload(server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "fields": {"confidence": 0.8}, "confirm": True,
    }))
    assert data["written"] is True
    meta, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["confidence_measured"] == date.today().isoformat()
    assert meta["confidence_pages"] == 1


def test_update_without_confidence_adds_no_provenance(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "fields": {"title": "B"}, "confirm": True,
    })
    meta, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert "confidence_measured" not in meta
    assert "confidence_pages" not in meta


def test_update_preview_lists_the_provenance_changes(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    data = _payload(server.tool_wiki_update_frontmatter({
        "path": "wiki/a.md", "fields": {"confidence": 0.8},
    }))
    assert data["written"] is False
    assert data["changes"]["confidence_measured"] == [None, date.today().isoformat()]
    assert data["changes"]["confidence_pages"] == [None, 1]


def test_write_page_confidence_stamps_measurement_provenance(repo: Path):
    content = '---\ntitle: "N"\ntype: concept\nconfidence: 0.7\n---\n\nBody.\n'
    data = _payload(server.tool_wiki_write_page({
        "path": "wiki/n.md", "content": content, "confirm": True,
    }))
    assert data["written"] is True
    meta, _ = parse_frontmatter((repo / "wiki" / "n.md").read_text(encoding="utf-8"))
    assert meta["confidence_measured"] == date.today().isoformat()
    # The corpus state at measurement time: the new page is not in it yet.
    assert meta["confidence_pages"] == 0


def test_update_never_changes_human_page(repo: Path):
    page = repo / "wiki" / "hand.md"
    original = '---\ntitle: "H"\ntype: concept\norigin: human\n---\nbody\n'
    page.write_text(original, encoding="utf-8")
    _error(server.tool_wiki_update_frontmatter({
        "path": "wiki/hand.md", "fields": {"title": "X"}, "confirm": True,
    }))
    assert page.read_text(encoding="utf-8") == original


# ─── wiki_archive_page ────────────────────────────────────────────────


def test_archive_sets_lifecycle_and_keeps_file(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    result = server.tool_wiki_archive_page({
        "path": "wiki/a.md", "reason": "outdated", "confirm": True,
    })
    assert _payload(result)["written"] is True
    assert page.is_file()
    meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert meta["lifecycle"] == "archived"
    assert meta["archived_reason"] == "outdated"
    assert meta["last_updated"] == date.today().isoformat()
    assert body == "Body stays.\n"


def test_archive_preview_writes_nothing(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    before = page.read_text(encoding="utf-8")
    data = _payload(server.tool_wiki_archive_page({
        "path": "wiki/a.md", "reason": "old",
    }))
    assert data["written"] is False
    assert data["previous_lifecycle"] == "draft"
    assert page.read_text(encoding="utf-8") == before


def test_archive_twice_is_a_no_op(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    server.tool_wiki_archive_page({
        "path": "wiki/a.md", "reason": "old", "confirm": True,
    })
    first = page.read_text(encoding="utf-8")
    data = _payload(server.tool_wiki_archive_page({
        "path": "wiki/a.md", "reason": "old", "confirm": True,
    }))
    assert data["written"] is False
    assert "already" in data["note"].lower()
    assert page.read_text(encoding="utf-8") == first


def test_archive_requires_reason(repo: Path):
    page = repo / "wiki" / "a.md"
    page.write_text(UPDATE_PAGE, encoding="utf-8")
    _error(server.tool_wiki_archive_page({
        "path": "wiki/a.md", "confirm": True,
    }))


def test_archive_never_changes_human_page(repo: Path):
    page = repo / "wiki" / "hand.md"
    original = '---\ntitle: "H"\ntype: concept\norigin: human\n---\nbody\n'
    page.write_text(original, encoding="utf-8")
    _error(server.tool_wiki_archive_page({
        "path": "wiki/hand.md", "reason": "old", "confirm": True,
    }))
    assert page.read_text(encoding="utf-8") == original


# ─── Protocol ────────────────────────────────────────────────────────


def test_tools_list_marks_write_tools_read_only_false():
    tools = server.handle_tools_list({})["tools"]
    by_name = {tool["name"]: tool for tool in tools}
    for name in ("wiki_write_page", "wiki_update_frontmatter", "wiki_archive_page"):
        assert by_name[name]["annotations"]["readOnlyHint"] is False


def test_write_tool_schemas_declare_required_fields():
    tools = {tool["name"]: tool for tool in server.TOOLS}
    assert tools["wiki_write_page"]["inputSchema"]["required"] == ["path", "content"]
    assert tools["wiki_update_frontmatter"]["inputSchema"]["required"] == ["path"]
    assert tools["wiki_archive_page"]["inputSchema"]["required"] == ["path", "reason"]


def test_write_page_refuses_large_frontmatter_human_page(repo: Path):
    page = repo / "wiki" / "concepts" / "Human.md"
    page.parent.mkdir(parents=True)
    tags = "\n".join(f"  - tag{i}" for i in range(800))
    text = (
        f'---\ntitle: "H"\ntype: concept\ntags:\n{tags}\n'
        "origin: human\n---\n\nkeep me\n"
    )
    assert len(text.encode("utf-8")) > 8 * 1024
    page.write_text(text, encoding="utf-8")

    result = server.tool_wiki_write_page({
        "path": "wiki/concepts/Human.md",
        "content": GOOD_PAGE,
        "mode": "replace",
        "confirm": True,
    })

    assert "origin: human" in _error(result)
    assert page.read_text(encoding="utf-8") == text


def test_frontmatter_value_reads_both_quote_styles():
    content = '---\ntitle: \'He said "hi"\'\ntype: \'a"b\'\n---\n\nbody\n'
    assert server._frontmatter_value(content, "title") == 'He said "hi"'
    assert server._frontmatter_value(content, "type") == 'a"b'


def test_numeric_tag_round_trips_as_a_string():
    text = set_frontmatter_fields(
        '---\ntitle: "A"\n---\nbody\n', {"tags": ["2024", "v1.5"]}
    )
    assert parse_frontmatter(text)[0]["tags"] == ["2024", "v1.5"]


def test_previews_append_no_edit_line_and_writes_append_one(repo: Path):
    log = repo / "wiki" / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    page = repo / "wiki" / "concepts" / "A.md"
    page.parent.mkdir(parents=True)
    page.write_text(UPDATE_PAGE, encoding="utf-8")

    server.tool_wiki_update_frontmatter({
        "path": "wiki/concepts/A.md",
        "fields": {"title": "B"},
    })
    assert log.read_text(encoding="utf-8") == "# Log\n"

    server.tool_wiki_update_frontmatter({
        "path": "wiki/concepts/A.md",
        "fields": {"title": "B"},
        "confirm": True,
    })
    server.tool_wiki_archive_page({
        "path": "wiki/concepts/A.md",
        "reason": "old",
        "confirm": True,
    })
    text = log.read_text(encoding="utf-8")
    assert text.count("] edit | wiki/concepts/A.md") == 2
