"""Canonical frontmatter parser (#273).

Historically 8 copies of this function lived scattered across the
codebase with slightly different return shapes — dict vs
``(dict, body)`` tuple vs ``(str | None, body)``.  Consolidating in
one hit is risky (every caller makes specific assumptions about the
return shape), so this module ships the canonical implementation plus
thin wrappers that match the three existing signatures.  New call
sites should use :func:`parse_frontmatter` or
:func:`parse_frontmatter_dict`; legacy sites can migrate over time.

Stdlib-only.  No YAML dependency — we parse the minimal subset of
YAML we use in practice (scalars, inline lists, inline dicts, block
lists with `- ` bullets).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

# Accept LF, CRLF, or CR after each fence so Windows-authored (CRLF) and
# old-Mac (CR) files parse identically to LF input. The optional newline
# slots match the historical regex (`\n?(.*?)\n?---\n?`) so empty
# frontmatter (`---\n---\nbody`) still parses. BOM is handled separately
# in `_strip_bom()` before the regex runs. See #409, #423.
_FRONTMATTER_RE = re.compile(
    r"^---[ \t]*(?:\r\n|\r|\n)?(.*?)(?:\r\n|\r|\n)?---[ \t]*(?:\r\n|\r|\n)?(.*)$",
    re.DOTALL,
)


def _strip_bom(text: str) -> str:
    """Strip leading UTF-8 BOM if present (#423)."""
    if text and text[0] == "\ufeff":
        return text[1:]
    return text


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(meta, body)`` — the canonical shape.

    Empty or malformed input returns ``({}, text)`` so callers can
    treat every file uniformly. Handles UTF-8 BOM and CR/LF/CRLF
    line endings transparently.
    """
    text = _strip_bom(text)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_text = m.group(1)
    body = m.group(2)
    meta: dict[str, Any] = {}
    for line in meta_text.splitlines():
        mm = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if not mm:
            continue
        key, raw = mm.group(1), mm.group(2).strip()
        meta[key] = _parse_scalar(raw)
    return meta, body


def parse_frontmatter_dict(text: str) -> dict[str, Any]:
    """Return just the metadata dict — convenience for callers that
    don't need the body."""
    return parse_frontmatter(text)[0]


def parse_frontmatter_or_none(text: str) -> tuple[Optional[str], str]:
    """Return ``(raw_frontmatter_text | None, body)`` — legacy shape
    used by ``sessionwiki/tags.py`` which does its own line-level parsing
    inside the frontmatter block."""
    text = _strip_bom(text)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), m.group(2)


_EOL_RE = re.compile(r"\r\n|\r|\n")
_KEY_LINE_RE = re.compile(r"^([a-zA-Z_][\w-]*):")
_BLOCK_LIST_LINE_RE = re.compile(r"^\s*- ")
_LIST_ITEM_RE = re.compile(r"[\w][\w.\-/+ ]{0,63}")


def _first_eol(text: str, default: str = "\n") -> str:
    """Return the first line ending in ``text``, or ``default``."""
    m = _EOL_RE.search(text)
    return m.group(0) if m else default


