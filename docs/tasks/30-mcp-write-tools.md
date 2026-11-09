# 30 — Guarded MCP write tools

- Priority: P1
- Roadmap: Phase 1, E12 (also covers the MCP part of C4)
- Depends on: 11 (description limits), 12 (server `instructions`),
  22 (`origin: human` guard and `is_human_page`)
- Size: M (2–3 h)
- Files: `sessionwiki/mcp/server.py`, `sessionwiki/_frontmatter.py`,
  `tests/test_mcp_write_tools.py` (new), `tests/test_mcp_enhanced.py`,
  `tests/test_mcp_protocol.py`, `README.md`, `CLAUDE.md`, `AGENTS.md`,
  `CHANGELOG.md`
- Branch: `feat/mcp-write-tools`
- PR title: `feat(mcp): create, edit and archive wiki pages with a confirm step`

## Read first

- `sessionwiki/mcp/server.py`:
  - `TOOLS` (starts around line 57), `_TOOL_TITLES`, `_WRITE_TOOLS` and the
    annotation loop right after `TOOLS`
  - `_safe_path`, `_is_read_page_allowed`, `tool_wiki_read_page`
  - `tool_wiki_sync`: the `dry_run` / `confirm` pattern
  - `_ok`, `_err`, `TOOL_IMPLS`
  - `SERVER_INSTRUCTIONS` (added by card 12)
- `sessionwiki/_frontmatter.py`: `parse_frontmatter`, `_parse_scalar`,
  `is_human_page` (added by card 22)
- `sessionwiki/_system_pages.py`: `is_system_file`
- `sessionwiki/lock.py`: `atomic_write_text`
- `sessionwiki/lifecycle.py`: `LifecycleState`
- `tests/test_mcp_enhanced.py`: `test_all_12_tools_registered`,
  `test_every_tool_has_title_and_behaviour_annotations`,
  `test_only_wiki_sync_writes`, `test_every_description_points_to_a_sibling_tool`
- `tests/test_mcp_protocol.py`: the `len(tools) == 12` assertion
- `tests/test_mcp_description_limits.py` (card 11)

## Problem

Every MCP tool except `wiki_sync` is read-only. An agent that finds a wrong
fact, a missing page or a bad tag cannot fix it through MCP. Directory
reviews (Glama) score the server low on completeness for this reason:
"there is no tool to create, edit, or delete a wiki page, and no way to add
tags or frontmatter".

Card 27 left the MCP part of C4 (`wiki_remember`) out of scope until a
write-permission decision was made. The decision is:

- Writes go only to `wiki/`, never to `raw/` (raw is immutable) and never
  to system pages.
- Pages with `origin: human` are never changed (roadmap principle 3,
  card 22).
- Every write tool previews by default and writes only with `confirm=true`,
  the same contract as `wiki_sync`. The agent asks the user first.
- Nothing is deleted. "Delete" means `lifecycle: archived`; the file stays,
  links keep working, card 21 ranks it lower, and the page can be restored.
- Pages written by an agent carry `origin: agent`.
- A remembered fact is a page under `wiki/candidates/` written with
  `wiki_write_page`. There is no separate `wiki_remember` tool.

## Required change

### 1. Frontmatter writer in `sessionwiki/_frontmatter.py`

Add below `parse_frontmatter_or_none`:

```python
def format_frontmatter_value(value: Any) -> str:
    """Serialize one value the way ``_parse_scalar`` reads it back.

    Lists become ``[a, b]``. Strings are double-quoted (single-quoted if
    they contain ``"``). Numbers and bools are written as-is. Raises
    ``ValueError`` for newlines, or for a string that holds both quote
    characters.
    """


def set_frontmatter_fields(text: str, fields: dict[str, Any]) -> str:
    """Return ``text`` with each key in ``fields`` set in its frontmatter.

    - An existing ``key: ...`` line is replaced in place. Block-list lines
      that follow it (lines that match ``^\\s*- ``) are removed.
    - A missing key is appended before the closing ``---``.
    - Text without frontmatter gets a new block at the top.
    - The body after the closing ``---`` is returned byte for byte.
    - Line endings: use the line ending of the first frontmatter line.
    """
```

Rules for `format_frontmatter_value`:

