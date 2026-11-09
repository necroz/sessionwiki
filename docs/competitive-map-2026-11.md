# Competitive map and improvement proposals — November 2026

**Date:** 2026-11-06  
**Status:** reviewed three times; corrected after the code review on 2026-11-06 (see section 10)  
**Scope:** tools and discussions found on Reddit and Habr, checked against the current `sessionwiki` codebase (master, v2.0.5).  
**Related:** [roadmap-2026-11.md](roadmap-2026-11.md) (the execution plan built from this map), [tasks/README.md](tasks/README.md) (implementation cards), [competitor-landscape.md](competitor-landscape.md), [feature-matrix.md](feature-matrix.md), [benchmarks.md](benchmarks.md).

---

## 1. Executive summary

`sessionwiki` is not entering an empty niche. It is an implementation of
Karpathy's **LLM Wiki** pattern applied to coding-agent transcripts. The market
around it has three layers:

1. **Compiled-memory tools** — `ai-memory`, `Basic Memory`, `agentmemory`,
   `MemPalace`. They also store knowledge as Markdown or local files and
   expose it over MCP.
2. **Memory plugins** — `claude-mem`, `kaeru`, `engram`, `supermemory`,
   `Mem0/OpenMemory`. They capture future sessions through hooks and
   summarize them with a model.
3. **Session-history search** — `deja-vu`, `cass`, `claude-self-reflect`,
   `claude-history`. They index what agents already wrote to disk and return
   it to the agent.

`sessionwiki` already sits in the strongest position for the **compiled wiki**
category: multi-agent ingestion, immutable `raw/`, generated `wiki/`, 12 MCP
tools, 16 lint rules, confidence and lifecycle metadata, a static site, a
SessionStart recall hook, autosync (a manual Claude Code `Stop` hook, an
installed ZCode `Stop` hook and scheduler, an OpenCode `session.idle` plugin), and four
synthesis backends — including `dummy` (the default, no LLM) and `agent`
(the running agent writes the pages, no extra API cost). The main gaps are
not "more memory features". They are:

- retrieval control (no filters; stale pages are not downranked). Scale is
  not a problem yet: 900 wiki pages and 65 MB of raw answer in ~0.3 s;
- proactive delivery (the MCP server sends no `instructions`; the wiki is
  only surfaced at session start, not when the agent is about to ask the
  human);
- synthesis freshness (~115 of 962 raw sessions have no source page, so
  `recall` often shows "not in the wiki yet");
- lifecycle trust (contradictions are flagged but not resolved; LLM pages and
  human notes are not separated);
- day-zero consolidation with the platform's built-in memory;
- published evidence (the recall benchmark exists but is not in the docs, and
  the k=10 runs contradict the "graph hop helps" claim).

The highest-leverage proposals are **E10 (MCP `instructions`) followed by C1
(pre-question hook)**, **C5 (import built-in auto memory)**, **D1 (turn the
`dummy` backend into an extractive one)**, **A3 (filters)** and **E1+E4
(publish the full benchmark and update the competitor landscape)**. A1 (FTS
index) waits for a measured trigger.

---

## 2. Method and verified current state

### 2.1 What was reviewed

- Reddit threads in `r/ClaudeCode`, `r/ClaudeAI`, `r/AI_Agents` about
  `claude-mem`, memory plugins, CLAUDE.md workflows and database-vs-Markdown
  debates.
- Habr articles about Claude Code auto memory, shared project memory, Memory
  MCP servers, `kaeru`, LLM Wiki and its critique.
- GitHub repositories and docs for the tools listed in section 3.
- The current repository: `sessionwiki/`, `plugin/`, `tests/`, `docs/`,
  `.metrics/`.

### 2.2 Verified current state

| Capability | State | Evidence |
|---|---|---|
| Version | `2.0.5` | `pyproject.toml`, `CHANGELOG.md` |
| Adapters | 10: 4 core + 6 contrib | `sessionwiki/adapters/__init__.py` |
| Core adapters | `claude_code`, `codex_cli`, `opencode`, `zcode` | `sessionwiki/adapters/` |
| Contrib adapters | `chatgpt`, `copilot_chat`, `copilot_cli`, `cursor`, `gemini_cli`, `obsidian` | `sessionwiki/adapters/contrib/` |
| MCP tools | 12 | `sessionwiki/mcp/server.py` `TOOLS` |
| Lint rules | 16 rule modules | `sessionwiki/lint/rules/` |
| Confidence | 4-factor score + content-type decay | `sessionwiki/confidence.py` |
| Lifecycle | draft → reviewed → verified → stale → archived | `sessionwiki/lifecycle.py` |
| Candidate review | `wiki/candidates/` + promote/merge/discard | `sessionwiki/candidates.py` |
| Folder context | `_context.md` discovery + lint | `sessionwiki/context_md.py` |
| Retrieval | BM25-style IDF + recency + one graph hop; no embeddings, no FTS | `sessionwiki/mcp/server.py` |
| Recall benchmark | 24 queries: exact / paraphrase / relational | `scripts/eval_recall.py`, `.metrics/recall-*.json` |
| SessionStart hook | `sessionwiki recall --format hook` | `plugin/hooks/hooks.json` |
| Autosync hooks | Claude Code `Stop` hook (manual `settings.json` snippet in README); ZCode `Stop` hook + scheduler (`zcode install`); OpenCode `session.idle` plugin; file lock and atomic state | `README.md`, `sessionwiki/zcode/install.py`, `sessionwiki/opencode/install.py`, `sessionwiki/lock.py` |
| Synthesis backends | `dummy` (default, no LLM, metadata-only page), `ollama`, `openai` (any OpenAI-compatible server), `agent` (pending prompts for the running agent, no API key) | `sessionwiki/synth/pipeline.py` `resolve_backend`, `synth/agent_delegate.py` |
| No-LLM commands | `synthesize --coalesce-only`, `--backfill-only` | `sessionwiki/cli.py` |
| Large-session chunking | Digests + reduce, shipped in v2.0.5 | `sessionwiki/synth/chunking.py`, `synth/prompts/chunk_digest.md` |
| MCP server `instructions` | not sent; `initialize` returns only `serverInfo` and `capabilities` | `sessionwiki/mcp/server.py` `handle_initialize` |
| MCP tool descriptions | 5238 characters in total; longest is `wiki_query` (733) | `sessionwiki/mcp/server.py` `TOOLS` |
| Scan budget | 256 MiB per `wiki_query` call; beyond it the result says "some pages were not searched" | `_MCP_SCAN_AGGREGATE_BYTES` |
| Corpus and latency (this repo) | 901 wiki pages (4.6 MB), 962 raw sessions (65 MB); `wiki_query` ≈ 0.27 s | measured 2026-11-06 |
| Synthesis backlog (this repo) | ~115 raw sessions without a source page; 12 source pages still carry a placeholder | `.llmwiki-synth-state.json`, `wiki/sources/` |
| Runtime dependencies | `markdown>=3.9` (not stdlib-only) | `pyproject.toml` |
| CI platforms | Ubuntu only | `.github/workflows/ci.yml` |

