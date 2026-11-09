# Roadmap — November 2026

**Date:** 2026-11-06  
**Base version:** v2.0.5  
**Built from:** [competitive-map-2026-11.md](competitive-map-2026-11.md) (proposal IDs A1…E11 come from its section 5)  
**Cards:** [tasks/README.md](tasks/README.md), cards 11–30  
**Replaces:** the execution plan in [roadmap.md](roadmap.md) (2026-04-08, v0.1–v0.3 phases). That file stays as history.

---

## Principles

1. **Use what exists first.** The `dummy` and `agent` backends, the autosync
   hooks, the lock and the eval script already exist. Cheap changes that use
   them go before new infrastructure.
2. **Measure before building.** FTS (A1), embeddings (A2) and the per-prompt
   hook (C1) start only when a number says they are needed.
3. **Never overwrite a human.** Anything that imports, remembers or edits
   facts (C4, C5, E12) depends on the `origin: human` guard (B3).
4. **Publish the whole result.** Benchmarks include the configurations that
   lose.
5. **One card, one PR.** Each card fits a cheap model: one concern, listed
   files, exact acceptance criteria.

---

## Phase 0 — fixes and honesty (~1 week)

Goal: the docs say what the code does, the MCP server tells the agent when to
use it, and the backlog is visible.

| Card | ID | What | Size |
|---|---|---|---:|
| 11 | E3 | Tests for tool description and `instructions` length | S |
| 12 | E10 | MCP server `instructions` in `initialize` | S |
| 13 | — | `recall`: say *when* to search ("before you ask the user") | S |
| 14 | — | Docs facts: README sources, dependency wording, `roadmap.md` banner | S |
| 15 | E4 | Rewrite `docs/competitor-landscape.md` | S |
| 16 | E1 | Recall results in `docs/benchmarks.md` (k=5 and k=10) | S |
| 17 | E7 | `sessionwiki query` on the MCP ranking engine, `--json`, `--limit` | M |
| 18 | E7 | `recall --format json` | S |
| 19 | E11 | `doctor` reports the synthesis backlog | S |

**Exit criteria**

- `pytest` green; `lint` reports 0 errors.
- `initialize` returns `instructions`; a test guards its length.
- `sessionwiki query "<q>"` and MCP `wiki_query` return the same top pages.
- `doctor` prints the number of raw sessions without a source page.
- README, competitor landscape and benchmarks contain no claim that the code
  contradicts.

## Phase 1 — retrieval control and trust (2–3 weeks)

Goal: the agent can narrow a search, old answers sink, human pages are safe,
the agent can fix a page through MCP with the user's confirmation, and
`recall` says where the work stopped.

| Card | ID | What | Size | Depends on |
|---|---|---|---:|---|
| 20 | A3 | Filters in `wiki_query` and `query`: `project`, `type`, `tag`, `date_from`, `date_to` | M | 17 |
| 21 | B6 | Downrank `stale` and `archived` pages | S | 20 |
| 22 | B3 | `origin: human` guard in the synthesis pipeline | S | — |
| 23 | C2 | Handoff block in `recall` with a raw-transcript fallback | M | 18 |
| 24 | E2 | `synthesize --max-sessions N` for paid backends | S | — |
| 30 | E12 | Guarded MCP write tools: `wiki_write_page`, `wiki_update_frontmatter`, `wiki_archive_page` (preview by default, `confirm=true` to write) | M | 11, 12, 22 |

**Exit criteria**

- `wiki_query` with `project=` returns only that project's pages.
- A page with `origin: human` survives `synthesize --force` unchanged.
- Through MCP an agent can create a page, change its tags and archive it;
  every call without `confirm=true` writes nothing, and an `origin: human`
  page is refused.
- `recall` for a project whose newest session has no page still shows what
  that session ended with.
- Recall eval (`scripts/eval_recall.py`) at k=5 and k=10 is not worse than
  the Phase 0 numbers.

## Phase 2 — proactive delivery and import (3–4 weeks)

Goal: the wiki reaches the agent before it asks the human, and the
platform's built-in memory becomes part of the wiki.

| Card | ID | What | Size | Depends on |
|---|---|---|---:|---|
| 25 | D1 | `extractive` synthesis backend (no LLM, useful pages) | M | — |
| 26 | C5 | `sessionwiki import-memory` for Claude Code auto memory | M | 22 |
| 27 | C4 | `sessionwiki remember "<fact>"` writes a candidate (the MCP side is card 30) | S | 22 |
| 28 | E5 | CI on macOS and Windows | M | — |
| 29 | C1 | Opt-in `UserPromptSubmit` hook: `recall --prompt-hook` | M | 12, 17, 20 |

**Exit criteria**

- `synthesize` with `backend: extractive` produces pages with a real summary
  and passes `lint` without new errors.
- Claude Code memory files appear under `wiki/notes/claude-memory/` and are
  found by `wiki_query`.
- CI is green on Ubuntu, macOS and Windows (known platform skips are listed
  with a reason).
- The prompt hook adds context only above its threshold, and its median
  latency is measured and written into the card's PR.

## Phase 3 — retrieval quality (1–2 months, not carded yet)

Each item needs a short design note before cards are written.

- **Ranking decision.** Expand the recall set to ≥ 100 queries, record the
  `prf1`/`prf2` parameters, then choose graph hop, PRF or both at k=5 and
  k=10.
- **A2** optional embeddings with hybrid RRF; off by default, providers
  `ollama` and `openai`.
- **A5 / A6** `path:line` anchors and progressive disclosure (`detail`,
  `max_chars`).
- **D3** structured observations (`## Decisions`, `## Open Questions`,
  `## Errors & Fixes`) in the source-page prompt.
- **D4** save-back answers to `wiki/syntheses/` with a quality gate.
- **B1** semantic contradiction resolution with `supersedes:` /
  `superseded_by:`.

## Later — on a trigger

| ID | Start when |
|---|---|
| A1 FTS5 index | `wiki/` + `raw/` > ~200 MB, or `wiki_query` > 1 s |
| A4 access stats | Phase 3 ranking work needs a reinforcement signal |
| B2 quality score | D3 lands and pages need a rewrite threshold |
| B4 typed graph | D3 lands and relation verbs are common in `## Connections` |
| B5 procedures and reminders | users ask for runbooks in `recall` |
| C3 pre-compaction checkpoint | C1 is in use and measured |
| C6 / C7 `CLAUDE.md` digest, repo memory | C5 lands and users ask for in-repo memory |
| C8 branch filters | A3 lands and worktree users ask |
| D2 / D5 auto entity pages, theme pages | D3 lands |
| E6 `doctor --gc` | E11 shows orphans in real repositories |
| E8 generic JSONL adapter | a user asks for an unsupported agent |
| E9 code-aware links | graphify becomes a default dependency |

## Not doing

Unchanged from section 7 of the competitive map: no TUI or desktop app, no
cloud sync, no required vector database, no benchmark chasing, no
auto-generated reflective notes, no one-to-one copy of claude-mem.

---

## How to run the cards

See [tasks/README.md](tasks/README.md). One card per model run, in the
order of the table, respecting `Depends on`. Cards 11–19 can be done in any
order except 12 after 11. Card 30 runs after 11, 12 and 22; it appends to
`TOOLS` in `mcp/server.py`, so rebase it on 17, 20 and 21 if they are open.
Card 29 is last.
