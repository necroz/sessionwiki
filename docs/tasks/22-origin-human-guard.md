# 22 — Never overwrite pages with `origin: human`

- Priority: P0
- Roadmap: Phase 1, B3
- Depends on: none
- Size: S (1–1.5 h)
- Files: `sessionwiki/_frontmatter.py`, `sessionwiki/synth/pipeline.py`,
  `tests/test_synth_origin_human.py` (new), `CLAUDE.md`, `AGENTS.md`
- Branch: `feat/origin-human-guard`
- PR title: `feat(synth): keep human-written pages out of synthesis rewrites`

## Read first

- `sessionwiki/synth/pipeline.py`:
  - `_process_one` and `_record` inside `_synthesize_new_sessions_unlocked`
    (around line 1490) — writes `out_path`
  - the coalescing writer (around line 900, `page_path.write_text(content ...)`)
  - the backfill writer (around line 490, `page.write_text(head + new_body ...)`)
  - the `summary` dict (around line 1409)
- `sessionwiki/_frontmatter.py`: `parse_frontmatter`
- `tests/test_synth_pipeline.py`: how tests build a raw dir, a sources dir
  and a state file in `tmp_path`
- `CLAUDE.md`, section "Hard rules"

## Problem

The synthesis pipeline overwrites an existing source page without checking
who wrote it. A human who edits a page, or a page imported from built-in
memory (card 26), loses the edit on the next `synthesize --force`.

## Required change

1. Public helper in `sessionwiki/_frontmatter.py`, below
   `parse_frontmatter_or_none`. Card 30 (MCP write tools) uses it too, so it
   must not live in `pipeline.py`. Add `from pathlib import Path` to the
   imports there.

```python
def is_human_page(path: Path) -> bool:
    """True when an existing page says ``origin: human`` in its frontmatter."""
    if not path.is_file():
        return False
    try:
        with path.open("rb") as f:
            head = f.read(8 * 1024).decode("utf-8", errors="replace")
    except OSError:
        return False
    meta, _ = parse_frontmatter(head)
    return str(meta.get("origin", "")).strip().lower() == "human"
```

   If `parse_frontmatter` needs the closing `---` inside the head, 8 KB is
   enough for normal pages; do not read the whole file.

   In `pipeline.py`: `from sessionwiki._frontmatter import is_human_page`.

2. `_process_one`: before calling the backend, `if is_human_page(out_path):`
   return a new status `"human"` (same tuple shape, `mtime` set, no error).
   Do not call the backend for that session.

3. `_record`: for `"human"`, set `state[rel] = mtime` (so it is not retried
   every run), add 1 to `summary["kept_human"]` and print
   `  kept human page: {project} → {filename}`.

4. Add `"kept_human": 0` to the `summary` dict.

5. Coalescing and backfill writers: skip the write when
   `is_human_page(<target>)` is true.

6. Docs. In `CLAUDE.md`, "Hard rules", add:

```markdown
6. **Human pages are read-only for the LLM.** A page with `origin: human`
   in its frontmatter is never rewritten by synthesis, coalescing,
   backfill, ingest or the MCP write tools. Put hand-written notes under
   `wiki/notes/`.
```

   If `AGENTS.md` repeats the hard rules, add the same rule there.

## Tests

New `tests/test_synth_origin_human.py`:

- An existing source page with `origin: human` survives
  `synthesize_new_sessions(..., force=True)` byte for byte; the backend's
  `synthesize_source_page` is never called for it (use a stub backend that
  records calls); `summary["kept_human"] == 1`.
- The same page without `origin` is overwritten (control).
- `is_human_page` is False for a missing file and for `origin: llm`, and
  importable from `sessionwiki._frontmatter`.

## Verification

```bash
.venv/bin/python -m pytest tests/test_synth_origin_human.py tests/test_synth_pipeline.py tests/test_synth_coalesce.py -q
.venv/bin/python -m pytest tests/ -q
```

Back up `.llmwiki-synth-state.json` before running tests, as
`docs/tasks/README.md` describes.

## Acceptance criteria

- [ ] Human pages survive all three writers.
- [ ] No backend call for a human page.
- [ ] The rule is in `CLAUDE.md`.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- A lint rule for `origin`.
- Creating `wiki/notes/` (card 26 does it).

## Rollback

Revert the files.
