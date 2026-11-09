# 13 — `recall`: say when to search

- Priority: P0
- Roadmap: Phase 0 (kaeru lesson, precursor of C1)
- Depends on: none
- Size: S (15–20 min)
- Files: `sessionwiki/cli.py`, `tests/test_mcp_recall.py`
- Branch: `feat/recall-when-to-search`
- PR title: `feat(recall): tell the agent to search before asking the user`

## Read first

- `sessionwiki/cli.py`, `cmd_recall` (around line 120)
- `tests/test_mcp_recall.py`, `test_recall_lists_recent_sessions_of_the_project_newest_first`

## Problem

`recall` ends with:

```
Search earlier work with the wiki_query tool; open a page with wiki_read_page.
```

It does not say *when*. Agents ignore optional wording (kaeru: 0/7).

## Required change

In `cmd_recall`, replace the last line with:

```python
lines += [
    "",
    "Before you ask the user about earlier work, call the wiki_query tool; "
    "open a page with wiki_read_page.",
]
```

Add to `test_recall_lists_recent_sessions_of_the_project_newest_first`:

```python
assert "Before you ask the user" in text
```

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_recall.py -q
.venv/bin/python -m sessionwiki recall --project llm-wiki --limit 2
```

## Acceptance criteria

- [ ] The new line is printed in text and hook formats.
- [ ] Tests pass.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- Any other change to `recall` output (cards 18, 23).

## Rollback

Restore the old line and remove the assertion.
