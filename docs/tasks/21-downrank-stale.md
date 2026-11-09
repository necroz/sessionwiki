# 21 — Downrank `stale` and `archived` pages

- Priority: P1
- Roadmap: Phase 1, B6
- Depends on: 20 (same function; avoid conflicts)
- Size: S (30–45 min)
- Files: `sessionwiki/mcp/server.py`, `tests/test_mcp_query_filters.py`
- Branch: `feat/downrank-stale`
- PR title: `feat(mcp): rank stale and archived pages lower`

## Read first

- `sessionwiki/mcp/server.py`: the wiki loop in `rank_query` where
  `weight` is computed (`_QUERY_HUB_WEIGHT`)
- `sessionwiki/lifecycle.py`: the state names

## Problem

A page marked `lifecycle: stale` or `archived` ranks like a fresh one. Old
answers that newer work replaced should sink. Card 30's `wiki_archive_page`
retires a page by setting `lifecycle: archived` and leaves the file in
place, so this weight is what moves archived pages down.

## Required change

Add next to `_QUERY_HUB_WEIGHT`:

```python
# Replaced answers sink but stay findable.
_LIFECYCLE_WEIGHT = {"stale": 0.5, "archived": 0.25}
```

In the wiki loop, after `weight` is computed:

```python
weight *= _LIFECYCLE_WEIGHT.get(_frontmatter_value(content, "lifecycle").lower(), 1.0)
```

Do not change the raw loop (raw files have no lifecycle).

## Tests

Add to `tests/test_mcp_query_filters.py`:

- Two pages with the same body and date; one has `lifecycle: stale`. The
  other ranks first.
- An `archived` page with a better match still appears in the results (it
  is lower, not removed).

## Verification

```bash
.venv/bin/python -m pytest tests/test_mcp_query_filters.py tests/test_mcp_search_quality.py -q
.venv/bin/python -m pytest tests/ -q
```

If `.metrics/recall-queries.json` exists, run the eval at k=5 and k=10 and
put both numbers in the PR body. If overall recall drops by more than 0.02,
say so and do not merge without the maintainer.

## Acceptance criteria

- [ ] Stale and archived pages rank lower.
- [ ] They are not removed.
- [ ] `CHANGELOG.md` updated.

## Out of scope

- Changing `confidence.py`.

## Rollback

Remove the constant and the line.