- `bool` → `true` / `false`; `int`, `float` → `repr`-style number.
- `str` → `"value"`; if it contains `"` → `'value'`; if it contains both
  `"` and `'` → `ValueError`. Any `\n` or `\r` → `ValueError`.
- `list` → `[item1, item2]`, each item written bare. Items must match
  `^[\w][\w.\-/+ ]{0,63}$` (Unicode `\w`); otherwise `ValueError`.
  `_parse_scalar` splits lists on `,`, so items must not contain `,`,
  `[`, `]` or quotes.

Round-trip check: `parse_frontmatter(set_frontmatter_fields(t, f))[0][k]`
equals `f[k]` for every key (the tests assert this).

### 2. Path guard in `sessionwiki/mcp/server.py`

```python
def _resolve_wiki_write_path(rel: str) -> tuple[Path | None, str | None]:
    """Return (absolute path, None) when ``rel`` may be written by an MCP
    write tool, else (None, error message)."""
```

Refuse, with a clear message, when:

- `rel` is empty, or `_safe_path(rel)` is `None`;
- `(REPO_ROOT / rel)` is a symlink;
- the resolved path is not under `REPO_ROOT / "wiki"`;
- the suffix is not `.md`;
- any path part starts with `.`;
- the first part under `wiki/` is `archive` (archive with
  `wiki_archive_page` instead);
- `is_system_file(path.name)` is true (index, log, overview, hot, …);
- the file exists and `is_human_page(path)` is true. Message:
  `"<rel> has origin: human; sessionwiki tools never change it"`.

### 3. Three tools

Append them **at the end** of `TOOLS`, `_TOOL_TITLES` and `TOOL_IMPLS`
(cards 17, 20 and 21 edit `TOOLS[0]` and `rank_query`; appending keeps the
merge clean). Use these descriptions exactly, with the lines joined by
single spaces (767, 678 and 534 characters); card 11's test caps each at
1024 characters.

`wiki_write_page`, title `"Write a page"`:

```text
Create or replace one Markdown page under wiki/. content is the whole page and
must start with frontmatter that has title and type. The tool sets origin: agent
and last_updated (today) in it. mode='create' (default) fails if the page
exists; mode='replace' overwrites it. Refused for paths outside wiki/, non-.md
files, wiki/archive/, system pages (index, log, overview, ...) and pages with
origin: human. Without confirm=true it writes nothing and returns a preview.
Ask the user before confirm=true. A real write is atomic and adds a line to
wiki/log.md. Returns JSON {path, action, written, old_bytes, new_bytes}. Put new
facts for review under wiki/candidates/. Use wiki_update_frontmatter to change
only tags or fields, and wiki_archive_page instead of deleting.
```

Schema: `path` (string, required), `content` (string, required), `mode`
(enum `create` | `replace`, default `create`), `confirm` (boolean, default
false).

`wiki_update_frontmatter`, title `"Edit page fields"`:

```text
Change frontmatter fields of one existing page under wiki/; the body is kept
byte for byte. fields may set title, type, tags (a list that replaces the old
one), lifecycle (draft, reviewed, verified, stale, archived) and confidence
(0.0-1.0); other keys are refused. add_tags and remove_tags change the tag list
without replacing it. last_updated is set to today. Refused for system pages
and pages with origin: human. Without confirm=true it writes nothing and returns
the old and new value of each field. Ask the user before confirm=true. Returns
JSON {path, changes: {field: [old, new]}, written}. Use wiki_write_page to
change the body and wiki_archive_page to retire a page.
```

Schema: `path` (string, required), `fields` (object), `add_tags` (array of
string), `remove_tags` (array of string), `confirm` (boolean, default
false). At least one of `fields`, `add_tags`, `remove_tags` must be given.

`wiki_archive_page`, title `"Archive a page"`:

```text
Retire one page under wiki/ without deleting it: set lifecycle: archived,
archived_reason and last_updated in its frontmatter. The file stays where it
is, so links keep working, and wiki_update_frontmatter with lifecycle: reviewed
restores it. Nothing is ever deleted. Refused for system pages and pages with
origin: human. Without confirm=true it writes nothing and returns a preview.
Ask the user before confirm=true. Returns JSON {path, previous_lifecycle,
written}. Use wiki_lifecycle with state 'archived' to list archived pages.
```

Schema: `path` (string, required), `reason` (string, required, at most 200
characters, no newlines), `confirm` (boolean, default false).

Implementation rules for all three:

