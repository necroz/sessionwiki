# 23 — Handoff block in `recall`

- Priority: P0
- Roadmap: Phase 1, C2
- Depends on: 18 (JSON format)
- Size: M (1.5–2 h)
- Files: `sessionwiki/cli.py`, `tests/test_mcp_recall.py`
- Branch: `feat/recall-handoff`
- PR title: `feat(recall): show where the last session stopped`

## Read first

- `sessionwiki/cli.py`: `_recent_sessions`, `cmd_recall`
- One raw transcript under `raw/sessions/`: turns are headed
  `### Turn N — User` and `### Turn N — Assistant`
- One source page: the `source_file:` frontmatter key points at the raw file
- `tests/test_mcp_recall.py`: `_seed_project`, `_recall`

## Problem

`recall` lists sessions but does not say what the last one ended with. For
the newest session there is often no wiki page yet ("not in the wiki yet"),
so a summary-based handoff would be empty. The raw transcript always
exists. Raw files can be over 1 GB, so never read a whole file.

## Required change

1. Helpers in `cli.py`:

```python
_TURN_RE = re.compile(r"^### Turn \d+ — (User|Assistant)\s*$", re.MULTILINE)
_HANDOFF_TAIL_BYTES = 64 * 1024
_HANDOFF_MAX_CHARS = 400


def _raw_path_for(path: str) -> Optional[Path]:
    """The raw transcript behind a recall item (a raw path or a wiki page)."""
    p = REPO_ROOT / path
    if path.startswith("raw/"):
        return p if p.is_file() else None
    from sessionwiki._frontmatter import parse_frontmatter
    try:
        with p.open("rb") as f:
            meta, _ = parse_frontmatter(f.read(8 * 1024).decode("utf-8", errors="replace"))
    except OSError:
        return None
    src = str(meta.get("source_file", "")).strip()
    raw = REPO_ROOT / src if src else None
    return raw if raw is not None and raw.is_file() else None


def _last_assistant_text(raw: Path) -> str:
    """First characters of the last assistant turn, read from the file's tail."""
    try:
        with raw.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _HANDOFF_TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    turns = list(_TURN_RE.finditer(tail))
    for i in range(len(turns) - 1, -1, -1):
        if turns[i].group(1) != "Assistant":
            continue
        end = turns[i + 1].start() if i + 1 < len(turns) else len(tail)
        text = tail[turns[i].end():end]
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"^#+ .*$", " ", text, flags=re.MULTILINE)
        text = " ".join(text.split())
        if not text:
            continue
        return text if len(text) <= _HANDOFF_MAX_CHARS else text[: _HANDOFF_MAX_CHARS - 1].rstrip() + "…"
    return ""
```

   Check the exact turn heading in a real transcript (the dash is `—`,
   U+2014). If it differs, use the real form and say so in the PR body.
   `Optional` and `re` may need imports.

2. In `cmd_recall`, after `items` is built, compute the handoff for the
   newest item only:

```python
handoff = ""
if items:
    raw = _raw_path_for(items[0][3])
    handoff = _last_assistant_text(raw) if raw else ""
```

3. Text and hook output: after the session list and before the final
   instruction line, when `handoff` is not empty:

```
Last session ended with («<request of items[0]>», <date>):
<handoff>
```

4. JSON output (card 18): add
   `"handoff": {"path": items[0][3], "date": items[0][0], "text": handoff}`
   when there are items, else `"handoff": null`.

## Tests

Add to `tests/test_mcp_recall.py`:

- The newest session is raw-only and ends with an assistant turn that has a
  code block: the handoff contains the prose, not the code.
- The newest session has a wiki page whose `source_file` points at a raw
  file: the handoff comes from that raw file.
- A transcript with no assistant turn: no handoff block.
- A transcript larger than 64 KB: only the tail is read (patch
  `_HANDOFF_TAIL_BYTES` to a small value and check the result).
- JSON format has the `handoff` key.

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_recall.py -q
.venv/bin/python -m sessionwiki recall --project llm-wiki --limit 3
```

## Acceptance criteria

- [ ] Handoff shown for the newest session, from raw.
- [ ] Never reads more than the tail of a transcript.
- [ ] Code blocks and headings removed; ≤ 400 characters.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- LLM summaries of the handoff.
- Open questions (needs D3).

## Rollback

Revert the files.