def format_frontmatter_value(value: Any) -> str:
    """Serialize one value the way ``_parse_scalar`` reads it back.

    Lists become ``[a, b]``. Strings are double-quoted (single-quoted if
    they contain ``"``). Numbers and bools are written as-is. Raises
    ``ValueError`` for newlines, or for a string that holds both quote
    characters.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        if "\n" in value or "\r" in value:
            raise ValueError("frontmatter values must not contain newlines")
        if "\x00" in value:
            raise ValueError("frontmatter values must not contain NUL bytes")
        if '"' in value:
            if "'" in value:
                raise ValueError(
                    "frontmatter value contains both quote characters: "
                    f"{value!r}"
                )
            return f"'{value}'"
        return f'"{value}"'
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"list items must be strings: {item!r}")
            if not _LIST_ITEM_RE.fullmatch(item):
                raise ValueError(
                    f"invalid list item {item!r}: use letters, digits, '_', "
                    "'.', '-', '/', '+' and spaces; no commas or brackets"
                )
            # A bare "2024" or "1.5" parses back as a number, so quote any
            # item whose scalar form would change type.
            if _parse_scalar(item, coerce_bool=False) != item:
                item = f'"{item}"'
            items.append(item)
        return "[" + ", ".join(items) + "]"
    raise ValueError(f"unsupported frontmatter value: {value!r}")


def set_frontmatter_fields(text: str, fields: dict[str, Any]) -> str:
    """Return ``text`` with each key in ``fields`` set in its frontmatter.

    - An existing ``key: ...`` line is replaced in place. Block-list lines
      that follow it (lines that match ``^\\s*- ``) are removed.
    - A missing key is appended before the closing ``---``.
    - Text without frontmatter gets a new block at the top.
    - The body after the closing ``---`` is returned byte for byte.
    - Line endings: use the line ending of the first frontmatter line.
    """
    text = _strip_bom(text)
    formatted = {key: format_frontmatter_value(value) for key, value in fields.items()}

    m = _FRONTMATTER_RE.match(text)
    if not m:
        eol = _first_eol(text)
        lines = [f"{key}: {value}" for key, value in formatted.items()]
        block = "---" + eol + eol.join(lines) + eol + "---" + eol
        return block + text

    meta_text = m.group(1)
    body = m.group(2)
    head = text[: m.start(1)]
    tail = text[m.end(1): m.start(2)]
    eol = _first_eol(head)
    # ``tail`` is the newline before the closing fence, the fence itself and
    # whatever followed it on that line. Keep the part after the fence so the
    # body stays byte for byte.
    after_close = tail[tail.rfind("---") + 3:]
    open_prefix = head if head.endswith(("\n", "\r")) else head + eol

    lines = re.split(r"\r\n|\r|\n", meta_text)
    out: list[str] = []
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        km = _KEY_LINE_RE.match(line)
        if km and km.group(1) in formatted:
            key = km.group(1)
            out.append(f"{key}: {formatted[key]}")
            seen.add(key)
            i += 1
            while i < len(lines) and _BLOCK_LIST_LINE_RE.match(lines[i]):
                i += 1
            continue
        out.append(line)
        i += 1
    for key, value in formatted.items():
        if key not in seen:
            out.append(f"{key}: {value}")

    meta_new = eol.join(out) + (eol if out else "")
    return open_prefix + meta_new + "---" + after_close + body


def is_human_page(path: Path) -> bool:
    """True when an existing page says ``origin: human`` in its frontmatter.

    Reads the whole file. A fixed-size head misses a page whose frontmatter
    is longer, and a missed human page may be overwritten. Accepts a
    trailing YAML comment after the value.
    """
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    meta, _ = parse_frontmatter(text)
    if str(meta.get("origin", "")).strip().lower() == "human":
        return True
    # ``parse_frontmatter`` keeps a trailing ``# comment`` in the value.
    raw, _ = parse_frontmatter_or_none(text)
    if raw is None:
        return False
    for line in raw.splitlines():
        m = re.match(r"^origin:\s*(.*?)\s*$", line, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).split("#", 1)[0].strip().strip("'\"")
        if value.lower() == "human":
            return True
    return False


def _parse_scalar(raw: str, *, coerce_bool: bool = True) -> Any:
    """Parse a single YAML scalar value (best-effort, no external deps).

    Handles: inline lists ``[a, b, c]``, quoted strings, bools, ints.
    Everything else comes back as the stripped string.

    #py-l1 (#599): pass ``coerce_bool=False`` when recursing into list
    items so a tag list like ``[no, yes, maybe]`` doesn't become
    ``[False, True, "maybe"]``. Top-level scalars still coerce.
    """
    s = raw.strip()
    if not s:
        return ""
    # Quoted string
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # Inline list: [a, b, c]
    if s.startswith("[") and s.endswith("]"):
        body = s[1:-1].strip()
        if not body:
            return []
        return [_parse_scalar(x, coerce_bool=False) for x in body.split(",")]
    # Bool
    low = s.lower()
    if coerce_bool and low in {"true", "yes"}:
        return True
    if coerce_bool and low in {"false", "no"}:
        return False
    # Int
    try:
        return int(s)
    except ValueError:
        pass
    # Float
    try:
        return float(s)
    except ValueError:
        pass
    return s
