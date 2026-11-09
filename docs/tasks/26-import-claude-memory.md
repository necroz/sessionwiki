# 26 — `sessionwiki import-memory` for Claude Code auto memory

- Priority: P0
- Roadmap: Phase 2, C5
- Depends on: 22 (`origin: human` guard)
- Size: M (2–3 h)
- Files: `sessionwiki/memory_import.py` (new), `sessionwiki/cli.py`,
  `sessionwiki/lint/rules/frontmatter_validity.py`,
  `tests/test_memory_import.py` (new), `docs/reference/cli.md`
- Branch: `feat/import-claude-memory`
- PR title: `feat: mirror Claude Code auto memory into wiki/notes`

## Read first

- `sessionwiki/adapters/claude_code.py`: `session_store_path`,
  `derive_project_slug`
- `sessionwiki/convert.py`: `class Redactor` (around line 616) and how
  `convert` builds it from the config (search `Redactor(config)`)
- `sessionwiki/lint/rules/frontmatter_validity.py`: `VALID_TYPES`
- `sessionwiki/cli.py`: how a small subcommand is registered (for example
  `recall`)

## Problem

Claude Code writes its own memory: `~/.claude/projects/<dir>/memory/MEMORY.md`
and topic files. The wiki does not see it, so sessionwiki competes with a
free built-in feature instead of including it.

Memory files change in place. `raw/` is immutable, so they must **not** go
through `raw/`. They are written by the user (or by the agent on the user's
request), so they are `origin: human` and synthesis must never rewrite them
(card 22).

## Required change

1. New `sessionwiki/memory_import.py`:

```python
def import_claude_memory(
    store: Path,
    wiki_dir: Path,
    config: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Mirror <store>/<dir>/memory/*.md into wiki/notes/claude-memory/<project>/.

    Returns {"written": [...], "unchanged": int, "skipped": [...]}.
    """
```

   For each `<store>/<dir>/memory/*.md`:

   - `project = ClaudeCodeAdapter().derive_project_slug(store / dir / "x.jsonl")`.
     Check that `derive_project_slug` uses `self.session_store_path`; pass a
     store that matches it or set the attribute on the instance for tests.
   - Destination: `wiki_dir / "notes" / "claude-memory" / project / <file name>`.
   - Split the memory file's own frontmatter (it may have `name`,
     `description`, `metadata`) from its body with `parse_frontmatter`.
   - Write:

```markdown
---
title: "Claude memory: <project> — <file stem>"
type: note
origin: human
project: <project>
description: "<memory description, if any>"
source_path: "~/.claude/projects/<dir>/memory/<file>"
tags: [claude-memory, <project>]
last_updated: <file mtime as YYYY-MM-DD>
---

<body, passed through the Redactor>

## Connections

- [[<ProjectEntity>]] — project
```

   - `source_path` starts with `~`, never the absolute home path (privacy).
   - Apply the same `Redactor` that `convert` uses to the body and the
     description.
   - Write only when the content differs from the existing file
     (`unchanged` += 1 otherwise).
   - If the destination exists and is **not** `origin: human`, do not touch
     it; add it to `skipped` with a reason.
   - Never delete destination files.
   - Create `wiki/notes/` if needed.

2. CLI subcommand:

```
sessionwiki import-memory [--store PATH] [--dry-run]
```

   Default store: `ClaudeCodeAdapter.session_store_path`. Print one line per
   written file and a summary line. Load the config the same way `sync`
   does.

3. Add `"note"` to `VALID_TYPES` in `frontmatter_validity.py`.

4. `docs/reference/cli.md`: add the command.

## Tests

New `tests/test_memory_import.py` with a fake store in `tmp_path`:

- One project dir with `MEMORY.md` and `topic.md` → two files under
  `wiki/notes/claude-memory/<project>/` with `origin: human`.
- `source_path` starts with `~/.claude/projects/`.
- A second run reports `unchanged == 2` and writes nothing.
- A changed memory file is rewritten.
- An existing destination without `origin: human` is skipped.
- A token-like secret in the body is redacted (use a pattern the default
  `Redactor` already catches; read its default patterns).
- `--dry-run` writes nothing.
- `wiki_query` finds a word from the imported body (seed `REPO_ROOT` as
  other MCP tests do).

## Verification

```bash
.venv/bin/python -m pytest tests/test_memory_import.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m sessionwiki import-memory --dry-run
```

## Acceptance criteria

- [ ] Memory files mirrored with `origin: human`, redacted, `~` paths.
- [ ] Idempotent; never deletes; never overwrites non-human pages.
- [ ] `note` is a valid type; lint passes.
- [ ] Docs and `CHANGELOG.md` updated.

## Out of scope

- Codex memories.
- Running import from `sync` automatically (follow-up after real use).
- Writing back into Claude Code memory.

## Rollback

Remove the module, the subcommand and the type.
