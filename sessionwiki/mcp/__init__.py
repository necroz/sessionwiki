"""sessionwiki MCP server.

Exposes sessionwiki operations as Model Context Protocol (MCP) tools that any
MCP-capable client (Claude Desktop, Claude Code, Codex, Cline, Cursor, ChatGPT
desktop, etc.) can call directly.

Eleven tools in two profiles, chosen with ``SESSIONWIKI_MCP_TOOLS``.

``read`` (default) — read-only:

    - wiki_query(question)       — ranked search, falls back to raw/
    - wiki_search(term)          — exact text over wiki/ (+ optional raw/)
    - wiki_list_sources(project) — list raw session files with metadata
    - wiki_read_page(path)       — read one page (path-traversal guarded)
    - wiki_lint()                — the structural rules of `sessionwiki lint`
    - wiki_dashboard()           — page counts, lifecycle and confidence

``full`` adds:

    - wiki_sync(confirm)         — import new sessions
    - wiki_export(format)        — return any AI-consumable export
    - wiki_write_page, wiki_update_frontmatter, wiki_archive_page
                                 — guarded writers (preview, then confirm)

Protocol: Model Context Protocol, stdio transport, JSON-RPC 2.0.
See the MCP spec at: https://modelcontextprotocol.io/

Run with:

    python3 -m sessionwiki.mcp
"""

from __future__ import annotations

from sessionwiki.mcp.server import main

__all__ = ["main"]
