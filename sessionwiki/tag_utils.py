"""Shared tag parsing utilities (v1.0.1 · post-audit cleanup).

Consolidates the tag parser that was duplicated byte-for-byte in
``sessionwiki/categories.py`` and ``sessionwiki/search_facets.py``. Both
modules now import from here so there's a single source of truth
for what counts as "noise" and how YAML-list tags get parsed.

Also used by the lint rules (via ``scan_tags()``) and MCP server
tools.
"""

from __future__ import annotations

from typing import Any

# ─── Noise tag filter ──────────────────────────────────────────────────

# Tags that appear on nearly every session and add no navigation value.
# Keep this list short — removing a tag here restores it to categories.
NOISE_TAGS: set[str] = {
    "claude-code",
    "session-transcript",
    "demo",
    "",
}


def parse_tags_field(raw: Any, *, keep_noise: bool = False) -> list[str]:
    """Parse a YAML ``tags:`` field into a cleaned list of lowercase tags.

    Handles four input shapes:
      - ``None`` / empty string → ``[]``
      - a real ``list``/``tuple`` (e.g. from the canonical frontmatter
        parser's block lists) → items stringified and cleaned
      - ``"[a, b]"`` (YAML list as string) → ``["a", "b"]``
      - ``"a, b"`` (plain comma list) → ``["a", "b"]``

    Strips surrounding brackets, quotes, and whitespace. Filters out
    NOISE_TAGS unless ``keep_noise=True`` (query tag matching must keep
    agent tags like ``claude-code``). Always lowercases.
    """
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        parts = [str(item).strip().strip('"').strip("'").strip() for item in raw]
    else:
        raw = str(raw).strip()
        # Strip YAML-list brackets if present
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        # Split and clean each tag
        parts = [p.strip().strip('"').strip("'") for p in raw.split(",")]
    cleaned = [p.lower() for p in parts if p]
    if keep_noise:
        return cleaned
    return [p for p in cleaned if p not in NOISE_TAGS]


def scan_tags(pages: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Scan page metadata and return ``{tag: [page_rel, ...]}``.

    Input is the output of ``sessionwiki.lint.load_pages()``. Each page has
    a ``meta`` dict; we read its ``tags`` key and aggregate.
    """
    out: dict[str, list[str]] = {}
    for rel, page in pages.items():
        raw_tags = page["meta"].get("tags", "")
        for tag in parse_tags_field(raw_tags):
            out.setdefault(tag, []).append(rel)
    # Deterministic order for callers
    return {tag: sorted(pages_) for tag, pages_ in out.items()}
