# sessionwiki — Codex CLI / Agent Schema

This file is the schema for **Codex CLI** and any other coding agent that reads `AGENTS.md` instead of `CLAUDE.md` (OpenCode, Gemini CLI, etc.). The workflows are identical to [CLAUDE.md](CLAUDE.md) — only the language is agent-agnostic.

## Three layers

```
raw/           IMMUTABLE. Session transcripts converted from the agent's session store.
               Never modify files here.

wiki/          LLM-maintained. Pages you write that summarise and cross-reference raw/.
  index.md         Catalog of every page. Update on every ingest.
  log.md           Append-only chronological record (auto-archives at 50KB).
  overview.md      Living synthesis.
  hints.md         Writing conventions and entity naming rules (load on demand).
  hot.md           Last 10 session summaries — global hot cache.
  hot/<project>.md Per-project hot caches (default ON, configurable).
  MEMORY.md        Cross-session facts (200-line cap, auto-consolidated).
  SOUL.md          Wiki identity and writing voice.
  CRITICAL_FACTS.md Must-know facts (<120 tokens).
  sources/         One page per raw source.
  entities/        People, companies, projects, products.
  concepts/        Ideas, frameworks, methods.
  syntheses/       Saved query answers.
  lessons/         Distilled experience injected into later attempts.

site/          GENERATED. Static HTML from `python3 -m sessionwiki build`. Do not edit.
```

## Session stores by agent

Different agents write their transcripts to different locations. The adapter registry in `sessionwiki/adapters/` abstracts this away.

| Agent | Session store | Adapter |
|---|---|---|
| Claude Code | `~/.claude/projects/<project>/<uuid>.jsonl` | `claude_code.py` |
| Codex CLI | `~/.codex/sessions/` | `codex_cli.py` (stub in v0.1) |
| Gemini CLI | `~/.gemini/` (TBD) | `gemini_cli.py` (planned) |
| OpenCode | `~/.local/share/opencode/opencode.db` → `~/.llmwiki/opencode/` | `opencode.py` |

The CLI auto-detects which adapter(s) to run. Override with `--adapter <name>`.

## Commands

Run from inside the repo:

```bash
python3 -m sessionwiki sync           # export ZCode/OpenCode + convert .jsonl → raw/sessions/*.md
python3 -m sessionwiki opencode autosync  # OpenCode V2 SQLite → JSONL → markdown
python3 -m sessionwiki opencode install   # install the session.idle autosync plugin
python3 -m sessionwiki build          # compile site/ from raw/ + wiki/
python3 -m sessionwiki serve          # local HTTP server on 127.0.0.1:8765
python3 -m sessionwiki init           # scaffold raw/, wiki/, site/ directories
```

Or use the one-click scripts: `./sync.sh`, `./build.sh`, `./serve.sh` (macOS/Linux); `sync.bat`, `build.bat`, `serve.bat` (Windows).

## Ingest Workflow

Triggered when the user says "ingest this", "sync the wiki", or runs `/wiki-sync`:

1. Read the source file(s) under `raw/`.
2. Read `wiki/index.md` and `wiki/overview.md` for current wiki context.
3. For each source, write `wiki/sources/<slug>.md` using the Source Page Format below.
4. Update `wiki/index.md` — add the new source under `## Sources`.
5. Update `wiki/overview.md` if the source adds substantial new information.
6. Create/update `wiki/entities/<Name>.md` for any people, companies, projects, tools, or libraries mentioned.
7. Create/update `wiki/concepts/<Name>.md` for any ideas or patterns discussed.
8. Cross-link everything with `[[wikilinks]]` under `## Connections`.
9. Flag contradictions under `## Contradictions` — keep both claims visible.
10. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

## Query Workflow

Triggered by `/wiki-query <question>`:

1. Read `wiki/index.md` and `wiki/overview.md`.
2. Read the pages most relevant to the question.
3. Synthesise an answer with `[[wikilink]]` citations.
4. If the answer is substantial, ask if it should be saved to `wiki/syntheses/<slug>.md`.
5. Append to `wiki/log.md`: `## [YYYY-MM-DD] query | <question>`.

## Lint Workflow

Triggered by `/wiki-lint`:

Check for:

