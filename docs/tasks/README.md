# Task cards

These cards are written so a cheap model can execute one card at a time
without reading the whole repository. Each card is one branch and one PR.

- Cards 01–08: bug fixes after the synthesis/coalescing work (done).
- Cards 11–30: the [November 2026 roadmap](../roadmap-2026-11.md), built
  from the [competitive map](../competitive-map-2026-11.md). See
  [Roadmap 2026-11 cards](#roadmap-2026-11-cards) below.

## How to hand a card to a model

Use this prompt template:

```
Implement exactly one task card from docs/tasks/.
Read docs/tasks/<card>.md completely before touching code.
Read only the files listed under "Read first".
Make the smallest change that satisfies the acceptance criteria.
Run every command under "Verification".
Do not start another card.
Report: files changed, commands run, command output, anything that failed.
```

Do not give a model more than one card per run. Do not let it "clean up"
unrelated code.

The scheduled autonomous worker follows [AUTONOMOUS.md](AUTONOMOUS.md) and
records every run in [RUN_JOURNAL.md](RUN_JOURNAL.md).

## Order and dependencies

| # | Card | Priority | Size | Depends on | Status |
|---|---|---|---:|---|---|
| 01 | [Isolate synth state in tests](01-test-isolate-synth-state.md) | P0 | S | — | done |
| 02 | [Preserve manual text in project Sessions](02-project-sessions-markers.md) | P0 | M | — | done |
| 03 | [Valid frontmatter for projects index](03-projects-index-frontmatter.md) | P1 | S | — | done |
| 04 | [Force graphify overwrite after page removal](04-graphify-force-overwrite.md) | P1 | S | — | done |
| 05 | [Add graph runtime dependencies](05-graph-extra-dependencies.md) | P1 | S | — | done |
| 06 | [Make --estimate honest about the backend](06-estimate-backend-pricing.md) | P2 | S | — | done |
| 07 | [Do not retry non-retryable OpenAI errors](07-openai-retry-fallback.md) | P2 | M | — | done |
| 08 | [Make wikilink stripping configurable](08-wikilink-strip-flag.md) | P3 | S | — | done |

Optional follow-ups, not carded yet:

- **09 — Coalesce-only hook.** Done: `sessionwiki synthesize --coalesce-only`
  runs without an LLM backend, and `sessionwiki zcode autosync --coalesce`
  runs it after sync. `sessionwiki zcode install --coalesce` enables it in
  the scheduled hook/timer.
- **10 — Seed page cleanup.** Done (2026-11-09): seven demo seed pages
  (`concepts/ARC-AGI-2`, `AgenticWorkloads`, `CachePricing`,
  `MultimodalModels`, `entities/ClaudeSonnet4`, `GPT5`, `OpenAI`) moved to
  `wiki/archive/seed/` with `lifecycle: archived`. `entities/Anthropic`
  stays (real sessions link to it) and was rewritten from those sessions.
  `lint` now skips `wiki/archive/`, as its comment always said.

## Roadmap 2026-11 cards

Run them in this order. A card may start only when every card in
`Depends on` is `done`. Cards in the same phase without a dependency
between them can run in parallel branches, but cards that touch the same
function are chained on purpose (17 → 20 → 21, 13 → 18 → 23) to avoid
merge conflicts. Card 30 also edits `mcp/server.py`, but only appends to
`TOOLS` and the annotation block; rebase it on 17, 20 and 21 if they are open.

| # | Card | Phase | ID | Priority | Size | Depends on | Status |
|---|---|---|---|---|---:|---|---|
| 11 | [Guard MCP description and instructions length](11-mcp-description-limits.md) | 0 | E3 | P0 | S | — | done |
| 12 | [Send MCP server instructions](12-mcp-server-instructions.md) | 0 | E10 | P0 | S | 11 | done |
| 13 | [recall: say when to search](13-recall-when-to-search.md) | 0 | — | P0 | S | — | done |
| 14 | [Align docs with the code](14-docs-facts.md) | 0 | — | P0 | S | — | done |
| 15 | [Rewrite the competitor landscape](15-competitor-landscape-rewrite.md) | 0 | E4 | P0 | S | — | done |
| 16 | [Publish recall results](16-benchmarks-recall.md) | 0 | E1 | P0 | S | — | done |
| 17 | [query on the MCP ranking engine](17-cli-query-mcp-engine.md) | 0 | E7 | P0 | M | — | done |
| 18 | [recall --format json](18-recall-json.md) | 0 | E7 | P1 | S | 13 | done |
| 19 | [doctor reports the synthesis backlog](19-doctor-synthesis-backlog.md) | 0 | E11 | P0 | S | — | done |
| 20 | [Filters in wiki_query and query](20-wiki-query-filters.md) | 1 | A3 | P0 | M | 11, 17 | done |
| 21 | [Downrank stale and archived pages](21-downrank-stale.md) | 1 | B6 | P1 | S | 20 | todo |
| 22 | [Never overwrite origin: human pages](22-origin-human-guard.md) | 1 | B3 | P0 | S | — | todo |
| 23 | [Handoff block in recall](23-recall-handoff.md) | 1 | C2 | P0 | M | 18 | todo |
| 24 | [synthesize --max-sessions](24-synthesize-max-sessions.md) | 1 | E2 | P1 | S | — | todo |
| 30 | [Guarded MCP write tools](30-mcp-write-tools.md) | 1 | E12 | P1 | M | 11, 12, 22 | todo |
| 25 | [Extractive synthesis backend](25-extractive-backend.md) | 2 | D1 | P0 | M | — | todo |
| 26 | [import-memory for Claude Code auto memory](26-import-claude-memory.md) | 2 | C5 | P0 | M | 22 | todo |
| 27 | [remember a fact as a candidate](27-remember-command.md) | 2 | C4 | P1 | S | 22 | todo |
| 28 | [CI on macOS and Windows](28-ci-macos-windows.md) | 2 | E5 | P0 | M | — | todo |
| 29 | [Opt-in prompt recall hook](29-prompt-recall-hook.md) | 2 | C1 | P1 | M | 12, 17, 20 | todo |

Phase 3 items (ranking decision, embeddings, anchors, observations,
save-back, contradiction resolution) need a design note first. Do not give
them to a cheap model as cards until the note exists.

For roadmap cards, the branch prefix follows the card (`feat/`, `docs/`,
`test/`, `ci/`) and the commit title follows the card's PR title.

Cards that need extra care from the reviewer:

- **17** refactors `wiki_query`. The MCP text must stay byte-identical;
  check the eval numbers in the PR body.
- **22** and **26** touch what the pipeline may overwrite. Read the diff of
  every write site.
- **28** needs `gh` and a pushed branch; the model cannot verify it locally.
- **29** needs calibration and latency numbers; reject the PR without them.

## Before you start

Until card 01 is merged, running the test suite mutates the real
synthesis state. Back it up before every test run:

```bash
cp .llmwiki-synth-state.json /tmp/sessionwiki-synth-state.bak
```

After the test run:

```bash
cmp .llmwiki-synth-state.json /tmp/sessionwiki-synth-state.bak
```

`cmp` must print nothing. If it prints a difference, the test suite
touched production state; restore it:

```bash
cp /tmp/sessionwiki-synth-state.bak .llmwiki-synth-state.json
```

## Verification baseline

Run from the repository root:

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m sessionwiki lint
.venv/bin/python -m sessionwiki --version
```

Expected:

- `pytest` exits with code 0.
- `lint` reports no **new** errors. On 2026-11-09 the maintainer's local
  wiki already had 16 `index.md` errors (dead links to demo projects,
  project pages missing from the index); the number grows as new project
  pages appear. Count the errors before the card
  (`.venv/bin/python -m sessionwiki lint 2>&1 | grep -c '\[error\]'`) and
  after; the number must not grow. Do not fix wiki content inside a code
  card. Warnings are allowed.
- `--version` prints the version.

## Rules for every card

- One concern per PR. The repository enforces this in
  `.kiro/steering/contributing-rules.md`.
- Branch name: `fix/<card-slug>`, for example `fix/test-isolate-synth-state`.
- Commit title: `fix: <short description>`.
- Do not modify `raw/`. It is immutable.
- Do not modify `site/`. It is generated.
- Do not rewrite unrelated code, rename functions, or reformat files.
- Add or update a test for every code change. If a test is impractical,
  say why in the PR body.
- Update `CHANGELOG.md` under `## [Unreleased]` with one line.
- Report the exact commands you ran and their output.

## Status tracking

Update the `Status` column in the table above when a card is done:
`todo` → `in-progress` → `done`. Keep the card file as the record of
what was required.
