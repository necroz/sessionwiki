---
name: Adapter request
about: Ask for support for a new coding agent (Cursor, Cline, Aider, …)
title: 'adapter: '
labels: 'adapter, enhancement'
---

## Agent

<!-- Which coding agent? -->

- Name:
- Homepage:
- My version:

## Session store

- Where does this agent write session transcripts?
  - Path: <!-- e.g. ~/.cursor/sessions/ -->
  - File pattern: <!-- e.g. <uuid>.jsonl -->

## Record format

<!-- Paste a small sample (1-2 records) with any PII redacted -->

```jsonl
{"type": "user", "content": "...", ...}
{"type": "assistant", "content": "...", ...}
```

## Known record types

<!-- List any you've seen — user, assistant, tool_use, tool_result, system, etc. -->

## Are you willing to contribute this adapter?

- [ ] Yes, I'll open a PR
- [ ] I can help test but not write code
- [ ] No, just reporting

## Contract reminder

Per `docs/framework.md §5.25 Adapter Flow`, a new adapter needs:

1. `sessionwiki/adapters/<agent>.py`
2. `tests/fixtures/<agent>/minimal.jsonl`
3. `tests/snapshots/<agent>/minimal.md`
4. `tests/test_<agent>_adapter.py`
5. `docs/adapters/<agent>.md`
6. README update
7. CHANGELOG entry