- **Orphans** — pages with no inbound `[[links]]`.
- **Broken wikilinks** — pointing to non-existent pages.
- **Contradictions** — conflicting claims across pages.
- **Stale pages** — `last_updated` older than the most recent contributing source.
- **Missing entity pages** — entities mentioned in 3+ sources but no dedicated page.
- **Data gaps** — questions the wiki can't answer.

Output a report. Offer to save it to `wiki/lint-report.md`.

## Page formats

### Source page (`wiki/sources/<slug>.md`)

```markdown
---
title: "Source Title"
type: source
tags: []
date: YYYY-MM-DD
source_file: raw/sessions/<project>/<file>.md
project: <project-slug>
---

## Summary
2–4 sentences.

## Key Claims
- Claim 1
- Claim 2

## Key Quotes
> "Quote" — context

## Connections
- [[Entity]] — how they relate
- [[Concept]] — how it connects
```

### Entity / Concept page

```markdown
---
title: "Name"
type: entity   # or: concept
tags: []
sources: [slug-1, slug-2]
last_updated: YYYY-MM-DD
---

# Name

One paragraph.

## Key Facts
- Fact 1

## Sessions
- [[session-slug]] (YYYY-MM-DD) — what happened

## Connections
- [[Other]]
```

### Lesson page (`wiki/lessons/<slug>.md`)

Distilled experience carried into later attempts (Reflexion-style). The
prompt hook injects up to three lessons whose lifecycle is `reviewed` or
`verified`; `draft` lessons stay out until approved. Prefer external
evidence (test result, review verdict, user correction) over the model's
self-evaluation. Agent-written lessons start as `draft`; approve them
with `wiki_update_frontmatter` (`lifecycle: reviewed`) after the user
agrees.

```markdown
---
title: "Short rule name"
type: lesson
tags: []
sources: [session-slug]
project: project-slug
date: YYYY-MM-DD
lifecycle: draft  # reviewed/verified = approved for auto-injection
confidence: 0.7
---

## Situation
When this applies.

## Outcome
What happened, with evidence.

## Rule
What to do differently next time. One or two sentences.

## Connections
- [[session-slug]] — where this was learned
```

### Index

```markdown
# Wiki Index

## Overview
- [Overview](overview.md)

## Sources
- [Title](sources/slug.md) — one-line summary

## Entities
- [Name](entities/Name.md) — one-line description

## Concepts
- [Name](concepts/Name.md) — one-line description

## Syntheses
- [Title](syntheses/slug.md) — the question it answers
```

### Log

```markdown
## [YYYY-MM-DD] <operation> | <title>

<optional one-line notes>
```

Parse recent entries with: `grep "^## \[" wiki/log.md | tail -10`

## Naming conventions

- Source slugs: `kebab-case`
- Entity / concept pages: `TitleCase.md`
- Synthesis pages: `kebab-case.md`
- Lesson pages: `kebab-case.md`

## Cross-project wiki access

Other projects can reference this wiki by adding to their agent config:

```
wiki_path: ~/path/to/sessionwiki
```

Then read `wiki/index.md` first, navigate from there.

## Entity types

Every entity page should declare `entity_type` in frontmatter:

`person` | `org` | `tool` | `concept` | `api` | `library` | `project`

## Confidence & lifecycle

- `confidence: 0.85` — 4-factor score (source count, quality, recency, cross-refs)
- `confidence_measured: 2026-11-11` / `confidence_pages: 976` — stamped automatically when a write sets confidence: the date and the corpus state at measurement time. A confidence without provenance is a lint warning; re-score when the sources change.
- `lifecycle: draft` — one of: draft, reviewed, verified, stale, archived

## Hard rules

1. `raw/` is immutable. Never edit files there.
2. No silent overwrites. Record contradictions, don't hide them.
3. Cross-link everything — every page has a `## Connections` section.
4. Frontmatter is authoritative. Always populate `title`, `type`, `tags`, `sources`, `last_updated`, `confidence`, `lifecycle`, `entity_type`.
5. Do not ingest raw `.jsonl` files directly — only ingest the markdown under `raw/`.
6. **Human pages are read-only for the LLM.** A page with `origin: human`
   in its frontmatter is never rewritten by synthesis, coalescing,
   backfill, ingest or the MCP write tools. Put hand-written notes under
   `wiki/notes/`.
