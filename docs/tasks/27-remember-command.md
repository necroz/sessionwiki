# 27 — `sessionwiki remember "<fact>"`

- Priority: P1
- Roadmap: Phase 2, C4
- Depends on: 22
- Size: S (1 h)
- Files: `sessionwiki/cli.py`, `tests/test_remember.py` (new),
  `docs/reference/cli.md`
- Branch: `feat/remember`
- PR title: `feat: remember a fact as a wiki candidate`

## Read first

- `sessionwiki/candidates.py`: module docstring, `candidates_dir`,
  `list_candidates`, the `Candidate` fields
- `sessionwiki/synth/base.py`: `DummySynthesizer._title_case_project`
- `sessionwiki/cli.py`: how `candidates` is registered

## Problem

There is no explicit "remember this" path. Basic Memory has `/remember`.
A remembered fact must not enter the trusted wiki directly; it goes to
`wiki/candidates/` for review.

## Required change

Subcommand:

```
sessionwiki remember "<fact>" [--title TITLE] [--project PROJECT]
```

- `--project` default: the current folder name.
- Title: `--title`, else the first 8 words of the fact.
- File name: TitleCase of the title words with letters and digits only
  (Unicode letters allowed), at most 60 characters, plus `.md`. If empty,
  use `Remembered-<YYYYMMDD-HHMMSS>`. If the file exists, add `-2`, `-3`, …
- Path: `wiki/candidates/concepts/<Name>.md`.
- Content:

```markdown
---
title: "<title>"
type: concept
status: candidate
origin: human
project: <project>
tags: [remembered, <project>]
created: <YYYY-MM-DD>
last_updated: <YYYY-MM-DD>
sources: []
---

# <title>

<fact>

## Connections

- [[<ProjectEntity>]] — project
```

  Check `list_candidates` to confirm the frontmatter keys it reads
  (`status`, `created`, `title`) and match them.
- Print the path and the hint
  `review with: sessionwiki candidates list`.

## Tests

New `tests/test_remember.py` (patch `REPO_ROOT` to `tmp_path`):

- The file is created under `wiki/candidates/concepts/` with
  `status: candidate` and `origin: human`.
- `list_candidates(tmp_path / "wiki")` returns it.
- A second call with the same title creates `-2`.
- A Cyrillic fact gets a Cyrillic file name, not an empty one.

## Verification

```bash
.venv/bin/python -m pytest tests/test_remember.py tests/test_candidates.py -q
.venv/bin/python -m pytest tests/ -q
```

## Acceptance criteria

- [ ] Fact stored as a candidate, never in trusted folders.
- [ ] Visible in `candidates list`.
- [ ] Docs and `CHANGELOG.md` updated.

## Out of scope

- An MCP `wiki_remember` tool. Card 30 made the write-permission decision:
  an agent remembers a fact with `wiki_write_page` under
  `wiki/candidates/concepts/` (it gets `origin: agent`; this command writes
  `origin: human`). Use the same frontmatter keys as this card so
  `candidates list` shows both.

## Rollback

Remove the subcommand and the test.
