# 11 — Guard MCP description and instructions length

- Priority: P0
- Roadmap: Phase 0, E3
- Depends on: none
- Size: S (20–30 min)
- Files: `tests/test_mcp_description_limits.py` (new)
- Branch: `test/mcp-description-limits`
- PR title: `test: cap MCP tool description and instructions length`

## Read first

- `sessionwiki/mcp/server.py`: `TOOLS` (starts around line 57) and
  `handle_initialize` (around line 1339)
- `tests/test_mcp_protocol.py`, `test_initialize_returns_protocol_version`

## Problem

MCP clients truncate long text. Claude Code cuts server `instructions` and
long tool descriptions at about 2048 characters (habr 1102588). Nothing in
the test suite stops a description from growing past that.

Today the longest tool description is `wiki_query` (733 characters). The
total of all descriptions is 5238 characters. Do **not** cap the total: that
test would fail today and would force removing tools. Card 30 adds three
write tools later; the per-tool and per-property caps apply to them too, so
the tests must iterate over `server.TOOLS`, not over a fixed name list.

## Required change

Create `tests/test_mcp_description_limits.py`:

```python
"""MCP clients truncate long text; keep every description under the cap."""

from __future__ import annotations

from sessionwiki.mcp import server

MAX_TOOL_DESCRIPTION = 1024
MAX_PROPERTY_DESCRIPTION = 400
MAX_INSTRUCTIONS = 2048


def test_every_tool_description_fits():
    too_long = {
        t["name"]: len(t["description"])
        for t in server.TOOLS
        if len(t["description"]) > MAX_TOOL_DESCRIPTION
    }
    assert not too_long, too_long


def test_every_property_description_fits():
    too_long = {}
    for tool in server.TOOLS:
        props = tool.get("inputSchema", {}).get("properties", {})
        for name, spec in props.items():
            text = spec.get("description", "")
            if len(text) > MAX_PROPERTY_DESCRIPTION:
                too_long[f"{tool['name']}.{name}"] = len(text)
    assert not too_long, too_long


def test_tool_names_are_unique():
    names = [t["name"] for t in server.TOOLS]
    assert len(names) == len(set(names))


def test_instructions_fit_when_present():
    result = server.handle_initialize({})
    text = result.get("instructions", "")
    assert len(text) <= MAX_INSTRUCTIONS, len(text)
```

Do not change `server.py` in this card.

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_description_limits.py -q
.venv/bin/python -m pytest tests/ -q
```

Both exit with code 0.

## Acceptance criteria

- [ ] The new test file exists and passes.
- [ ] No production code changed.
- [ ] `CHANGELOG.md` has one line under `## [Unreleased]`.

## Out of scope

- Shortening any existing description.
- Adding `instructions` (card 12).

## Rollback

Delete the test file.