### 2.3 Measured retrieval quality

From `.metrics/recall-{base,graph,prf1,prf2}-{k5,k10}.json` (24 queries, 8 per
kind). Each cell is recall / hit. This is a preliminary measurement: the set is
small, has no confidence intervals, and one query moves a per-kind number by
0.125.

| k | Config | exact | paraphrase | relational | **overall** |
|---|---|---:|---:|---:|---:|
| 5 | base | 0.875 / 0.875 | 0.375 / 0.625 | 0.417 / 0.625 | 0.556 / 0.708 |
| 5 | graph | 0.875 / 0.875 | **0.542** / 0.625 | 0.490 / 0.625 | **0.635** / 0.708 |
| 5 | prf1 | 0.875 / 0.875 | 0.542 / 0.625 | 0.490 / 0.625 | 0.635 / 0.708 |
| 5 | prf2 | 0.875 / 0.875 | 0.333 / 0.500 | **0.521** / 0.750 | 0.576 / 0.708 |
| 10 | base | **1.000** / 1.000 | 0.708 / 0.875 | 0.521 / 0.625 | 0.743 / 0.833 |
| 10 | graph | 0.875 / 0.875 | 0.708 / 0.875 | 0.594 / 0.750 | 0.726 / 0.833 |
| 10 | prf1 | 0.875 / 0.875 | 0.708 / 0.875 | 0.594 / 0.750 | 0.726 / 0.833 |
| 10 | prf2 | **1.000** / 1.000 | 0.708 / 0.875 | **0.625** / 0.750 | **0.778** / **0.875** |

What the numbers say:

- At k=5 the graph hop helps (overall 0.556 → 0.635), mostly on paraphrases.
- At k=10 the graph hop is **worse** than the baseline (0.743 → 0.726): it
  pushes one exact match out of the top 10. The "graph hop improves recall"
  claim holds only at k=5.
- `prf2` is the best configuration at k=10 and the worst on paraphrases at
  k=5. No configuration wins at both depths.
- `prf1` gives the same numbers as `graph`. The parameters of the `prf1` and
  `prf2` runs are not recorded in the repository; E1 must record them before
  anything is published.
- Paraphrase recall at k=5 is still the weak spot. This is the argument for
  optional embeddings (A2), not for replacing the lexical index.

Treat all of this as a direction, not a benchmark claim. E1 covers recording
the configurations and expanding the set before publishing.

### 2.4 Gaps found during the audit

- `wiki_query` has no `project`, `agent`, `model`, `date` or `type` filter.
- `wiki_query` cannot save an answer back to `wiki/syntheses/`.
- `contradiction_detection` and `claim_verification` are structural checks,
  not semantic resolution.
- `recall` lists recent sessions but does not say "where we stopped / what is
  open". For sessions without a source page it shows only "not in the wiki
  yet", and ~115 sessions in this repository are in that state.
- Nothing reports the synthesis backlog: `doctor` checks the install only,
  and pending `agent` placeholders are visible only through
  `synthesize --list-pending`.
- The Claude Code plugin only registers `SessionStart`; there is no
  pre-question or pre-compaction hook. Autosync already exists (a manual
  Claude Code `Stop` hook, the ZCode `Stop` hook and scheduler, the OpenCode
  `session.idle` plugin), so the hook infrastructure (lock, wrapper,
  idempotent install) is there and C1/C3 should reuse it.
- The MCP server sends no `instructions` in `initialize`. This is the
  cheapest place for an imperative "check the wiki before asking the user"
  rule, and it is not used.
- The synthesis pipeline overwrites an existing source page without checking
  who wrote it.
- `CLAUDE.md` / `AGENTS.md` are not generated from the wiki.
- The built-in Claude Code / Codex memory is not imported.
- No `origin: human` distinction; lint cannot protect human-authored pages.
- No `last_accessed` / `access_count`; confidence has no reinforcement signal.
- `sessionwiki query` uses the optional graphify engine, while the MCP
  `wiki_query` uses the ranked lexical search. The CLI and MCP answer the same
  question differently.
- `docs/competitor-landscape.md` is stale: it still compares against mem0,
  Rewind and Pieces, mentions 6 agents and a PDF adapter.
- README claims 8 sources; the code has 10 adapters. The README list groups
  Copilot Chat and Copilot CLI and omits ChatGPT. The docs should be aligned.
- `docs/competitor-landscape.md` says "Python 3.9+ stdlib only"; the package
  depends on `markdown>=3.9`.
- `docs/roadmap.md` is dated 2026-04-08 and plans v0.1–v0.3. With
  `docs/public-roadmap.md` and this map there are three roadmap documents.
  [roadmap-2026-11.md](roadmap-2026-11.md) replaces the execution part.

---

## 3. Tools

Status legend: ✅ exists, 🟡 partial, ❌ missing.

