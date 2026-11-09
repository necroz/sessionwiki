# 16 — Publish recall results in `docs/benchmarks.md`

- Priority: P0
- Roadmap: Phase 0, E1 (first step)
- Depends on: none
- Size: S (45 min)
- Files: `docs/benchmarks.md`
- Branch: `docs/benchmarks-recall`
- PR title: `docs: publish wiki_query recall at k=5 and k=10`

## Read first

- `scripts/eval_recall.py`, the module docstring
- `docs/benchmarks.md` (current headings: build time, site size, search
  index, memory, page load, scaling notes)
- `docs/competitive-map-2026-11.md`, section 2.3

## Problem

The recall measurement exists only in `.metrics/` (ignored by git). The
docs do not mention it. The first draft of the competitive map quoted only
k=5, where the graph hop wins, and hid k=10, where it loses.

## Required change

Add a section `## Retrieval recall (wiki_query)` before `## Scaling notes`
with:

1. **Method** (5–8 lines): 24 hand-made queries over a real 900-page wiki,
   8 per kind — `exact` (words from the page), `paraphrase` (other words,
   same meaning), `relational` (the answer is on a page linked to the
   match). recall@k = share of a query's expected pages in the top k,
   averaged; hit@k = share of queries with at least one expected page in
   the top k. The query set names private sessions and is not published.
   Command:

```bash
.venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 5
```

2. **Results** — this table (recall / hit). `base` = lexical ranking only;
   `graph` = lexical + one graph hop (the shipped default).

| k | Config | exact | paraphrase | relational | overall |
|---|---|---:|---:|---:|---:|
| 5 | base | 0.875 / 0.875 | 0.375 / 0.625 | 0.417 / 0.625 | 0.556 / 0.708 |
| 5 | graph | 0.875 / 0.875 | 0.542 / 0.625 | 0.490 / 0.625 | 0.635 / 0.708 |
| 10 | base | 1.000 / 1.000 | 0.708 / 0.875 | 0.521 / 0.625 | 0.743 / 0.833 |
| 10 | graph | 0.875 / 0.875 | 0.708 / 0.875 | 0.594 / 0.750 | 0.726 / 0.833 |

   If `.metrics/recall-base-k5.json` and the other three files exist, check
   every number against their `by_kind` and `overall` keys. If a number
   differs, use the file's number and say so in the PR body.

3. **Reading** (bullets):
   - At k=5 the graph hop raises overall recall from 0.556 to 0.635, mostly
     on paraphrases.
   - At k=10 the graph hop is slightly worse (0.743 → 0.726): it pushes one
     exact match out of the top 10.
   - Paraphrase recall at k=5 is the weak spot.
   - 24 queries are few: one query moves a per-kind number by 0.125. Treat
     the numbers as a direction, not a claim.

4. One line: "Experimental `prf` variants exist in `.metrics/` but are not
   published until their parameters are recorded."

## Verification

```bash
.venv/bin/python -m pytest tests/test_docs_structure.py -q
grep -n "Retrieval recall" docs/benchmarks.md
```

## Acceptance criteria

- [ ] Section added with method, table, reading.
- [ ] The k=10 result where graph loses is in the table and the text.
- [ ] No query text and no session names in the docs.

## Out of scope

- README claims about recall.
- Expanding the query set (Phase 3).

## Rollback

Remove the section.
