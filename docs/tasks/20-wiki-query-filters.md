# 20 — Filters in `wiki_query` and `sessionwiki query`

- Priority: P0
- Roadmap: Phase 1, A3
- Depends on: 17 (`rank_query`), 11 (length tests)
- Size: M (2–3 h)
- Files: `sessionwiki/mcp/server.py`, `sessionwiki/cli.py`,
  `tests/test_mcp_query_filters.py` (new), `docs/reference/cli.md`
- Branch: `feat/wiki-query-filters`
- PR title: `feat(mcp): filter wiki_query by project, type, tag and date`

## Read first

- `sessionwiki/mcp/server.py`: `TOOLS[0]` (`wiki_query`), `rank_query`
  (from card 17), `_frontmatter_value`, the wiki loop and the raw loop
  inside `rank_query`
- `sessionwiki/cli.py`: the `query` parser and `cmd_query` (card 17)
- One source page and one raw transcript, to see the keys: `project`,
  `type`, `tags`, `date`

## Problem

"What happened in project X last week" scans every project. Agents cannot
narrow a search. Pages have no `agent` key (the agent is the first entry in
`tags`, for example `[zcode, session-transcript]`) and `model` is often
empty, so filter by `tag` instead of `agent`/`model`.

## Required change

### 1. Filter helper in `server.py`

```python
_FILTER_KEYS = ("project", "type", "tag", "date_from", "date_to")


def _tags(content: str) -> set[str]:
    raw = _frontmatter_value(content, "tags").strip().strip("[]")
    return {t.strip().strip("'\"").lower() for t in raw.split(",") if t.strip()}


def _passes_filters(content: str, filters: dict[str, str]) -> bool:
    """True when the page's frontmatter matches every given filter."""
    if not filters:
        return True
    if "project" in filters and _frontmatter_value(content, "project") != filters["project"]:
        return False
    if "type" in filters and _frontmatter_value(content, "type") != filters["type"]:
        return False
    if "tag" in filters and filters["tag"].lower() not in _tags(content):
        return False
    day = _frontmatter_value(content, "date")[:10]
    if "date_from" in filters and (not day or day < filters["date_from"]):
        return False
    if "date_to" in filters and (not day or day > filters["date_to"]):
        return False
    return True
```

Check how `_frontmatter_value` strips quotes; if it does not, strip them
here.

### 2. Apply in `rank_query`

- New parameter: `filters: Optional[dict[str, str]] = None`. Drop empty
  values: `filters = {k: v for k, v in (filters or {}).items() if v and k in _FILTER_KEYS}`.
- Wiki loop: after the service-page skip, `if not _passes_filters(content, filters): continue`
  — before `_collect` and before `links[page] = ...`. Pages that fail are
  then also excluded from the graph hop.
- Raw loop: the same check on `content`, before `_collect`.
- Validate dates: if `date_from`/`date_to` is not `YYYY-MM-DD`, ignore it
  (do not raise).

### 3. MCP schema

Add five properties to `wiki_query.inputSchema.properties`:

```python
"project": {"type": "string", "description": "Only pages of this project (frontmatter project)."},
"type": {"type": "string", "description": "Only this page type: source, entity, concept, synthesis, ..."},
"tag": {"type": "string", "description": "Only pages with this tag, e.g. the agent: claude-code, codex-cli, zcode, opencode."},
"date_from": {"type": "string", "description": "Only pages dated on or after YYYY-MM-DD."},
"date_to": {"type": "string", "description": "Only pages dated on or before YYYY-MM-DD."},
```

Do not grow the main description by more than one short sentence
("Optional filters: project, type, tag, date_from, date_to."). Card 11's
test must still pass. `tool_wiki_query` passes the filters through.

### 4. CLI

Add `--project`, `--type`, `--tag`, `--date-from`, `--date-to` to
`sessionwiki query` and pass them as `filters`. Update
`docs/reference/cli.md`.

## Tests

New `tests/test_mcp_query_filters.py` with a seeded wiki of two projects,
two dates and two tags:

- `project="app"` returns only `app` pages.
- `tag="zcode"` returns only pages tagged `zcode`.
- `date_from`/`date_to` keep the range inclusive.
- A bad date (`"last week"`) is ignored, not an error.
- A page of another project that shares a `[[link]]` with a top hit does
  **not** enter through the graph hop.
- No filters: same result as before (compare with a call without filters).

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_query_filters.py tests/test_mcp_description_limits.py tests/test_cli_query.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m sessionwiki query release --project llm-wiki --limit 3
```

## Acceptance criteria

- [ ] Five filters work in MCP and CLI.
- [ ] Filtered-out pages never appear, also not via the graph hop.
- [ ] Unfiltered results unchanged.
- [ ] Docs and `CHANGELOG.md` updated.

## Out of scope

- Filters for `wiki_search` (separate card if needed).
- Branch filters (C8).

## Rollback

Revert the files.