| # | Tool | What to take | Status | Proposals |
|---|---|---|---|---|
| 1 | [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | The wiki is a compounding artifact; good query answers must be filed back | three layers, index/log, ingest/query/lint ✅; save-back ❌ | D4 |
| 2 | [LLM Wiki v2](https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2) | Supersession, quality score, forgetting, consolidation tiers, typed graph, hybrid search, event-driven hooks | confidence/lifecycle/decay/candidates 🟡; supersession, quality, typed graph, hybrid ❌ | B1, B2, B4, B6, A2, A4, D5 |
| 3 | [Astro-Han/karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki) | One-skill distribution, citations, lint | MCP skill ✅; wording is optional ("may") 🟡 | C1, A5 |
| 4 | [wikiagent](https://github.com/lileilei2023/wikiagent) | Incremental entity/concept extraction during ingest | prompt asks for `[[links]]`, pipeline does not create pages 🟡 | D2 |
| 5 | [ai-memory](https://github.com/akitaonrails/ai-memory) | Git-backed Markdown wiki as source of truth; cross-agent handoff; zero-LLM default | multi-agent and raw/wiki ✅; zero-LLM default 🟡 (`dummy` exists, but its pages hold metadata only); handoff, git mode ❌ | D1, C2, C7 |
| 6 | [Basic Memory](https://github.com/basicmachines-co/basic-memory) | Session-start briefings, pre-compaction checkpoints, `/remember`, progressive tool discovery | `recall` and MCP annotations 🟡; checkpoint and remember ❌ | C3, C4, C2 |
| 7 | [agentmemory](https://github.com/rohitg00/agentmemory) | Keyless BM25 default, import of old sessions, viewer, decay | BM25, import of old sessions and dashboard ✅; useful no-LLM pages 🟡; access stats ❌ | A4, D1 |
| 8 | [MemPalace](https://github.com/mempalace/mempalace) | Verbatim local storage, local embeddings, 47 MCP tools (claimed) | local-first and MCP 🟡; embeddings ❌ | A2, E1 |
| 9 | [claude-mem](https://github.com/thedotmack/claude-mem) | Hooks, structured observations, model summaries, progressive disclosure | hooks and synthesis 🟡; observations and pre-question hook ❌ | D3, C1, E2 |
| 10 | [kaeru (Habr)](https://habr.com/ru/articles/1102588/) | Memory layers, weighted links, reasoning chains, hooks; behavior lessons | layers and candidates 🟡; reminders, debt wording, instruction budget ❌ | C1, B5, E3, C3 |
| 11 | [agent-memory-mcp](https://github.com/ipiton/agent-memory-mcp) | Four memory types, importance, context filter, access stats, embedding fallback | episodic/semantic 🟡; procedural, filters, access stats ❌ | B5, A3, A4 |
| 12 | [supermemory](https://supermemory.ai/) | Stop-hook extraction, user profile | different shape | D3 (idea only) |
| 13 | [Mem0 / OpenMemory](https://github.com/mem0ai/mem0) | Memory API for applications | different shape | — |
| 14 | [deja-vu](https://github.com/vshulcz/deja-vu/) | Retroactive index over 44 harnesses (claimed), no LLM, published benchmark | day-zero sync, raw fallback, eval 🟡; 44 adapters and publication ❌ | E1, E8, A2 |
| 15 | [cass / coding_agent_session_search](https://github.com/Dicklesworthstone/coding_agent_session_search) | 30+ providers (claimed), robot CLI, quarantine/GC, atomic publish | quarantine and atomic state 🟡; robot JSON and GC ❌ | E7, E6, E8, A1 |
| 16 | [claude-self-reflect](https://github.com/ramakay/claude-self-reflect) | Semantic search, code graph, 15 tools, 6 hooks (claimed) | graphify 🟡; code-aware links ❌ | E9, A2 |
| 17 | [claude-session-index](https://github.com/Jeremyx000/claude-session-index) | Full-text search and analytics over sessions | scan and site metrics 🟡 | A1 |
| 18 | [claude-history](https://github.com/raine/claude-history) | Rust TUI fuzzy search | deliberately declined | — |
| 19 | [engram](https://github.com/Gentleman-Programming/engram/) | Go + SQLite FTS5, project-aware reads, candidate staging, TUI | candidates ✅; FTS ❌ | A1, E7, B5 |

Traction (GitHub API, 2026-11-06): claude-mem 113.8k, MemPalace 60.4k,
agentmemory 30.2k, ai-memory 15.3k, engram 7.8k, Cipher 4.9k, Basic Memory
4.5k, deja-vu 1.4k, cass 1.2k. Stars measure attention, not quality or
correctness.

### 3.1 Adjacent patterns not in the table

- **Cline / Roo Memory Bank** — a structured set of Markdown files
  (`projectbrief.md`, `activeContext.md`, `systemPatterns.md`, …) that the
  agent reads at the start of every task. It is the closest "compiled
  Markdown memory" pattern without an LLM synthesis pipeline, and the direct
  ancestor of C6/C7. <https://docs.cline.bot/best-practices/memory-bank>
- **Letta / MemGPT** — an agent runtime with self-editing memory blocks. It
  owns the agent loop, so it is a different shape from a wiki over
  transcripts. <https://github.com/letta-ai/letta>
- **Graphiti / Zep** — a temporal knowledge graph with validity windows and
  typed edges. Relevant to B4 (typed connections); not a wiki.
  <https://github.com/getzep/graphiti>
- **Cipher** — an open-source memory layer for coding agents over MCP,
  shared across IDEs and projects. The closest "memory API" competitor.
  <https://github.com/campfirein/cipher>

### 3.2 Closest competitors in detail

**ai-memory** is the closest architectural analogue. It uses a git-backed
Markdown wiki as the source of truth, a derived index for retrieval, lifecycle
hooks for capture and MCP for access. Two ideas are worth copying directly:
a **handoff summary** at session start ("what was in progress, what is next")
and a **zero-LLM default** that still produces useful Markdown pages. The
project should not copy the single-binary Go approach; `uvx` already covers
distribution.

**Basic Memory** is the closest product analogue. It has a Claude Code plugin
with session-start briefings, pre-compaction checkpoints, `/remember` and
`/status`. Its progressive tool discovery with behavior hints is already
matched by the MCP annotations in `sessionwiki/mcp/server.py`. The missing
pieces are the **checkpoint** and the **explicit remember** path.

**claude-mem** is one of the most popular plugins (113.8k stars on GitHub,
2026-11-06) and the best source of failure modes: token cost, Windows/macOS
breakage, closed issue submission, and no day-zero import in early versions. Its **observation** model (capture tool
use, summarize with a model, inject the relevant subset) is better than
per-session summaries for "what did we try and why". The project should add
structured observations (D3) but keep the no-LLM path (D1) so it does not
inherit the cost problem. The project already has a stronger answer to the
cost objection than claude-mem: the `agent` backend lets the running Claude
Code or Codex session write the pages, so a subscription user pays no extra
API cost. The docs and the competitor landscape should lead with it.

**deja-vu** is the best source of positioning language. Its comparison table
splits the market into **retroactive indexing** (read transcripts already on
disk) and **forward capture** (record from install on). `sessionwiki` is
retroactive *and* compiles a wiki, which is a stronger claim than either
category. Its published benchmark also sets the bar for E1.

**LLM Wiki v2** is the best roadmap document. Many of its ideas are already
implemented (confidence, lifecycle, decay, candidates). The missing ones —
supersession, quality scoring, typed edges, forgetting in ranking, access
reinforcement — are the natural next layer of the wiki, not new infrastructure.

### 3.3 Surveyed, not proposed

- **CCHV** — viewer with token analytics; the static site already covers this.
- **Mantra** — session replay with redaction; out of scope.
- **Shelf** — workspace manager for Claude Code / Codex; different job.
- **Agent Sessions** — Mac app to search and resume sessions; different job.

The dev.to comparison of four history browsers is the source for CCHV and
Mantra:
<https://dev.to/gonewx/i-tested-4-tools-for-browsing-claude-code-session-history-17ie>

---

## 4. Articles and threads

| # | Source | What to take | Status | Proposals |
|---|---|---|---|---|
| 1 | [Habr: Claude Code auto memory](https://habr.com/ru/news/1004278/) | `MEMORY.md` + topic files; first 200 lines auto-loaded; `~/.claude/projects/<project>/memory/` | built-in memory is not imported ❌ | C5 |
| 2 | [Habr: shared project memory for Claude Code and Codex](https://habr.com/ru/articles/1091422/) | Memory next to code, `.agents/memory/MEMORY.md`, `autoMemoryEnabled: false`, migration skill | wiki is gitignored by default 🟡 | C6, C7, C8 |
| 3 | [Habr: Memory MCP Server architecture](https://habr.com/ru/articles/1006756/) | Four memory types, importance weighting, context filter, embedding fallback | partial | A3, A4, B5 |
| 4 | [Habr: 13k agent logs (kaeru)](https://habr.com/ru/articles/1102588/) | "You may read" ignored 0/7; "link this" executed 751 times; 80% of questions to the human without a memory read; MCP instructions truncated at 2048 chars | `recall` uses optional wording 🟡; no instruction budget ❌ | C1, E3, B5 |
| 5 | [Habr: why not to adopt LLM Wiki for personal notes](https://habr.com/ru/articles/1025220/) | Separate instrumental knowledge from reflective writing; writing is thinking | no `origin` split ❌ | B3 |
| 6 | [Habr: second brain and LLM Wiki guide](https://habr.com/ru/articles/1031970/) | Index works up to ~100–200 pages; beyond that, hybrid search; complexity moves into the agent and schema | index/scan; no FTS/hybrid ❌ | A1, A2, E4 |
| 7 | [Habr: Claude Code hooks, MCP and plugins guide](https://habr.com/ru/articles/987094/) | Hooks and MCP as the integration surface | hooks exist 🟡 | C1, C3 |
| 8 | [Reddit: claude-mem #1 trending](https://www.reddit.com/r/ClaudeCode/comments/1pjqnnk/claudemem_1_trending_on_github_today/) | Token cost, Windows install errors, demand for prior-session import | `--estimate` ✅; budget and Windows CI ❌ | E2, E5, D1 |
| 9 | [Reddit: claude-mem 45k stars](https://www.reddit.com/r/ClaudeCode/comments/1scz5kk/claudemem_hit_45000_stars_on_github_today_and_it/) | claude-mem had 45k stars at the time of the thread; the current count is 113.8k (GitHub API, 2026-11-06) | — | E1, E4 |
| 10 | [Reddit: need an alternative to claude-mem](https://www.reddit.com/r/ClaudeAI/comments/1srdpn8/need_an_alternative_to_thedotmackclaudemem/) | Broke on Windows and macOS; recommendations: CLAUDE.md summaries, vector + CLAUDE.md hybrid, engram | no digest or handoff | C2, C6, D1 |
| 11 | [Reddit: nothing beats a database for agent memory](https://www.reddit.com/r/ClaudeCode/comments/1wwzw33/nothing_beats_a_database_for_agent_memory/) | Database vs Markdown debate; speed and token cost | Markdown only | A1, A6 |
| 12 | [Reddit: useful memory without overdoing it](https://www.reddit.com/r/ClaudeAI/comments/1tyszhi/how_are_people_giving_claude_useful_memory/) | Context bloat; hybrid retrieval | no token budget | A6, E2 |
| 13 | [Reddit: rebuilt claude-mem 600x cheaper](https://www.reddit.com/r/ClaudeAI/comments/1r3xhr0/i_rebuilt_claudemem_from_scratch_600x_cheaper/) | Cost is the main objection | estimate, cache, chunking ✅ | E2 |
| 14 | [Reddit: Claude Code across multiple PCs](https://www.reddit.com/r/ClaudeCode/comments/1m7cb64/) | Sync via CLAUDE.md summaries | no repo digest | C6, C7 |
| 15 | [Reddit: claude-mem vs the new memory tool](https://www.reddit.com/r/ClaudeAI/comments/1oegbwo/how_is_claudemem_different_from_claudes_new_memory_tool/) | Built-in memory vs plugin | no auto-memory import | C5, E4 |
| 16 | [Reddit: tested 3 memory tools](https://www.reddit.com/r/AI_Agents/comments/1wfa2na/i_tested_3_memory_tools_for_my_agents_supermemory/) | Local vs hosted positioning | local-first ✅ | E4 |

### 4.1 Lessons from the discussions

- **The baseline is now built-in.** Claude Code writes `MEMORY.md` and topic
  files by default. A plugin that only "remembers" is competing with a free
  feature. `sessionwiki` must be the durable, cross-agent, auditable layer on
  top of it.
- **Cost is the top objection to claude-mem.** Several users disabled it
  because it used a model on every session. The answer is a useful no-LLM
  default (D1, built on the existing `dummy` backend), the existing `agent`
  backend (no extra API cost) and a visible cost estimate and cap for the
  paid backends (E2) — not a cheaper model.
- **Fragility kills trust.** Windows/macOS breakage was enough to make users
  look for alternatives. Hooks and installers need cross-platform CI.
- **Markdown vs database is a false dichotomy.** The winning pattern in the
  threads is Markdown as the source of truth plus an index for speed. That is
  exactly A1.
- **"You may read" is ignored.** kaeru measured 0/7. The wording in `recall`,
  the skill and the MCP server `instructions` (E10) should be imperative:
  "before answering, check X". `recall` already ends with an imperative line
  ("Search earlier work with the wiki_query tool"), but it does not say
  *when* — before asking the user.

---

## 5. Proposal map

Priority: **P0** now, **P1** next cycle, **P2** later.  
Effort: **S** up to a day, **M** several days, **L** a week or more.

### A. Retrieval and scale

| ID | Proposal | Source | Pri | Effort | Where |
|---|---|---|---|---|---|
| A1 | **SQLite FTS5 index** for `wiki_query`: `sessionwiki index` builds `.sessionwiki/index.db`; MCP uses it when present, falls back to scanning. Gives speed at large corpora, phrase and prefix search. FTS5 ships with stdlib `sqlite3` but is not compiled into every Python build; fall back to scanning when it is unavailable. **Trigger:** start when `wiki/` + `raw/` exceed ~200 MB or `wiki_query` takes more than 1 s; today it is 70 MB and 0.27 s | deja-vu, cass, engram, Habr 1031970 | P2 | M | `sessionwiki/mcp/server.py`, new `sessionwiki/search_index.py` |
| A2 | **Optional embeddings + hybrid RRF**: BM25 + vector + graph. Providers `off` (default), `ollama`, `openai`. Keep the stdlib-only default | deja-vu, MemPalace, LLM Wiki v2 | P1 | L | new `sessionwiki/embeddings.py`, `mcp/server.py` |
| A3 | **Filters in `wiki_query`**: `project`, `type`, `tag`, `date_from`, `date_to`. Pages have no `agent` key (the agent is the first tag) and `model` is often empty, so `tag` replaces both | agent-memory-mcp, cass | P0 | S | `mcp/server.py` `TOOLS` and `tool_wiki_query` |
| A4 | **Access stats**: write `last_accessed` and `access_count` on `wiki_read_page` / `wiki_query`; use them in ranking and confidence | agent-memory-mcp, agentmemory | P1 | M | `mcp/server.py`, `confidence.py` |
| A5 | **`path:line` anchors** in `wiki_query` and `wiki_read_page` results | deja-vu provenance, Astro-Han | P1 | S | `mcp/server.py` |
| A6 | **Progressive disclosure**: `detail=snippet|page|raw`, `max_chars`, `max_tokens` | claude-mem, cass robot mode | P1 | S | `mcp/server.py` |

### B. Lifecycle and trust

| ID | Proposal | Source | Pri | Effort | Where |
|---|---|---|---|---|---|
| B1 | **Semantic contradiction resolution**: an LLM lint rule proposes which claim wins (recency, source count, authority), writes `supersedes:` / `superseded_by:`, moves the old page to `stale` | LLM Wiki v2, Karpathy | P1 | M | `lint/rules/contradiction_detection.py` |
| B2 | **Quality score** for synthesized pages: `quality:` in frontmatter, a second-pass self-evaluation, threshold to candidate/rewrite | LLM Wiki v2 | P1 | M | `synth/pipeline.py`, `confidence.py` |
| B3 | **`origin: human|llm`** and `wiki/notes/` for pages the LLM must never rewrite; the synthesis pipeline skips pages with `origin: human` (today it overwrites existing source pages without a check) | Habr 1025220 | P0 | S | `synth/pipeline.py` write sites, docs |
| B4 | **Typed connections**: parse relation verbs in `## Connections` (`uses`, `caused`, `supersedes`, `contradicts`) into graph edge types | LLM Wiki v2 | P2 | M | `graph.py`, `mcp/server.py` |
| B5 | **`wiki/procedures/` + reminders**: runbooks and commands extracted from sessions; `remind_after:` surfaced in `recall` | kaeru, agent-memory-mcp | P1 | M | new `wiki/procedures/`, `cli.py` `recall`, `lint/rules/` |
| B6 | **Downrank `stale` / `archived`** in `wiki_query`, not only recency | LLM Wiki v2, `lifecycle.py` | P1 | S | `mcp/server.py` |

### C. Agent integration

| ID | Proposal | Source | Pri | Effort | Where |
|---|---|---|---|---|---|
| C1 | **Pre-question hook**: on `UserPromptSubmit`, run the ranked wiki search for the prompt and inject "relevant past work" only above a score threshold. Opt-in, hard timeout, no output when nothing matches. Ship E10 first: it is the same idea without per-prompt cost. Measure hook latency (`uvx` start-up) before enabling it by default | kaeru (80% questions without memory) | P1 | M | `plugin/hooks/hooks.json`, `cli.py` |
| C2 | **Handoff summary in `recall`**: not a list of sessions, but "what we did / where we stopped / what is open" from the latest session | ai-memory, Basic Memory | P0 | S | `cli.py` `_recent_sessions` / `cmd_recall` |
| C3 | **Pre-compaction checkpoint**: `sessionwiki checkpoint` + `PreCompact` hook; page in `wiki/checkpoints/` | Basic Memory, kaeru | P1 | M | `cli.py`, `plugin/hooks/hooks.json` |
| C4 | **`sessionwiki remember "<fact>"`**; writes a candidate, not directly into the trusted wiki. The MCP side moved to E12: an agent writes the candidate with `wiki_write_page` | Basic Memory `/remember` | P1 | S | `cli.py`, `candidates.py` |
| C5 | **Import built-in auto memory**: mirror `~/.claude/projects/*/memory/*.md` into `wiki/notes/claude-memory/<project>/` with `origin: human`. Not through `raw/`: memory files change in place, and `raw/` is immutable. Depends on B3 | Habr 1004278, 1091422 | P0 | M | new `sessionwiki/memory_import.py`, `cli.py` |
| C6 | **`CLAUDE.md` / `AGENTS.md` digest**: marker-delimited "recent decisions" block, max N lines, opt-in | Reddit, Habr 1091422 | P1 | S | `exporters.py`, `cmd_export` |
| C7 | **Repo-memory export**: `.agents/memory/MEMORY.md` + topics, curated and redacted, opt-in | Habr 1091422, ai-memory | P2 | M | new `sessionwiki/repo_memory.py` |
| C8 | **Branch/worktree filters** in `recall` and project pages; use `gitBranch` from frontmatter | Reddit worktrees | P2 | S | `cli.py` `recall`, `project_topics.py` |

### D. Synthesis and content

| ID | Proposal | Source | Pri | Effort | Where |
|---|---|---|---|---|---|
| D1 | **Extractive no-LLM backend**: the default `dummy` backend already runs without a model but writes metadata only. Add an `extractive` backend (and later make it the default): first request, decision phrases, files and commands, errors and fixes, last assistant message. The wiki becomes useful without a model | ai-memory, agentmemory, deja-vu | P0 | M | `synth/base.py`, new `synth/extractive.py`, `resolve_backend` |
| D2 | **Automatic entity/concept pages** from recurring `[[links]]`: frequency threshold → `wiki/candidates/` | Karpathy, wikiagent | P1 | M | `synth/pipeline.py`, `candidates.py` |
| D3 | **Structured observations**: `## Decisions`, `## Open Questions`, `## Errors & Fixes` in source pages plus a separate index | claude-mem, kaeru | P1 | M | `synth/prompts/source_page.md`, `synth/pipeline.py` |
| D4 | **Save-back answers**: MCP `wiki_save_synthesis` / `sessionwiki query --save`, with a quality gate | Karpathy query | P1 | S | `mcp/server.py`, `cli.py` |
| D5 | **Theme/decision pages**: cluster sessions into topics, not only per-session | LLM Wiki v2 tiers | P2 | M | `synth/pipeline.py` |

### E. Distribution, trust and documentation

| ID | Proposal | Source | Pri | Effort | Where |
|---|---|---|---|---|---|
| E1 | **Publish the recall benchmark**: methodology + all configurations at k=5 and k=10, including the k=10 result where the graph hop loses; record what `prf1`/`prf2` mean; expand to ≥100 queries or report confidence intervals before making claims in the README. The query set names real sessions and stays out of git | deja-vu, MemPalace controversy | P0 | S | `docs/benchmarks.md`, `README.md` |
| E2 | **Cost cap for paid backends**: `synthesize --max-sessions N` and a printed per-run estimate for `ollama`/`openai`. `dummy` and `agent` cost nothing and need no cap | Reddit claude-mem | P1 | S | `synth/pipeline.py`, `cli.py` |
| E3 | **Description length tests**: each tool description ≤ 1024 characters, server `instructions` ≤ 2048 characters. A total-length cap would fail today (5238 characters) and would force dropping tools | kaeru (2048-char truncation) | P0 | S | `tests/`, `mcp/server.py` |
| E4 | **Rewrite `docs/competitor-landscape.md`**: it still lists mem0/Rewind/Pieces, 6 agents and PDF. Add deja-vu, claude-mem, ai-memory, Basic Memory, agentmemory, MemPalace, cass and the axes "retroactive vs forward", "compiled wiki vs memory API" | deja-vu compare, all | P0 | S | `docs/competitor-landscape.md` |
| E5 | **Windows/macOS CI** for hooks, install and sync | Reddit claude-mem | P0 | M | `.github/workflows/ci.yml` |
| E6 | **`doctor --gc`**: prune orphan raw/manifest entries, stale candidates, quarantine | cass | P2 | S | `sessionwiki/doctor.py` |
| E7 | **`--json` for `recall` and `query`** (`lint` already has it) | cass robot mode | P1 | S | `cli.py` |
| E8 | **Expand adapters**: first one generic JSONL/Markdown adapter with a mapping config; dedicated adapters (Aider, Cline/Roo, Windsurf, Amp, Continue, Goose, Kiro, Qwen) only on user demand. Each adapter is permanent maintenance | deja-vu 44, cass 30+ | P2 | L | `adapters/contrib/` |
| E9 | **Code-aware links**: connect pages to repository files/symbols, `wiki_code_query` | claude-self-reflect | P2 | L | `graphify_bridge.py`, new `code_links.py` |
| E10 | **MCP server `instructions`**: return a ≤ 2048-character `instructions` string from `initialize`: "Before you ask the user about earlier decisions or fixes, call `wiki_query`." Zero runtime cost, works in every MCP client | kaeru, this review | P0 | S | `mcp/server.py` `handle_initialize` |
| E11 | **Synthesis backlog report**: `doctor` (and `--json`) shows raw sessions without a source page and pages with the `agent` placeholder | this review | P0 | S | `doctor.py` |
| E12 | **Guarded MCP write tools**: `wiki_write_page`, `wiki_update_frontmatter`, `wiki_archive_page`. Preview by default, write with `confirm=true`; only `wiki/`, never `raw/`, system pages or `origin: human` pages; "delete" sets `lifecycle: archived`. Depends on B3 | Glama completeness review ("essentially read-only") | P1 | M | `mcp/server.py`, `_frontmatter.py` |

---

## 6. Delivery phases

The waves from the first draft are replaced by four phases in
[roadmap-2026-11.md](roadmap-2026-11.md). The order changed after the code
review:

- **Phase 0 — fixes and honesty (~1 week):** E3, E10, docs facts, E4, E1,
  `sessionwiki query` on the MCP engine with `--json`/`--limit` (E7), E11.
- **Phase 1 — retrieval control and trust (2–3 weeks):** A3, B6, B3, C2 with
  a fallback to the raw transcript, E2, E12 (after B3).
- **Phase 2 — proactive delivery and import (3–4 weeks):** C1 (opt-in), C5
  (after B3), D1, C4, E5.
- **Phase 3 — retrieval quality (1–2 months):** decide PRF vs graph hop on an
  expanded eval, A2, A5/A6, D3, D4, B1.
- **Later, on a trigger:** A1, B4, C7/C8, D5, E6, E8 (generic adapter first), E9.

Phases 0–2 are split into implementation cards in [tasks/](tasks/README.md).

---

## 7. What not to do

- **TUI / desktop / replay** (claude-history, CCHV, Mantra, Shelf). Already
  declined; the project's strength is the compiled wiki and the site, not a
  session browser.
- **Cloud sync** (Basic Memory Cloud, hosted memory APIs such as supermemory).
  Breaks local-first and the no-telemetry positioning.
- **A required vector database**. Only an optional provider; otherwise the
  minimal-dependency rule is lost.
- **Chasing benchmark claims** (MemPalace's "100% LongMemEval"). Publish a
  reproducible measurement instead of comparing incomparable numbers.
- **Auto-generating personal reflective notes**. The Habr critique is valid;
  add an `origin: human` namespace instead of delegating all writing.
- **Copying claude-mem one-to-one**. Its pain points (tokens, Windows,
  fragility) are the reason people look for alternatives.

---

## 8. Top five if time is short

1. **E10 → C1** MCP `instructions`, then the pre-question hook. kaeru's logs
   show the biggest gap: the agent asks the human without reading memory
   first. E10 fixes most of it for free; C1 adds the per-prompt push.
2. **C5** import built-in auto memory. Makes `sessionwiki` a superset of the
   platform's free feature instead of a competitor.
3. **D1** extractive backend. Turns the existing no-LLM `dummy` path into a
   useful one and, with the `agent` backend, answers the cost objection.
4. **A3 + C2** filters and handoff. "What happened in project X" and "where
   did we stop" are the two questions agents ask most.
5. **E1 + E4** full benchmark and honest competitor map. Cheap, and it raises
   trust immediately — as long as the k=10 result is published too.

---

## 9. Sources

### Primary sources

- Anthropic, **Claude Code memory** documentation:
  <https://code.claude.com/docs/en/memory>
- Andrej Karpathy, **LLM Wiki** (gist, 2026-04-04):
  <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- rohitg00, **LLM Wiki v2**:
  <https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2>
- **Astro-Han/karpathy-llm-wiki**:
  <https://github.com/Astro-Han/karpathy-llm-wiki>
- **lileilei2023/wikiagent**:
  <https://github.com/lileilei2023/wikiagent>
- **akitaonrails/ai-memory**:
  <https://github.com/akitaonrails/ai-memory>, <https://aimemory.sh/>
- **basicmachines-co/basic-memory**:
  <https://github.com/basicmachines-co/basic-memory>, <https://www.basicmemory.com/>
- **rohitg00/agentmemory**:
  <https://github.com/rohitg00/agentmemory>, <https://www.agent-memory.dev/>
- **MemPalace/mempalace**:
  <https://github.com/mempalace/mempalace>
- **thedotmack/claude-mem**:
  <https://github.com/thedotmack/claude-mem>
- **ipiton/agent-memory-mcp**:
  <https://github.com/ipiton/agent-memory-mcp>
- **supermemory**: <https://supermemory.ai/>
- **mem0ai/mem0**: <https://github.com/mem0ai/mem0>
- **vshulcz/deja-vu**: <https://github.com/vshulcz/deja-vu/>; comparison:
  <https://vshulcz.github.io/deja-vu/guide/compare.html>
- **Dicklesworthstone/coding_agent_session_search (cass)**:
  <https://github.com/Dicklesworthstone/coding_agent_session_search>;
  project page: <https://www.jeffreyemanuel.com/projects/cass>
- **ramakay/claude-self-reflect**:
  <https://github.com/ramakay/claude-self-reflect>
- **Jeremyx000/claude-session-index**:
  <https://github.com/Jeremyx000/claude-session-index>
- **raine/claude-history**:
  <https://github.com/raine/claude-history>
- **Harukaon/shelf**: <https://github.com/Harukaon/shelf>
- **Agent Sessions**: <https://jazzyalex.github.io/agent-sessions/>
- **Gentleman-Programming/engram**:
  <https://github.com/Gentleman-Programming/engram/>
- **Cline Memory Bank**:
  <https://docs.cline.bot/best-practices/memory-bank>
- **Letta / MemGPT**: <https://github.com/letta-ai/letta>
- **Graphiti / Zep**: <https://github.com/getzep/graphiti>
- **Cipher**: <https://github.com/campfirein/cipher>
- Dev.to comparison of four history browsers:
  <https://dev.to/gonewx/i-tested-4-tools-for-browsing-claude-code-session-history-17ie>

### Habr

- **Claude Code теперь автоматически запоминает контекст между сессиями**
  (2026-02-26): <https://habr.com/ru/news/1004278/>
- **Общая память проекта для Claude Code и Codex** (2026-10-07):
  <https://habr.com/ru/articles/1091422/>
- **Как я спроектировал Memory MCP Server для AI-агентов** (2026-03-05):
  <https://habr.com/ru/articles/1006756/>
- **Мы прочитали 13 тысяч файлов логов своих агентов** (2026-11-02):
  <https://habr.com/ru/articles/1102588/>
- **Почему LLM Wiki Карпатого не стоит внедрять для личной базы знаний**
  (2026-04-19): <https://habr.com/ru/articles/1025220/>
- **Второй мозг и LLM-Wiki: теория и практический гайд** (2026-05-06):
  <https://habr.com/ru/articles/1031970/>
- **Claude Code: практический гайд по хукам, MCP и плагинам**:
  <https://habr.com/ru/articles/987094/>

### Reddit

- **Claude-Mem #1 Trending on GitHub today**:
  <https://www.reddit.com/r/ClaudeCode/comments/1pjqnnk/claudemem_1_trending_on_github_today/>
- **Claude-Mem hit 45,000 stars**:
  <https://www.reddit.com/r/ClaudeCode/comments/1scz5kk/claudemem_hit_45000_stars_on_github_today_and_it/>
- **Need an alternative to thedotmack/claude-mem**:
  <https://www.reddit.com/r/ClaudeAI/comments/1srdpn8/need_an_alternative_to_thedotmackclaudemem/>
- **claude-mem / cmem — anyone else using it?**:
  <https://www.reddit.com/r/ClaudeCode/comments/1wkc0f0/claudemem_cmem_anyone_else_using_it/>
- **Has anyone tested claude-mem yet?**:
  <https://www.reddit.com/r/ClaudeCode/comments/1sjhw6t/has_anyone_tested_claudemem_yet/>
- **How do you deal with Claude's memory**:
  <https://www.reddit.com/r/ClaudeCode/comments/1w8yhua/how_do_you_deal_with_claudes_memory/>
- **how are people giving Claude useful memory without overdoing it?**:
  <https://www.reddit.com/r/ClaudeAI/comments/1tyszhi/how_are_people_giving_claude_useful_memory/>
- **Nothing beats a database for agent memory**:
  <https://www.reddit.com/r/ClaudeCode/comments/1wwzw33/nothing_beats_a_database_for_agent_memory/>
- **I rebuilt claude-mem from scratch — 600x cheaper**:
  <https://www.reddit.com/r/ClaudeAI/comments/1r3xhr0/i_rebuilt_claudemem_from_scratch_600x_cheaper/>
- **Anyone else using Claude Code across multiple PCs?**:
  <https://www.reddit.com/r/ClaudeCode/comments/1m7cb64/>
- **How is Claude-Mem different from Claude's New Memory Tool?**:
  <https://www.reddit.com/r/ClaudeAI/comments/1oegbwo/how_is_claudemem_different_from_claudes_new_memory_tool/>
- **I tested 3 memory tools for my agents (Supermemory, Mem0, Vilix AI)**:
  <https://www.reddit.com/r/AI_Agents/comments/1wfa2na/i_tested_3_memory_tools_for_my_agents_supermemory/>
- **Claude Code is game changer with memory plugin**:
  <https://www.reddit.com/r/ClaudeCode/comments/1o5o0f4/claude_code_is_game_changer_with_memory_plugin/>
- **Claude Code's "memory" over-generalizes**:
  <https://www.reddit.com/r/ClaudeCode/comments/1wxqu67/claude_codes_memory_overgeneralizes_and_this_is/>

### Repository evidence

- `sessionwiki/mcp/server.py` — MCP tools, ranked query, graph hop.
- `sessionwiki/lint/rules/` — 16 lint rules.
- `sessionwiki/confidence.py` — confidence formula and decay.
- `sessionwiki/lifecycle.py` — lifecycle state machine.
- `sessionwiki/candidates.py` — candidate review workflow.
- `sessionwiki/context_md.py` — folder context.
- `sessionwiki/synth/pipeline.py`, `sessionwiki/synth/prompts/source_page.md` —
  synthesis contract.
- `sessionwiki/cli.py` — commands, `recall`, `query`.
- `plugin/hooks/hooks.json` — SessionStart hook.
- `docs/competitor-landscape.md`, `docs/benchmarks.md` — existing docs.
- `.metrics/recall-*.json` — recall measurements.
- `.github/workflows/ci.yml` — Ubuntu-only CI.

### Method notes

- Reddit search without a logged-in session returns noisy results, so the
  relevant threads were opened directly and read.
- Habr search pages are client-rendered; articles were reached through search
  result links and read directly.
- Star counts are from the GitHub API on 2026-11-06. Capability counts marked
  "(claimed)" come from the project's own README and are not independently
  verified.
- The recall numbers in section 2.3 come from this repository's own
  `.metrics/recall-*.json`, not from a competitor's README.

---

## 10. Review log

- **2026-11-06 — factual review.** An independent `code-explorer` subagent
  (separate model) verified 11 claims against the code: adapter count, lint
  rule count, MCP tool count, CI platforms, `query`/graphify, `recall`
  handoff, plugin hooks, `wiki_query` filters, missing `origin`/access stats,
  synthesis scope, and the recall numbers. One issue found: C1 referenced a
  `--limit` flag that `sessionwiki query` does not have. Fixed by describing
  the post-Wave-0 command.
- **2026-11-06 — content review.** A second independent `code-explorer`
  subagent reviewed the map as a product document and raised 10 issues.
  Applied: claude-mem star count replaced with the GitHub API number;
  competitor capability counts marked "(claimed)"; the recall table marked
  preliminary; Memory Bank, Letta, Graphiti and Cipher added as adjacent
  patterns; A1 priority wording fixed; the MemPalace cloud contradiction
  removed; the MIT/cloud wording corrected; CCHV/Mantra/Shelf/Agent Sessions
  moved to an appendix; Wave 0 given a total estimate; FTS5 fallback and the
  official Anthropic memory docs cited.
- **2026-11-06 — code review.** A third pass checked the map against the
  code and the `.metrics/` files. Corrected: the `dummy` and `agent`
  synthesis backends and the existing autosync hooks were missing; E3
  targeted the total description length (5238 characters today) instead of
  per-description and `instructions` limits; section 2.3 showed only k=5 and
  hid the k=10 and `prf` runs, where the graph hop loses; A1 had no trigger
  although the current corpus answers in ~0.3 s; the synthesis backlog and
  the missing MCP `instructions` were not listed; C5 now depends on B3 and
  writes outside `raw/`; README, stdlib and roadmap drift added to 2.4.
  Added E10 and E11. Waves replaced by the phases in
  [roadmap-2026-11.md](roadmap-2026-11.md). External links were not
  re-checked in this pass.
- **2026-11-06 — write tools.** Glama scored the MCP server low on
  completeness: no tool creates, edits or deletes a page or changes tags.
  Added E12 (guarded write tools, card 30) and moved the MCP part of C4
  (`wiki_remember`) into it.
