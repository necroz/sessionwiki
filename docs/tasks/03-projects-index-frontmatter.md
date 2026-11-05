# 03 — Valid frontmatter for the generated projects index

- Priority: P1
- Depends on: none
- Size: S (15–30 min)
- Files: `sessionwiki/build.py`, `tests/test_graph_session.py`
- PR title: `fix: emit valid frontmatter for projects index`

## Read first

- `sessionwiki/build.py`, function `ensure_projects_index` (around line 338)
- `tests/test_graph_session.py`, function
  `test_ensure_projects_index_links_stubs` (around line 181)
- `sessionwiki/lint/rules/frontmatter_validity.py`, `VALID_TYPES`

## Problem

`ensure_projects_index()` writes:

```python
"type: index",
"tags: [index, projects]",
```

Two problems:

1. `frontmatter_validity` does not allow `index`. Allowed values are
   `source`, `entity`, `concept`, `synthesis`, `comparison`, `question`,
   `navigation`, `context`. The generated page produces a lint error.
2. `tags_topics_convention` expects project navigation pages to use
   `topics:`, not `tags:`.

`ensure_projects_index()` is called by `build_site(..., seed_project_stubs=True)`,
which `sessionwiki sync --auto-build` uses. So a normal sync can turn a
clean wiki into a lint error.

## Required change

In `sessionwiki/build.py` replace the two lines:

```python
"type: index",
"tags: [index, projects]",
```

with:

```python
"type: navigation",
"topics: [projects]",
```

Do not change the rest of the generated file.

## Test

Update `tests/test_graph_session.py::test_ensure_projects_index_links_stubs`.
It currently asserts:

```python
assert "type: index" in text
```

Change it to:

```python
assert "type: navigation" in text
assert "topics: [projects]" in text
assert "type: index" not in text
assert "tags: [index, projects]" not in text
```

Add a test that runs the generated page through the lint rule, if the
rule is easy to call. Otherwise the existing test plus the lint command
below is enough.

## Verification

```bash
.venv/bin/python -m pytest tests/test_graph_session.py -q
.venv/bin/python -m sessionwiki lint
```

Then reproduce the original failure path without touching the real
wiki:

```bash
.venv/bin/python - <<'PY'
import tempfile
from pathlib import Path
from sessionwiki.build import ensure_projects_index

with tempfile.TemporaryDirectory() as d:
    meta = Path(d)
    (meta / "demo.md").write_text(
        '---\ntitle: "demo"\ntype: entity\nentity_type: project\n'
        'project: demo\n---\n',
        encoding="utf-8",
    )
    text = ensure_projects_index(meta).read_text(encoding="utf-8")
    print(text)
    assert "type: navigation" in text
    assert "topics: [projects]" in text
    assert "type: index" not in text
PY
```

Expected: the assertions pass and `sessionwiki lint` reports `0 errors`.

## Acceptance criteria

- [ ] `ensure_projects_index` emits `type: navigation`.
- [ ] It emits `topics: [projects]`.
- [ ] It no longer emits `tags: [index, projects]`.
- [ ] The updated test passes.
- [ ] `sessionwiki lint` reports `0 errors`.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- Changing `frontmatter_validity` to accept `index`.
- Regenerating the real `wiki/projects/index.md`; `sync --auto-build`
  will do it later.
- Changing the project page format.

## Rollback

Revert the two lines and the test assertions.
