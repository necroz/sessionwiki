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

## 2026-11-09 13:05 — card 20: Filters in `wiki_query` and `query`

- Status: done
- Files: `sessionwiki/mcp/server.py`, `sessionwiki/cli.py`,
  `tests/test_mcp_query_filters.py` (new), `docs/reference/cli.md`,
  `CHANGELOG.md`
- Gates: targeted 19 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version 2.0.5 (rc 0), `query release --project llm-wiki --limit 3`
  printed three `wiki/sources/llm-wiki/…` hits (rc 0), ruff on changed
  files 15 → 15 with none on the new lines, privacy grep clean,
  synth state unchanged
- Commit: c467ebb
- Decisions: the filter check in the wiki loop sits before the
  `page_by_slug` registration as well as before `_collect`/`links`, so a
  filtered-out source page cannot become a raw target either; raw
  transcripts are filtered by their own frontmatter. `filters` is typed
  `dict[str, str] | None` (not the card's `Optional`) because ruff
  selects UP045, the card-17 precedent. Non-string and empty values are
  dropped, an unparseable date is dropped instead of raising. The graph
  hop still runs between two allowed pages that share a name — only
  filtered-out pages are excluded. `--graph` ignores the filters (out of
  scope). `docs/reference/cli.md` gained the five flags and an example.
- Next card: 21
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 13:26 — card 21: Downrank stale and archived pages

- Status: done
- Files: `sessionwiki/mcp/server.py`, `tests/test_mcp_query_filters.py`,
  `CHANGELOG.md`
- Gates: targeted 22 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version 2.0.5 (rc 0), eval on `.metrics/recall-queries.json` unchanged
  before → after (k=5 recall 55.6% / hit 66.7%, k=10 recall 74.3% /
  hit 83.3%; no drop, far below the 0.02 limit), ruff on the changed files
  4 → 4 with none on the new lines, `git grep ilashkevich` rc 1,
  synth state unchanged
- Commit: d9b2b0f
- Decisions: the card's snippet was used verbatim, including
  `_LIFECYCLE_WEIGHT = {"stale": 0.5, "archived": 0.25}` and the single
  line in the wiki loop; the raw loop is untouched. The eval numbers are
  recorded here because the worker has no PR body. The stale test asserts
  `score(fresh) > score(stale)` as well as the order: without the weight
  the two scores tie and path order alone put the fresh page first, so an
  order-only assertion passed with the change reverted. Both tests were
  checked to fail against HEAD and pass with the change. The test module's
  docstring gained two lines naming the lifecycle tests.
- Next card: 22
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 13:55 — card 22: Never overwrite pages with `origin: human`

- Status: done
- Files: `sessionwiki/_frontmatter.py`, `sessionwiki/synth/pipeline.py`,
  `tests/test_synth_origin_human.py` (new), `CLAUDE.md`, `AGENTS.md`,
  `CHANGELOG.md`
- Gates: targeted 52 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version 2.0.5 (rc 0), ruff on the changed files 30 → 30 with none on the
  new lines, privacy grep clean, synth state unchanged
- Commit: 292ffb7
- Decisions: `is_human_page` is the card's snippet verbatim. Both writers
  named in the card were guarded: `_strip_unresolved_wikilinks` — the
  `page.write_text(head + new_body …)` site at the card's "around line 490"
  — and `backfill_source_descriptions`. The coalescing guard skips the
  whole group, not only the `page_path.write_text` call: deleting the
  member pages while leaving a human cluster page unchanged would lose
  their content. The page name is still added to `produced`, so the
  manifest-reconciliation loop never treats the human page as stale, and
  that loop's `unlink` also skips human pages. `AGENTS.md` repeats the hard
  rules, so it got the same rule 6. The locked-run return dict also carries
  `kept_human: 0`, so every summary shape has the key.
- Next card: 23
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 14:34 — card 23: Handoff block in `recall`

- Status: done
- Files: `sessionwiki/cli.py`, `tests/test_mcp_recall.py`, `CHANGELOG.md`
- Gates: targeted 16 passed (rc 0), full suite rc 0 (pytest 9.1.1 does
  not print the summary line in this environment), lint 16 → 16 errors,
  version 2.0.5 (rc 0), `recall --project llm-wiki --limit 3` printed the
  `Last session ended with («…», 2026-11-09):` block and exited 0, ruff on
  the changed files 11 → 11 with none on the new lines, privacy grep: one
  pre-existing hit (`RUN_JOURNAL.md:208`, the card-21 entry quotes the
  command), none in this diff, synth state unchanged
- Commit: 9fcd114
- Decisions: the real transcript heading is `### Turn N — User` /
  `### Turn N — Assistant` with U+2014, as the card expected, so the
  regex is the card's verbatim form. `Path | None` instead of the card's
  `Optional[Path]` because ruff selects UP045 (card-17 precedent). The
  handoff heading falls back to "(no request recorded)" when the newest
  session has no description, matching the session-list line. The card's
  Files list has no docs page, and `docs/reference/cli.md` makes no false
  claim after the change, so it was left untouched — the recall section
  does not mention the handoff yet; that is a follow-up.
- Next card: 24
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 14:55 — card 24: `synthesize --max-sessions N`

- Status: done
- Files: `sessionwiki/synth/pipeline.py`, `sessionwiki/cli.py`,
  `tests/test_synth_pipeline.py`, `CHANGELOG.md`
- Gates: targeted `tests/test_synth_pipeline.py` 38 passed (rc 0),
  `test_synth_pipeline.py` + `test_synth_coalesce.py` 50 passed (rc 0),
  full suite rc 0, lint 16 → 16 errors, version 2.0.5 (rc 0),
  `synthesize --help | grep max-sessions` rc 0, ruff on the changed files
  40 → 40 with none on the new lines, privacy grep clean, synth state
  unchanged, end-to-end run in a `/tmp` vault: run 1 printed
  `deferred: 1 session(s)` and wrote one page, run 2 wrote the second
- Commit: 274bc8d
- Decisions: the cap block is the card's snippet verbatim, placed directly
  before `if backend is None:` and after the `coalesce_only` early return;
  `summary["new_files"]` keeps the number of new sessions found (2) and
  `deferred` carries the rest, so both numbers stay meaningful. The locked
  run's return dict also carries `deferred: 0`, so every summary shape has
  the key (card-22 precedent). `max_sessions: int | None` instead of
  `Optional[int]` because ruff selects UP045 (cards 17, 20, 23 precedent);
  `Optional` would have added two errors. The CLI passes
  `getattr(args, "max_sessions", None)`: a hand-built `Namespace` in
  `tests/test_synth_coalesce.py` omits the field, and the file already uses
  `getattr` for `backfill_only` and `vault` for the same reason.
- Next card: 30
- Blockers: none. The end-to-end smoke test used the configured
  OpenAI-compatible backend at `http://10.3.71.12:8001/v1` because the
  `synthesize` command has no backend override flag; only the two-line
  throwaway fixture was sent, and the temp vault was deleted. The
  pre-existing uncommitted `docs/tasks/AUTONOMOUS.md` change (scheduling
  notes) was left untouched and is not part of the card.

## 2026-11-09 15:40 — card 30: Guarded MCP write tools

- Status: done
- Files: `sessionwiki/_frontmatter.py`, `sessionwiki/mcp/server.py`,
  `tests/test_mcp_write_tools.py` (new), `tests/test_mcp_enhanced.py`,
  `tests/test_mcp_protocol.py`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`,
  `docs/competitor-landscape.md`
- Gates: targeted 118 passed (rc 0), full suite rc 0, lint 16 → 16 errors,
  version 2.0.5 (rc 0), `tools/list` prints `15` (rc 0), ruff on the changed
  files 7 → 7 with none on the new lines, privacy grep clean, synth state
  unchanged
- Commit: 027408f
- Decisions: the three descriptions are the card's text verbatim and measure
  767, 678 and 534 characters; `SERVER_INSTRUCTIONS` grew from 706 to 906
  characters, inside card 11's 2048 cap. `_resolve_wiki_write_path` checks a
  symlink first (so a link that escapes the repo reports the symlink, not the
  escape), then `_safe_path`, `wiki/`, hidden parts, the `.md` suffix,
  `wiki/archive/`, `is_system_file` and `is_human_page`; the human-page
  message is the card's exact text. `_page_tags` also reads the block-list
  form (`tags:` plus `  - item`), because `parse_frontmatter` skips bullet
  lines and `add_tags` would otherwise drop the current tags when
  `set_frontmatter_fields` rewrites the field. `tests/test_mcp_protocol.py`'s
  test was renamed `test_tools_list_returns_fifteen_tools` so the name does
  not say twelve. `AGENTS.md` and `CLAUDE.md` rule 6 already named "the MCP
  write tools" from card 22, so neither needed an edit. `docs/`
  `competitor-landscape.md` had the count twice (the comparison cell and the
  closing paragraph); both now say 15. The new MCP tests call the `tool_*`
  functions directly with `REPO_ROOT` monkeypatched to `tmp_path`.
- Next card: 25
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 16:20 — card 25: `extractive` synthesis backend

- Status: done
- Files: `sessionwiki/synth/extractive.py` (new),
  `sessionwiki/synth/pipeline.py` (`resolve_backend` only),
  `tests/test_synth_extractive.py` (new), `docs/configuration-reference.md`,
  `CHANGELOG.md`
- Gates: targeted `test_synth_extractive.py` 8 passed (rc 0),
  `test_synth_extractive.py` + `test_synth_pipeline.py` +
  `test_synth_config_loading.py` 51 passed (rc 0), full suite rc 0,
  lint 16 → 16 errors, version 2.0.5 (rc 0), ruff clean on the new files and
  `pipeline.py` 29 → 29 with none on the new lines, privacy grep: one
  pre-existing hit (`RUN_JOURNAL.md:208`, the card-21 entry quotes the
  command), synth state unchanged; manual check on a copy of all 998 raw
  sessions in `/tmp/sw-extractive` took 4.9 s (rc 0), wrote 998 pages,
  `lint --wiki-dir` on the copy reported 0 errors, and an audit found the
  four sections on every page
- Commit: 336b447
- Decisions: `name` is a property returning `"ExtractiveSynthesizer"`, as in
  `BaseSynthesizer` and the other backends — the card's
  `name = "extractive"` would shadow the base property, and the printed
  backend name then matches `DummySynthesizer`/`OllamaSynthesizer`.
  `is_available` stays inherited from `DummySynthesizer` (always True), so no
  override. The quote uses the same fence-free text as the claims; the card
  only required fence removal before sentences, and this keeps code out of a
  blockquote. Leading transcript list markers are stripped, so a list item no
  longer renders as `- - …` (found in the manual check, pinned by a test).
  The manual check needs the repo-root `config.local.json`: `resolve_config`
  reads `examples/`, `config.json` and `config.local.json` from `REPO_ROOT`,
  never from the vault, so the file was swapped for
  `{"synthesis": {"backend": "extractive"}}` and restored byte-identically
  (`cmp` silent). In that copy every `[[ProjectEntity]]` link was degraded to
  plain text because `strip_unresolved_wikilinks` defaults to true and the
  copy has no entity pages. Known limitation: a transcript sentence that
  starts with `**Tools used:**` and contains "because" still becomes a claim;
  it is verbatim text, and filtering bolded `Label:` sentences would also drop
  real fix statements.
- Next card: 26
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

## 2026-11-09 16:31 — card 26: `import-memory` for Claude Code auto memory

- Status: done
- Files: `sessionwiki/memory_import.py` (new), `sessionwiki/cli.py`,
  `sessionwiki/lint/rules/frontmatter_validity.py`,
  `sessionwiki/lint/rules/index_sync.py`, `tests/test_memory_import.py`
  (new), `docs/reference/cli.md`, `CHANGELOG.md`
- Gates: targeted `tests/test_memory_import.py` 9 passed (rc 0),
  `test_reference_coverage.py` + `test_docs_structure.py` 37 passed (rc 0),
  full suite rc 0, lint 16 → 16 errors, version 2.0.5 (rc 0),
  `import-memory --dry-run` rc 0 and wrote nothing (4 real memory files
  listed), ruff: 11 pre-existing errors in `cli.py`, none on the new lines;
  the new module and test are clean, `git grep ilashkevich` rc 0 with one
  pre-existing hit (`RUN_JOURNAL.md:208`), synth state unchanged
- Commit: 6f610e6
- Decisions: `index_sync.py` is not in the card's Files list, but the card
  accepts notes under `wiki/notes/` and its acceptance criterion says lint
  must pass; `index_sync` would otherwise report one "not listed in
  index.md" error per imported note. The rule now skips pages with
  `type: note`, so notes stay checked for links, frontmatter and freshness.
  `import_claude_memory` sets `adapter.session_store_path = store`, because
  `derive_project_slug` resolves the project against that attribute and
  `--store` must work for any directory. `source_path` always uses the
  canonical `~/.claude/projects/<dir>/memory/<file>` form, as the card's
  template and test require, even for a custom store. Titles and
  descriptions are collapsed to one line and lose `"`; the project tag is
  sanitized to the inline-list grammar, so an odd directory name cannot
  abort the import. A concurrent run finished card 25 at 16:21 and removed
  its lock before this run locked; this run then took 26.
- Next card: 27
- Blockers: none. The pre-existing uncommitted `docs/tasks/AUTONOMOUS.md`
  change (scheduling notes) was left untouched and is not part of the card.

