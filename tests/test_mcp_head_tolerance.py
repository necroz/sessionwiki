"""Head-read tolerance: frontmatter longer than the 8 KiB head window.

The canonical parser needs a closing fence; an 8 KiB head read of a page
with a very long frontmatter has none. The status line and list_sources
must still report the fields the old per-key reader extracted (review
minor #1), via the tolerant _frontmatter_value delegate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from sessionwiki.mcp import server
from sessionwiki.mcp.server import tool_wiki_list_sources, tool_wiki_query

_FILLER = "x" * 9000  # pushes the closing fence past the 8 KiB head window


def test_status_line_tolerates_unterminated_head(tmp_path: Path):
    p = tmp_path / "wiki" / "entities" / "Long.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'---\ntitle: "Long"\ntype: entity\n{_FILLER}\n---\n\nUnique status token.\n',
        encoding="utf-8",
    )
    with patch.object(server, "REPO_ROOT", tmp_path):
        text = tool_wiki_query({"question": "unique status token"})["content"][0]["text"]
    status = re.findall(r"^status: .*$", text, re.MULTILINE)
    assert status and "type=entity" in status[0]


def test_list_sources_tolerates_unterminated_head(tmp_path: Path):
    p = tmp_path / "raw" / "sessions" / "long.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nproject: longproj\ndate: 2026-11-01\n{_FILLER}\n---\n\nBody.\n",
        encoding="utf-8",
    )
    with patch.object(server, "REPO_ROOT", tmp_path):
        result = tool_wiki_list_sources({})
    entries = json.loads(result["content"][0]["text"])
    assert len(entries) == 1
    assert entries[0]["project"] == "longproj"
    assert entries[0]["date"] == "2026-11-01"
