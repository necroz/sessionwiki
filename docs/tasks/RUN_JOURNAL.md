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

## 2026-11-09 10:26 — card 13: `recall`: say when to search

- Status: done
- Files: `sessionwiki/cli.py`, `tests/test_mcp_recall.py`, `CHANGELOG.md`
- Gates: targeted 9 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version rc 0, `recall` text and `--format hook` both print
  `Before you ask the user about earlier work, call the wiki_query tool`,
  privacy grep clean, synth state unchanged
- Commit: b326c2a
- Decisions: added the `Before you ask the user` assertion to the hook-format
  test too, so both output formats are covered by the acceptance criteria
  (the card named only the text test).
- Next card: 14
- Blockers: none

## 2026-11-09 10:52 — card 14: Align docs with the code

- Status: done
- Files: `README.md`, `docs/index.md`, `docs/roadmap.md`, `CHANGELOG.md`
- Gates: targeted 38 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version rc 0, `grep -n "8 sources" README.md` prints nothing (rc 1),
  privacy grep clean
- Commit: 2668956
- Decisions: the adapter list matches the card — 4 core
  (`claude_code`, `codex_cli`, `opencode`, `zcode`) and 6 contrib
  (`chatgpt`, `copilot_chat`, `copilot_cli`, `cursor`, `gemini_cli`,
  `obsidian`). The card's replacement row was used verbatim. Translated
  READMEs under `docs/i18n/` stay untouched (out of scope); they still carry
  the old counts as a follow-up.
- Next card: 15
- Blockers: none

## 2026-11-09 11:31 — card 15: Rewrite the competitor landscape

- Status: done
- Files: `docs/competitor-landscape.md`, `CHANGELOG.md`
- Gates: targeted 28 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version rc 0, `grep -nE 'Rewind|Pieces|PDF|6 agents|stdlib only'` prints
  nothing (rc 1), privacy grep clean, synth state unchanged
- Commit: 067dadb
- Decisions: unknown table cells are `—` per the card, including the
  "needs an LLM" and "MCP server" rows; claude-mem's retroactive cell says
  "Early versions: no day-zero import" because the map does not claim the
  current version lacks it; star counts are one line under the table with the
  date and the GitHub API as the source.
- Next card: 16
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 11:34 — card 16: Publish recall results

- Status: done
- Files: `docs/benchmarks.md`, `CHANGELOG.md`
- Gates: `tests/test_docs_structure.py` 28 passed (rc 0), full suite
  2938 passed / 28 skipped (rc 0), lint 16 → 16 errors, version 2.0.5
  (rc 0), `grep -n "Retrieval recall"` rc 0, privacy grep clean,
  synth state unchanged
- Commit: 190b5fa
- Decisions: every table cell was checked against
  `.metrics/recall-{base,graph}-{k5,k10}.json` (`by_kind` and `overall`);
  all rounded values match, so the card's table was used unchanged.
  `CHANGELOG.md` is not in the card's Files list, but `README.md` and
  `.kiro/steering/contributing-rules.md` require an Unreleased line on every
  change; one line was added and this is the interpretation.
- Next card: 17
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 11:43 — card 17: `query` on the MCP ranking engine

- Status: done
- Files: `sessionwiki/mcp/server.py`, `sessionwiki/cli.py`,
  `tests/test_cli_query.py` (new), `docs/reference/cli.md`, `CHANGELOG.md`
- Gates: targeted 29 passed (rc 0), full suite 2943 passed / 28 skipped
  (rc 0), lint 16 → 16 errors, version 2.0.5 (rc 0), `query … --limit 3`
  and `--limit 3 --json` rc 0, MCP text byte-identical to HEAD for 9
  queries, eval report identical to HEAD for all 24 queries, ruff 15 → 15,
  privacy grep clean, synth state unchanged
- Commit: 5d459d2
- Decisions: `rank_query(..., include_raw: bool | None)` instead of the
  card's `Optional[bool]` — the repo's ruff config selects UP045 and
  `server.py` already uses `Path | None`; `Optional` would have added a
  16th ruff error. The CLI's and the server's `REPO_ROOT` are the same
  object (`from sessionwiki import REPO_ROOT`), so they cannot diverge.
  The card's eval step was run as a HEAD-vs-new comparison, not against
  `.metrics/recall-*.json`: the wiki content changed after the Nov-6
  snapshot (now overall recall@5 55.6%, hit@5 66.7%), so the old file is
  not a valid baseline for a code change.
- Next card: 18
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 12:15 — card 18: `recall --format json`

- Status: done
- Files: `sessionwiki/cli.py`, `tests/test_mcp_recall.py`,
  `docs/reference/cli.md`, `CHANGELOG.md`
- Gates: targeted 11 passed (rc 0), full suite 2973 collected (rc 0; the
  summary line is not printed by pytest 9.1.1 in this environment), lint
  16 → 16 errors, version 2.0.5 (rc 0), `recall --project llm-wiki
  --limit 2 --format json` printed valid JSON with two sessions (rc 0),
  ruff on the changed files 11 → 11 with none in the new lines, privacy
  grep clean, synth state unchanged
- Commit: 6dc48cd
- Decisions: `docs/reference/cli.md` is not in the card's Files list, but
  the page said "Prints nothing when the project has no sessions", which
  the json format makes false; added the json example and one clause.
  `sessions` uses the card's key order (`date`, `request`, `summary`,
  `path`) and the text/hook branches are untouched.
- Next card: 19
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 12:25 — card 19: `doctor` reports the synthesis backlog

- Status: done
- Files: `sessionwiki/doctor.py`, `tests/test_doctor.py`, `CHANGELOG.md`
- Gates: targeted 8 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version 2.0.5 (rc 0), `doctor` prints `[warn] synthesis 13 raw session(s)
  not synthesized, 0 page(s) waiting for the agent — run `sessionwiki
  synthesize`` and exits 0, ruff on changed files clean, privacy grep clean,
  synth state unchanged
- Commit: dbee2b2
- Decisions: `_check_synthesis` skips `_`-prefixed raw files, matching
  `_discover_raw_sessions`; the card's snippet lacked that skip, but the
  acceptance criterion requires the pipeline's exact rule. The maintainer's
  backlog is 13 sessions, not the ~115 in the Problem section — the number
  shrank before this card and is not an acceptance criterion. `CHANGELOG.md`
  is not in the card's Files list, but the repo rules require an Unreleased
  line for every change.
- Next card: 20
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.
