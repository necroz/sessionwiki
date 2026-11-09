# 14 — Align docs with the code: sources, dependencies, old roadmap

- Priority: P0
- Roadmap: Phase 0
- Depends on: none
- Size: S (30 min)
- Files: `README.md`, `docs/index.md`, `docs/roadmap.md`
- Branch: `docs/align-facts`
- PR title: `docs: count all adapters, state the markdown dependency, retire the old roadmap`

## Read first

- `README.md`, the `## Highlights` table (around line 36)
- `sessionwiki/adapters/__init__.py` and the file list of
  `sessionwiki/adapters/` and `sessionwiki/adapters/contrib/`
- `docs/index.md`, line 9
- `docs/roadmap.md`, the first 10 lines

## Problem

1. README says **8 sources**. The code has 10 adapters: 4 built in
   (`claude_code`, `codex_cli`, `opencode`, `zcode`) and 6 opt-in contrib
   adapters (`chatgpt`, `copilot_chat`, `copilot_cli`, `cursor`,
   `gemini_cli`, `obsidian`). The README row groups Copilot Chat and CLI and
   omits ChatGPT.
2. `docs/index.md` says "stdlib-only". The package depends on
   `markdown>=3.9` (`pyproject.toml`).
3. `docs/roadmap.md` is dated 2026-04-08 and plans v0.1–v0.3. The current
   plan is `docs/roadmap-2026-11.md`.

## Required change

1. In `README.md`, replace the `**8 sources**` row with:

```markdown
| **10 sources** | Built in: Claude Code, Codex CLI, **ZCode**, **OpenCode**. Opt-in: Cursor, Gemini CLI, Copilot Chat, Copilot CLI, ChatGPT export, Obsidian — each with its own agent badge |
```

   Before you write it, confirm the list against the files in
   `sessionwiki/adapters/` and `sessionwiki/adapters/contrib/`. If a file is
   missing or extra, use the real list and say so in the PR body.

2. Search the rest of `README.md` for other source counts:

```bash
grep -nE '\b[0-9]+ (sources|agents|adapters)\b' README.md
```

   Fix each count that contradicts the list above. Do not touch translated
   READMEs under `docs/i18n/`; list them in the PR body as follow-ups.

3. In `docs/index.md` line 9, replace "stdlib-only" with
   "minimal-dependency (Python stdlib plus `markdown`)". Keep the rest of the
   sentence.

4. At the top of `docs/roadmap.md`, directly under the `#` heading, add:

```markdown
> **Superseded.** This plan dates from 2026-04-08 (v0.1–v0.3). The current
> plan is [roadmap-2026-11.md](roadmap-2026-11.md). This file is kept as
> history.
```

## Verification

```bash
.venv/bin/python -m pytest tests/test_readme_badges.py tests/test_docs_structure.py -q
.venv/bin/python -m pytest tests/ -q
grep -n "8 sources" README.md
```

The last command prints nothing.

## Acceptance criteria

- [ ] README source count matches the adapter files.
- [ ] `docs/index.md` no longer says "stdlib-only".
- [ ] `docs/roadmap.md` carries the superseded banner.
- [ ] Tests pass.

## Out of scope

- `docs/competitor-landscape.md` (card 15).
- Translations under `docs/i18n/`.

## Rollback

Revert the three files.
