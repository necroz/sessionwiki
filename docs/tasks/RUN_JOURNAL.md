# Run journal

Append-only. The worker reads the last three entries on every run.
Newest entries go at the bottom.

## 2026-11-09 — setup

- Status: done
- Added the autonomous worker protocol (`AUTONOMOUS.md`) and the
  November 2026 card queue (cards 11–30).
- Automation: hourly, local commits only (no push).
- Next card: 11.

## 2026-11-09 10:04 — card 11: Guard MCP description and instructions length

- Status: done
- Files: `tests/test_mcp_description_limits.py`, `CHANGELOG.md`
- Gates: pytest 4 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version rc 0, privacy grep clean
- Commit: b07afa0
- Decisions: none
- Next card: 12
- Blockers: none

## 2026-11-09 10:14 — card 12: Send MCP server instructions

- Status: done
- Files: `sessionwiki/mcp/server.py`, `tests/test_mcp_description_limits.py`,
  `CHANGELOG.md`
- Gates: targeted 10 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version rc 0, `initialize` JSON contains `instructions`, privacy grep clean
- Commit: 8a45b02
- Decisions: none
- Next card: 13
- Blockers: none. Unrelated changes from a parallel process
  (`docs/reference/*`, `wiki/archive/seed/*`, `sessionwiki/lint/__init__.py`,
  `tests/test_lint_rules.py`) were present and left uncommitted.
