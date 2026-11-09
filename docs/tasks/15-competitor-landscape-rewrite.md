# 15 — Rewrite `docs/competitor-landscape.md`

- Priority: P0
- Roadmap: Phase 0, E4
- Depends on: none (card 14 recommended first)
- Size: S (1–1.5 h)
- Files: `docs/competitor-landscape.md`
- Branch: `docs/competitor-landscape-2026-11`
- PR title: `docs: rewrite the competitor landscape for coding-agent memory tools`

## Read first

- `docs/competitor-landscape.md` (the current file)
- `docs/competitive-map-2026-11.md`, sections 1, 2.2, 3, 3.1, 3.2, 4.1 and 7.
  This is the **only** source of facts for this card.

## Problem

The current page compares sessionwiki with mem0, Rewind and Pieces, says
"6 agents", lists a PDF adapter that does not exist and says "stdlib only".
The real competitors in 2026 are coding-agent memory tools.

## Required change

Rewrite the file with this structure. Keep it under ~200 lines.

```markdown
# Competitor Landscape

(one paragraph: what problem all these tools solve; date: November 2026)

## Two axes

- Retroactive indexing (reads transcripts already on disk) vs forward
  capture (records from install on).
- Compiled wiki (pages a human can read and audit) vs memory API (facts
  returned to an agent).
(2–3 sentences on where sessionwiki sits: retroactive and compiled.)

## Comparison

(table)

## Closest alternatives

(one short paragraph each: ai-memory, Basic Memory, claude-mem, deja-vu,
built-in Claude Code memory)

## Different shape

(one line each: Mem0/OpenMemory, supermemory, Letta, Graphiti/Zep, Cipher,
claude-history, CCHV, Mantra)

## When to pick sessionwiki

## When to pick something else

## Sources

(link to docs/competitive-map-2026-11.md section 9)
```

Table columns: sessionwiki, built-in Claude Code memory, claude-mem,
Basic Memory, ai-memory, agentmemory, MemPalace, deja-vu, cass.

Table rows:

- Approach
- Imports past sessions (retroactive)
- Captures new sessions (forward)
- Output a human can read (Markdown pages)
- Needs an LLM
- Runs locally
- MCP server
- Agents supported

Rules for the cells:

- Use only facts stated in `docs/competitive-map-2026-11.md`.
- When the map marks a number "(claimed)", keep "(claimed)".
- When the map does not state a fact, write `—`. Do not guess and do not
  look it up on the web.
- For sessionwiki use the verified state from section 2.2 of the map:
  10 adapters (4 built in + 6 opt-in), 12 MCP tools, backends `dummy`
  (default, no LLM), `ollama`, `openai`, `agent` (no extra API cost),
  runtime dependency `markdown`.
- Star counts are not quality. If you add them, give the date
  (2026-11-06) and the source (GitHub API).

In "When to pick sessionwiki", lead with: retroactive import of existing
sessions, auditable Markdown wiki, many agents, no LLM required (`dummy`
backend) or no extra cost (`agent` backend).

In "When to pick something else", be honest: forward capture with
structured observations (claude-mem), cloud sync (Basic Memory Cloud),
semantic search out of the box (MemPalace, claude-self-reflect), a memory
API for an application (Mem0).

## Verification

```bash
.venv/bin/python -m pytest tests/test_docs_structure.py -q
grep -nE 'Rewind|Pieces|PDF|6 agents|stdlib only' docs/competitor-landscape.md
```

The `grep` prints nothing.

## Acceptance criteria

- [ ] Structure as above.
- [ ] No fact that is not in the competitive map.
- [ ] mem0/Rewind/Pieces comparison removed (Mem0 stays under "Different shape").
- [ ] Docs tests pass.

## Out of scope

- README changes.
- New research.

## Rollback

`git checkout -- docs/competitor-landscape.md`
