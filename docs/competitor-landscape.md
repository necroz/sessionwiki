# Competitor Landscape

Every coding agent writes its work to disk: prompts, decisions, commands,
errors and fixes. The next session starts without any of it. The tools below
all attack that gap, and they differ in *when* they capture, *what* they
produce and *what* they require. This page compares the options a coding-agent
user is likely to weigh in November 2026.

## Two axes

- **Retroactive indexing** reads transcripts that are already on disk.
  **Forward capture** records from install on.
- **Compiled wiki** produces pages a human can read and audit. **Memory API**
  returns facts to an agent on demand.

The split comes from deja-vu's comparison. `sessionwiki` is retroactive *and*
compiles a wiki, which is a stronger claim than either category alone: it can
answer "what did we decide last month" on day zero, and the answer is a page
you can open, inspect and edit.

## Comparison

| | sessionwiki | Built-in Claude Code memory | claude-mem | Basic Memory | ai-memory | agentmemory | MemPalace | deja-vu | cass |
|---|---|---|---|---|---|---|---|---|---|
| **Approach** | Compiles agent transcripts into a Markdown wiki and a static site | `MEMORY.md` + topic files written by the agent; first 200 lines auto-loaded | Hooks capture sessions; a model writes structured observations; progressive disclosure | Markdown/local knowledge base over MCP; session-start briefings and pre-compaction checkpoints | Git-backed Markdown wiki + derived index; lifecycle hooks; MCP | Keyless BM25 memory over imported sessions; viewer; decay | Verbatim local storage + local embeddings; 47 MCP tools (claimed) | Retroactive index over transcripts; no LLM; published benchmark | Session search across providers; robot CLI; quarantine and GC |
| **Imports past sessions (retroactive)** | Yes — 10 adapters read transcripts already on disk | — | Early versions: no day-zero import | — | — | Yes — import of old sessions | — | Yes — 44 harnesses (claimed) | Yes — 30+ providers (claimed) |
| **Captures new sessions (forward)** | Yes — `Stop` hooks for Claude Code and ZCode, OpenCode `session.idle` | Yes — the agent writes the files by default | Yes — hooks | Yes — checkpoints and `/remember` | Yes — lifecycle hooks | — | — | — | — |
| **Output a human can read (Markdown pages)** | Yes — `wiki/` pages + static site | Yes — `MEMORY.md` + topic files | — | Yes — Markdown/local files | Yes — git-backed Markdown wiki | Yes — local files + viewer | — | — | — |
| **Needs an LLM** | No — `dummy` is the default; `extractive` writes useful pages with no model; `agent` adds no API cost; `ollama`/`openai` optional | Yes — the agent writes the files | Yes — a model summarizes every session | — | No — zero-LLM default | No — keyless BM25 default | — | No — no LLM | — |
| **Runs locally** | Yes — local-first, no cloud | Yes — files under `~/.claude/projects/<project>/memory/` | — | Yes — local Markdown; Basic Memory Cloud for sync | Yes — git-backed | Yes — local files | Yes — verbatim local storage | — | — |
| **MCP server** | Yes — 15 tools | — | — | Yes — progressive tool discovery | Yes — MCP for access | Yes — exposes its knowledge over MCP | Yes — 47 tools (claimed) | — | — |
| **Agents supported** | 10 adapters: 4 built in + 6 opt-in | Claude Code | Claude Code | Claude Code (plugin) | Cross-agent handoff | — | — | 44 harnesses (claimed) | 30+ providers (claimed) |

`—` means the competitive map does not state the fact; it is not a "no".

`sessionwiki` numbers are the verified state after 2.1.0: 10 adapters, 15 MCP
tools (the map's v2.0.5 snapshot recorded 12), five synthesis backends, one
runtime dependency (`markdown>=3.9`). Retrieval is lexical — BM25-style IDF,
recency and one graph hop — with no embeddings and no FTS index.

Stars measure attention, not quality. GitHub API, 2026-11-06: claude-mem
113.8k, MemPalace 60.4k, agentmemory 30.2k, ai-memory 15.3k, Basic Memory
4.5k, deja-vu 1.4k, cass 1.2k.

## Closest alternatives

**ai-memory** is the closest architectural analogue. It uses a git-backed
Markdown wiki as the source of truth, a derived index for retrieval, lifecycle
hooks for capture and MCP for access. Two ideas are worth copying: a handoff
summary at session start ("what was in progress, what is next") and a zero-LLM
default that still produces useful Markdown pages. It ships as a single Go
binary; `uvx` already covers distribution for `sessionwiki`, so that part does
not need copying.

**Basic Memory** is the closest product analogue. Its Claude Code plugin has
session-start briefings, pre-compaction checkpoints, `/remember` and `/status`.
Progressive tool discovery with behavior hints is already matched by the MCP
annotations in `sessionwiki/mcp/server.py`; the checkpoint and the explicit
remember path are still missing here.

**claude-mem** is one of the most popular plugins (113.8k stars on GitHub,
2026-11-06) and the best source of failure modes: token cost, Windows/macOS
breakage, closed issue submission, and no day-zero import in early versions.
Its observation model — capture tool use, summarize with a model, inject the
relevant subset — is better than per-session summaries for "what did we try and
why". `sessionwiki` already answers the cost objection better than claude-mem:
the `agent` backend lets the running session write the pages, so a subscription
user pays no extra API cost.

**deja-vu** is the best source of positioning language. Its comparison splits
the market into retroactive indexing and forward capture; `sessionwiki` is
retroactive *and* compiles a wiki. Its published benchmark also sets the bar
for the recall benchmark this project must publish.

**Built-in Claude Code memory** is the new baseline. Claude Code writes
`MEMORY.md` and topic files by default, auto-loads the first 200 lines, and
keeps them under `~/.claude/projects/<project>/memory/`. A plugin that only
"remembers" is competing with a free feature. `sessionwiki` has to be the
durable, cross-agent, auditable layer on top of it — which is why importing
that memory is on the roadmap.

## Different shape

- **Mem0 / OpenMemory** — a memory API for applications.
- **supermemory** — hosted memory with stop-hook extraction and a user profile.
- **Letta / MemGPT** — an agent runtime with self-editing memory blocks; it
  owns the agent loop.
- **Graphiti / Zep** — a temporal knowledge graph with validity windows and
  typed edges; not a wiki.
- **Cipher** — an open-source memory layer for coding agents over MCP, shared
  across IDEs and projects.
- **claude-history** — a Rust TUI for fuzzy search; deliberately declined.
- **CCHV** — a viewer with token analytics; the static site already covers
  this.
- **Mantra** — session replay with redaction; out of scope.

## When to pick sessionwiki

- You want your **existing** sessions imported, not only sessions from install
  on.
- You want an **auditable Markdown wiki** — pages in git, readable and
  editable, plus a static site.
- You use **several agents**: 10 adapters, one archive.
- You want **no LLM required** — the `extractive` backend writes useful pages
  with no model or network, and the `dummy` default writes metadata-only
  pages — or **no extra API cost**: the `agent` backend has the running agent
  write the pages.

## When to pick something else

- **Forward capture with structured observations** — claude-mem.
- **Cloud sync** — Basic Memory Cloud.
- **Semantic search out of the box** — MemPalace, claude-self-reflect.
- **A memory API for an application you build** — Mem0.

## Sources

All facts on this page are taken from the
[competitive map](competitive-map-2026-11.md#9-sources) (section 9).