- Every call goes through `_resolve_wiki_write_path` first.
- `confirm` is read as `args.get("confirm") is True`. Anything else is a
  preview. A preview never creates files or folders.
- Writes use `atomic_write_text`.
- `wiki_write_page`:
  - `content` must be a string of at most 1 MiB (UTF-8 bytes) with no
    `\x00`.
  - `parse_frontmatter(content)` must give a non-empty `title` and `type`;
    otherwise error.
  - The written text is
    `set_frontmatter_fields(content, {"origin": "agent", "last_updated": today})`.
    An `origin` the agent put in `content` is overwritten.
  - `mode="create"` and the file exists → error that names
    `mode='replace'`. `mode="replace"` and the file is missing → error that
    names `mode='create'`.
  - Parent folders are created only on a real write.
- `wiki_update_frontmatter`:
  - The page must exist.
  - Allowed keys in `fields`: `title`, `type`, `tags`, `lifecycle`,
    `confidence`. Any other key → error that lists the allowed ones.
  - `lifecycle` must be a `LifecycleState` value. Do not call
    `can_transition`: the user's `confirm=true` is the manual step.
  - `confidence` must be a number in 0.0–1.0.
  - `tags`, `add_tags`, `remove_tags`: lists of strings. Final tag list =
    (`fields["tags"]` if given, else the current tags) + `add_tags` (no
    duplicates, order kept) − `remove_tags`.
  - Always also set `last_updated`.
  - Any `ValueError` from `format_frontmatter_value` → `_err` with its
    message; nothing is written.
- `wiki_archive_page`:
  - The page must exist.
  - Sets `lifecycle: archived`, `archived_reason: <reason>`,
    `last_updated: <today>`. Already archived → `_ok` with
    `written: false` and a note.
- After a real write, if `wiki/log.md` exists, append:

  ```text

  ## [YYYY-MM-DD] edit | <rel> (<tool name>: <action>)
  ```

  where `<action>` is `create`, `replace`, `fields` or `archive`. Do not
  create `log.md` if it is missing.
- Results are JSON text through `_ok`. `path` is relative to `REPO_ROOT`
  with `/` separators. Results do not include `DATA_NOTICE` (they echo no
  stored content).

### 4. Annotations

Replace the `_WRITE_TOOLS` block and its comment:

```python
# MCP tool annotations (spec 2025-03-26): behaviour hints clients and
# directories read. Every tool works on local files only. wiki_sync adds
# files to raw/; the three page tools change files in wiki/ and only with
# confirm=true. Replacing a page or a field overwrites the old value.
_WRITE_TOOLS = {
    "wiki_sync", "wiki_write_page", "wiki_update_frontmatter", "wiki_archive_page",
}
_DESTRUCTIVE_TOOLS = {"wiki_write_page", "wiki_update_frontmatter"}
```

and in the loop use `"destructiveHint": _name in _DESTRUCTIVE_TOOLS`.
Keep `idempotentHint: True` (the same call twice gives the same file) and
`openWorldHint: False` for every tool.

### 5. Server instructions

Append one line to `SERVER_INSTRUCTIONS` (card 12), before the
"stored data" line:

```python
    "- Change the wiki only when the user asks. Call wiki_write_page, "
    "wiki_update_frontmatter or wiki_archive_page without confirm first, "
    "show the preview to the user, then repeat the call with "
    "confirm=true.\n"
```

