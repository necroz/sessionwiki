# 25 — `extractive` synthesis backend (no LLM, useful pages)

- Priority: P0
- Roadmap: Phase 2, D1
- Depends on: none
- Size: M (2–3 h)
- Files: `sessionwiki/synth/extractive.py` (new),
  `sessionwiki/synth/pipeline.py` (`resolve_backend` only),
  `tests/test_synth_extractive.py` (new), `docs/configuration-reference.md`
- Branch: `feat/extractive-backend`
- PR title: `feat(synth): add an extractive backend that needs no LLM`

## Read first

- `sessionwiki/synth/base.py`: `BaseSynthesizer`, `DummySynthesizer`
  (whole class) — the new backend subclasses it
- `sessionwiki/synth/pipeline.py`: `resolve_backend` (around line 63)
- One raw transcript under `raw/sessions/`: turn headings are
  `### Turn N — User` / `### Turn N — Assistant`
- `docs/configuration-reference.md`: the `synthesis.backend` entry

## Problem

The default `dummy` backend works without a model but writes metadata only
("Auto-synthesized from session …"). Users without a model get an empty
wiki. Competitors (ai-memory, agentmemory, deja-vu) give useful pages
without an LLM.

## Required change

1. New `sessionwiki/synth/extractive.py`:

```python
"""Extractive synthesizer: a useful source page without any LLM (D1).

Picks text that is already in the transcript: the request, the last
answer, sentences that state a decision or a fix, file paths and tools.
Output follows the source-page sections so lint and the site work.
"""

from __future__ import annotations

import re
from typing import Any

from sessionwiki.synth.base import DummySynthesizer

_TURN_RE = re.compile(r"^### Turn \d+ — (User|Assistant)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_DECISION_RE = re.compile(
    r"\b(decided|decision|we will|let's go with|chose|switched to|fixed|"
    r"root cause|the fix|because)\b|решил|выбрал|исправ|причина|потому что",
    re.IGNORECASE,
)
_PATH_RE = re.compile(r"(?<![\w/])[\w./-]+\.(?:py|md|json|toml|ya?ml|ts|tsx|js|sh|sql|go|rs)\b")
_MAX_CLAIMS = 8
_MAX_FILES = 10


class ExtractiveSynthesizer(DummySynthesizer):
    name = "extractive"
    supports_chunking = False

    def synthesize_source_page(self, raw_body: str, meta: dict[str, Any], prompt_template: str) -> str:
        ...
```

   Check the `name` attribute convention in `BaseSynthesizer` and the other
   backends and follow it.

   `synthesize_source_page` builds this body:

```markdown
## Summary

<request, ≤ 300 chars> → <first sentence(s) of the last assistant turn, ≤ 300 chars>
(<user_messages> user messages, <tool_calls> tool calls.)

## Key Claims

- <decision sentence 1>
- ... (≤ 8, unique, each ≤ 240 chars)
- Files: `a.py`, `b.md` (≤ 10, only if any)
- Tools: Bash, Edit (from meta["tools_used"], only if any)

## Key Quotes

> <first user turn, ≤ 300 chars>

## Connections

- [[<ProjectEntity>]] — parent project
```

   Rules:
   - Split turns with `_TURN_RE`. Remove fenced code (`_FENCE_RE`) from the
     text before taking sentences. Collapse whitespace.
   - Request: `meta["description"]` if present, else the first user turn.
   - Decision sentences: from assistant turns, split on `(?<=[.!?])\s+`,
     keep sentences that match `_DECISION_RE`, newest turns first.
   - Files: from the whole body including code, first seen order, unique.
   - If there are no turns, fall back to `DummySynthesizer` output
     (`super().synthesize_source_page(...)`).
   - No `[[wikilink]]` other than the project entity (reuse
     `_title_case_project`). Without a project, write the Dummy placeholder
     line for Connections.
   - Output is deterministic: same input, same output.

2. `resolve_backend`: before the final fallback, add

```python
if name == "extractive":
    from sessionwiki.synth.extractive import ExtractiveSynthesizer
    return ExtractiveSynthesizer()
```

   Update the docstring list. Do **not** change the default (`dummy`).

3. `docs/configuration-reference.md`: add `extractive` to the
   `synthesis.backend` values with one line: "no LLM; extracts the request,
   the last answer, decisions, files and tools from the transcript".

## Tests

New `tests/test_synth_extractive.py` with an inline raw body of three turns
(user request, assistant answer with a code block that contains
`decided_in_code`, assistant answer "We decided to use SQLite because it
ships with Python." and mentions `sessionwiki/cli.py`):

- All four section headings are present.
- The decision sentence is in Key Claims; `decided_in_code` is not.
- `sessionwiki/cli.py` is in Files.
- The only `[[` link is the project entity.
- Two calls give identical output.
- A body without turns returns the Dummy output.
- `resolve_backend({"synthesis": {"backend": "extractive"}})` returns an
  `ExtractiveSynthesizer`.
- Russian decision words: "Решили оставить Markdown, потому что так проще."
  is picked up.

## Verification

```bash
.venv/bin/python -m pytest tests/test_synth_extractive.py tests/test_synth_pipeline.py tests/test_synth_config_loading.py -q
.venv/bin/python -m pytest tests/ -q
```

Manual check on a copy, never on the real wiki:

```bash
mkdir -p /tmp/sw-extractive && cp -r raw /tmp/sw-extractive/ && mkdir -p /tmp/sw-extractive/wiki/sources
```

Then run synthesis against `/tmp/sw-extractive` with the `--vault` option
of `synthesize` (read `_add_vault_arg`) and `backend: extractive` in a
config there. Open three generated pages and paste one into the PR body.
Run `sessionwiki lint` on the copy: no new errors.

## Acceptance criteria

- [ ] `backend: extractive` works.
- [ ] Pages have real content and pass lint.
- [ ] Default backend unchanged.
- [ ] Docs and `CHANGELOG.md` updated.

## Out of scope

- Making `extractive` the default (maintainer decision after real use).
- Chunking for huge sessions.

## Rollback

Remove the new file and the `resolve_backend` branch.
