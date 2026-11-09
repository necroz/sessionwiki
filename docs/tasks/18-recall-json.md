# 18 — `recall --format json`

- Priority: P1
- Roadmap: Phase 0, E7 (recall part)
- Depends on: 13 (same function; avoid merge conflicts)
- Size: S (30–45 min)
- Files: `sessionwiki/cli.py`, `tests/test_mcp_recall.py`
- Branch: `feat/recall-json`
- PR title: `feat(recall): add a JSON output format`

## Read first

- `sessionwiki/cli.py`: `_recent_sessions`, `cmd_recall` and the `recall`
  parser (search for `"recall"`)
- `tests/test_mcp_recall.py`: `_seed_project`, `_recall`

## Problem

`recall` prints text or SessionStart hook JSON. Scripts and other agents
need the list itself.

## Required change

1. Parser: `choices=["text", "hook", "json"]`; help:
   `"text, hook = SessionStart JSON with additionalContext, json = machine-readable list"`.

2. In `cmd_recall`, handle `json` **before** the `if not items: return 0`
   check, so an unknown project still prints a valid document:

```python
if args.format == "json":
    print(json.dumps({
        "project": project,
        "notice": DATA_NOTICE,
        "sessions": [
            {"date": day, "request": request, "summary": summary, "path": path}
            for day, request, summary, path in items
        ],
    }, ensure_ascii=False, indent=2))
    return 0
```

Text and hook output stay unchanged.

## Tests

Add to `tests/test_mcp_recall.py`:

- `--format json` for project `app` returns `sessions` newest first, with
  the same requests the text test checks.
- `--format json` for an unknown project returns `{"sessions": []}` with the
  project name.

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_recall.py -q
.venv/bin/python -m sessionwiki recall --project llm-wiki --limit 2 --format json
```

## Acceptance criteria

- [ ] JSON format works and is valid JSON.
- [ ] Unknown project prints an empty list, not nothing.
- [ ] Other formats unchanged.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- Handoff block (card 23 adds a `handoff` key).

## Rollback

Remove the branch and the choice.