The total must stay ≤ 2048 characters (card 11's test checks it).

### 6. Existing tests

- `tests/test_mcp_enhanced.py`:
  - rename `test_all_12_tools_registered` to `test_all_tools_registered`,
    expect 15 tools and add the three names to the required list;
  - in `test_every_tool_has_title_and_behaviour_annotations`, replace
    `assert annotations["destructiveHint"] is False` with
    `assert annotations["destructiveHint"] is (tool["name"] in {"wiki_write_page", "wiki_update_frontmatter"})`;
  - rename `test_only_wiki_sync_writes` to `test_write_tools_are_marked`
    and expect the four names in `_WRITE_TOOLS`;
  - fix the "12 similar tools" wording in the sibling-tool docstring.
- `tests/test_mcp_protocol.py`: `len(tools) == 15`.

Change nothing else in those files.

### 7. Docs

- `README.md`, "MCP server" row: `15 tools: query, search, read, list
  sources, lint, sync, exports, dashboard, write/edit/archive pages (with a
  confirm step)…`
- If `docs/competitor-landscape.md` (card 15) says "12 MCP tools", change
  it to 15.
- `CLAUDE.md`, "Log Format": add `edit` to the operations list.
- `CLAUDE.md` and `AGENTS.md`, hard rule 6 from card 22: it must name "MCP
  write tools" among the writers that never change an `origin: human` page.
  Add the words if card 22 did not.
- `CHANGELOG.md`: one line under `## [Unreleased]`.

## Tests

New `tests/test_mcp_write_tools.py`. Use
`monkeypatch.setattr(server, "REPO_ROOT", tmp_path)` and create
`tmp_path / "wiki"`. Call the `tool_*` functions directly.

Frontmatter writer:

- Round trip for `title` with `:` and `"`, `tags` list, `confidence`
  float, `lifecycle` string.
- An existing block list (`tags:` + `  - a` lines) is replaced by one
  inline line.
- A missing key is appended; text without frontmatter gets a block.
- The body is unchanged byte for byte, also with CRLF line endings.
- Newline in a value and a tag with `,` raise `ValueError`.

`wiki_write_page`:

- Without `confirm` → `written: false`, no file and no folder created.
- `create` + `confirm=true` → file exists, `origin: agent`,
  `last_updated` is today, `title` kept; `wiki/log.md` (when present) gets
  one `edit` line.
- `create` on an existing page → error; `replace` + `confirm=true`
  overwrites it; `replace` on a missing page → error.
- Refused: `../x.md`, `raw/sessions/a.md`, `docs/a.md`, `wiki/index.md`,
  `wiki/sub/log.md`, `wiki/a.txt`, `wiki/.hidden/a.md`,
  `wiki/archive/a.md`, a symlink inside `wiki/` pointing outside it,
  content without `title`, content over 1 MiB.
- An existing page with `origin: human` is refused and stays byte for
  byte, also with `confirm=true`.
- `wiki/candidates/concepts/Fact.md` can be created (the "remember" path).

`wiki_update_frontmatter`:

- `fields={"tags": [...]}` replaces tags; `add_tags` / `remove_tags`
  change them; the body is unchanged byte for byte.
- Unknown key, bad lifecycle, confidence 1.5, newline in title → error,
  file unchanged.
- No `fields`, `add_tags` or `remove_tags` → error.
- Preview returns `changes` with old and new values and writes nothing.
- `origin: human` page → refused.

`wiki_archive_page`:

- Sets `lifecycle: archived` and `archived_reason`; the file stays in
  place; without `confirm` nothing changes.
- Second call → `written: false`.
- Missing `reason` → error. `origin: human` page → refused.

Protocol:

- `tools/list` (through `handle_tools_list`) contains the three tools with
  `readOnlyHint: false`.

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_write_tools.py tests/test_mcp_enhanced.py tests/test_mcp_protocol.py tests/test_mcp_description_limits.py tests/test_frontmatter_shared.py -q
.venv/bin/python -m pytest tests/ -q
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | .venv/bin/python -m sessionwiki mcp | .venv/bin/python -c "import json,sys; print(len(json.load(sys.stdin)['result']['tools']))"
```

The last command prints `15`.

## Acceptance criteria

- [ ] Three write tools exist, preview by default and write only with
      `confirm=true`.
- [ ] No tool writes outside `wiki/`, into `wiki/archive/`, into a system
      page or into an `origin: human` page.
- [ ] Nothing is deleted; archiving keeps the file.
- [ ] Annotations mark the four writers and the two destructive tools.
- [ ] Descriptions and `instructions` pass card 11's limits.
- [ ] README, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md` updated.
- [ ] All tests pass.

## Out of scope

- Hard delete, rename or move of pages.
- Updating `wiki/index.md` (lint reports orphans; `build` regenerates the
  site).
- Protecting `origin: agent` pages from `synthesize --force` (card 22
  guards only `origin: human`).
- A file lock across concurrent writers (writes are atomic; last writer
  wins).
- A separate `wiki_remember` tool (use `wiki_write_page` under
  `wiki/candidates/`).
- Access stats (A4) and save-back of answers (D4); they reuse these tools
  later.

## Rollback

Revert the files. No data migration: pages written by the tools are plain
Markdown with `origin: agent`.
