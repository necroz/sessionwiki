"""wiki_query shows the status of every record it returns.

A raw transcript says what happened in a session, including dead ends;
a wiki page says what was accepted into the book. The reader must see
which record it is looking at and how much trust it carries: type,
lifecycle, confidence, update date, and the number of backing sources.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_query


def _page(root: Path, rel: str, frontmatter: str, body: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
    return rel


def _query(root: Path, question: str, **args: object) -> str:
    with patch.object(server, "REPO_ROOT", root):
        return tool_wiki_query({"question": question, **args})["content"][0]["text"]


def _status_lines(text: str) -> list[str]:
    return re.findall(r"^status: .*$", text, re.MULTILINE)


def test_hit_shows_type_lifecycle_confidence_date_and_sources(tmp_path: Path):
    _page(
        tmp_path, "wiki/entities/Keycloak.md",
        'title: "Keycloak"\ntype: entity\nlifecycle: reviewed\n'
        "confidence: 0.85\nlast_updated: 2026-10-01\n"
        "sources: [login, logout]",
        "Keycloak is the identity provider.",
    )

    text = _query(tmp_path, "Keycloak")

    assert _status_lines(text) == [
        "status: type=entity · lifecycle=reviewed · confidence=0.85 · "
        "updated=2026-10-01 · sources=2"
    ]


def test_missing_status_fields_are_marked_unset(tmp_path: Path):
    _page(
        tmp_path, "wiki/concepts/OIDC.md",
        'title: "OIDC"\ntype: concept',
        "OIDC is the login protocol.",
    )

    text = _query(tmp_path, "OIDC")

    assert _status_lines(text) == [
        "status: type=concept · lifecycle=unset · confidence=unset · updated=unset"
    ]


def test_source_page_date_falls_back_to_the_date_field(tmp_path: Path):
    _page(
        tmp_path, "wiki/sources/app/2026-01-01-login.md",
        'title: "Session: login"\ntype: source\nslug: login\ndate: 2026-01-01',
        "Added the OIDC login flow.",
    )

    text = _query(tmp_path, "OIDC")

    assert _status_lines(text) == [
        "status: type=source · lifecycle=unset · confidence=unset · updated=2026-01-01"
    ]


def test_raw_transcript_hit_is_marked_as_not_curated(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    _page(
        tmp_path, "raw/sessions/2026-01-01-app-login.md",
        "slug: login\ndate: 2026-01-01\nproject: app",
        "Added the OIDC login flow.",
    )

    text = _query(tmp_path, "OIDC", include_raw=True)

    assert _status_lines(text) == [
        "status: raw transcript · 2026-01-01 · not in the wiki yet"
    ]


def test_lesson_page_is_returned_with_its_status(tmp_path: Path):
    _page(
        tmp_path, "wiki/lessons/chunk-by-budget.md",
        'title: "Chunk by budget"\ntype: lesson\nlifecycle: reviewed\n'
        "date: 2026-11-05\nsources: [cache-session]",
        "## Rule\n\nChunk large sessions by token budget before synthesis.",
    )

    text = _query(tmp_path, "chunk sessions")

    assert "wiki/lessons/chunk-by-budget.md" in text
    assert _status_lines(text) == [
        "status: type=lesson · lifecycle=reviewed · confidence=unset · "
        "updated=2026-11-05 · sources=1"
    ]


def test_empty_sources_list_counts_zero(tmp_path: Path):
    _page(
        tmp_path, "wiki/entities/Vault.md",
        'title: "Vault"\ntype: entity\nsources: []',
        "Vault stores the secrets.",
    )

    text = _query(tmp_path, "Vault")

    assert _status_lines(text) == [
        "status: type=entity · lifecycle=unset · confidence=unset · "
        "updated=unset · sources=0"
    ]