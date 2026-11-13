"""wiki_query follows one hop of the session graph (habr 1044200).

Session pages name the tools and topics they touch under ``## Connections``
("- Keycloak — the identity provider"). Two pages that name the same rare
thing are neighbours. A question that finds one of them also brings up the
other, even when the neighbour does not use the question's words: the
article reports the biggest recall gain on such "how is X related to Y"
questions.

A name passes score on only when two or more top hits carry it
(pseudo-relevance feedback). A top hit that matched by accident then does
not drag its own neighbours in. Names that most pages share connect
nothing.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_query


def _source(root: Path, name: str, summary: str, connections: list[str]) -> str:
    rel = f"wiki/sources/app/2026-01-01-{name}.md"
    lines = "\n".join(f"- {c} — related" for c in connections)
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "Session: {name}"\ntype: source\nslug: {name}\ndate: 2026-01-01\n---\n\n'
        f"## Summary\n\n{summary}\n\n## Connections\n\n{lines}\n",
        encoding="utf-8",
    )
    return rel


def _seed(root: Path) -> dict[str, str]:
    pages = {
        # Top hits for "OIDC": two of them name Keycloak, one names Rare.
        "login": _source(root, "login", "Added the OIDC login flow to the web app.",
                         ["Keycloak", "Common"]),
        "logout": _source(root, "logout", "Added OIDC logout to the API.",
                          ["Keycloak", "Common"]),
        "scopes": _source(root, "scopes", "Listed the OIDC scopes we request.",
                          ["Rare", "Common"]),
        # Neighbours without the word "OIDC".
        "refresh": _source(root, "refresh", "Fixed expired tokens being reused by the worker.",
                           ["Keycloak", "Common"]),
        "rare": _source(root, "rare", "Renamed a column in the billing report.",
                        ["Rare", "Common"]),
        "unrelated": _source(root, "unrelated", "Tuned the print layout of a spreadsheet.",
                             ["Common"]),
    }
    # Filler sessions: every page names "Common", so it links nothing.
    for i in range(60):
        _source(root, f"filler{i}", f"Routine maintenance number {i}.", ["Common"])
    return pages


def _query(root: Path, question: str) -> str:
    with patch.object(server, "REPO_ROOT", root):
        return tool_wiki_query({"question": question, "max_pages": 5})["content"][0]["text"]


def _ranked(text: str) -> list[str]:
    return re.findall(r"^## `([^`]+)`", text, re.MULTILINE)


def test_page_links_parses_crlf_connections():
    # Windows-authored pages have CRLF line endings; the Connections
    # section must still parse so the graph hop finds neighbours.
    content = (
        "## Summary\r\n\r\ntext\r\n\r\n"
        "## Connections\r\n\r\n- Keycloak — why\r\n- Common — related\r\n"
    )
    links = server._page_links(content)
    assert links.get("keycloak") == "Keycloak"


def test_neighbour_without_the_query_words_is_returned(tmp_path: Path):
    pages = _seed(tmp_path)

    ranked = _ranked(_query(tmp_path, "OIDC"))

    assert pages["refresh"] in ranked
    assert ranked.index(pages["refresh"]) > ranked.index(pages["login"])


def test_name_only_one_top_hit_carries_links_nothing(tmp_path: Path):
    pages = _seed(tmp_path)

    ranked = _ranked(_query(tmp_path, "OIDC"))

    assert pages["rare"] not in ranked


def test_name_shared_by_most_pages_links_nothing(tmp_path: Path):
    pages = _seed(tmp_path)

    ranked = _ranked(_query(tmp_path, "OIDC"))

    assert pages["unrelated"] not in ranked
    assert sorted(ranked) == sorted([pages["login"], pages["logout"], pages["scopes"], pages["refresh"]])


def test_neighbour_says_which_name_links_it(tmp_path: Path):
    pages = _seed(tmp_path)

    text = _query(tmp_path, "OIDC")

    assert re.search(rf"^## `{re.escape(pages['refresh'])}` \(score: [\d.]+, via Keycloak\)$",
                     text, re.MULTILINE)
    assert re.search(rf"^## `{re.escape(pages['scopes'])}` \(score: [\d.]+\)$", text, re.MULTILINE)


def test_tiny_wiki_where_every_page_shares_a_name_does_not_crash(tmp_path):
    """Two pages that both link [[Keycloak]] give it idf log(2/2) = 0;
    the hop used to divide by that sum."""
    for n, day in (("a", "01"), ("b", "02")):
        page = tmp_path / "wiki" / "sources" / "x" / f"2026-01-{day}-{n}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f'---\ntitle: "{n}"\ntype: source\nslug: {n}\n---\n\n'
            "## Summary\n\nkeycloak setup\n\n## Connections\n\n- [[Keycloak]] — auth\n",
            encoding="utf-8",
        )
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = server.tool_wiki_query({"question": "keycloak setup"})
    assert result["isError"] is False


def test_shorter_result_list_is_a_prefix_of_a_longer_one(tmp_path: Path):
    """The graph hop must not depend on how many results the caller wants.

    Four weaker hits name Vault. When the seed set shrank with max_pages,
    only two of them were seeds at max_pages=5, the pages that name Vault
    got a different bonus, and the top 5 differed from the first 5 of the
    top 10.
    """
    for i in range(3):
        _source(tmp_path, f"oidc{i}", "Reviewed the OIDC setup.", ["Common"])
    for i in range(4):
        _source(tmp_path, f"carrier{i}", "Rotated the OIDC client secret.", ["Vault", "Common"])
    neighbour = _source(tmp_path, "neighbour", "Moved the signing keys.", ["Vault", "Common"])
    for i in range(120):
        _source(tmp_path, f"filler{i}", f"Routine maintenance number {i}.", ["Common"])

    with patch.object(server, "REPO_ROOT", tmp_path):
        short = _ranked(tool_wiki_query({"question": "OIDC", "max_pages": 5})["content"][0]["text"])
        long = _ranked(tool_wiki_query({"question": "OIDC", "max_pages": 10})["content"][0]["text"])

    assert short == long[:5]
    assert neighbour in long
