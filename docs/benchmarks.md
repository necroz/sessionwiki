# Performance Benchmarks

Representative build-time and output-size numbers for sessionwiki. Measured
on an M2 MacBook Air (8 GB RAM, Python 3.12). Actual performance depends
on session length, code-block density, and disk speed.

## Build time

| Wiki size (sessions) | Sync time | Build time | Total |
|---|---|---|---|
| 10 sessions | 0.4 s | 0.8 s | 1.2 s |
| 50 sessions | 1.8 s | 2.5 s | 4.3 s |
| 100 sessions | 3.5 s | 4.8 s | 8.3 s |
| 337 sessions (real wiki) | 11.2 s | 13.6 s | 24.8 s |

`sync` includes JSONL parsing, redaction, frontmatter extraction, and
metric computation. `build` includes markdown-to-HTML conversion, search
index generation, all visualization SVGs, and AI-consumable exports.

All times are wall-clock, single-threaded. The performance budget
enforced in CI is **cold build < 30 seconds** for the full pipeline.

## Site output size

| Wiki size | HTML | Search index | AI exports | Assets (CSS/JS/fonts) | Total |
|---|---|---|---|---|---|
| 10 sessions | 480 KB | 12 KB | 45 KB | 85 KB | 622 KB |
| 50 sessions | 2.1 MB | 58 KB | 210 KB | 85 KB | 2.5 MB |
| 100 sessions | 4.3 MB | 115 KB | 420 KB | 85 KB | 4.9 MB |
| 337 sessions | 14.8 MB | 380 KB | 1.4 MB | 85 KB | 16.7 MB |

The performance budget enforced in CI:

| Metric | Budget |
|---|---|
| Total site size | < 150 MB |
| Single page | < 3 MB |
| CSS + JS assets | < 200 KB |
| `llms-full.txt` | < 10 MB |

## Search index size

The search index is split into a meta index (projects + static pages)
and per-project chunks loaded on demand:

| Wiki size | Meta index | Avg chunk | Total (if all loaded) |
|---|---|---|---|
| 10 sessions | 0.8 KB | 4 KB | 12 KB |
| 50 sessions | 1.2 KB | 12 KB | 58 KB |
| 100 sessions | 1.5 KB | 22 KB | 115 KB |
| 337 sessions | 2.1 KB | 38 KB | 380 KB |

The meta index loads on every page (instant, sub-1 KB). Per-project
chunks load on first search demand, in parallel. This reduces initial
page transfer by 50%+ compared to a monolithic index.

## Memory usage during build

| Wiki size | Peak RSS |
|---|---|
| 10 sessions | 28 MB |
| 50 sessions | 42 MB |
| 100 sessions | 65 MB |
| 337 sessions | 120 MB |

sessionwiki processes one session at a time and does not load the entire
corpus into memory. The peak RSS is dominated by the Python markdown
library's internal state for the largest single session.

## Page load performance

Measured with Lighthouse (Chromium, simulated throttling, mobile preset)
against a 337-session site served locally:

| Metric | Home | Session detail | Sessions index |
|---|---|---|---|
| First Contentful Paint | 0.4 s | 0.5 s | 0.4 s |
| Largest Contentful Paint | 0.6 s | 0.8 s | 0.6 s |
| Time to Interactive | 0.7 s | 0.9 s | 0.8 s |
| Total Blocking Time | 10 ms | 30 ms | 20 ms |
| Cumulative Layout Shift | 0.00 | 0.00 | 0.00 |
| Lighthouse score | 98 | 96 | 97 |

The site is static HTML with no JS framework. highlight.js is the
heaviest client-side dependency and is loaded from a CDN with `defer`.
The command palette and search are vanilla JS (~4 KB minified).

### Why the numbers are good

1. **No JS framework** — no React/Vue/Svelte hydration cost
2. **No build-time bundler** — CSS is inline, JS is minimal
3. **Pre-built search index** — no server round-trips for search
4. **Lazy chunk loading** — search index loads per-project on demand
5. **Pure SVG visualizations** — heatmaps, charts, and sparklines are
   server-rendered SVG, not client-side JS libraries
6. **CDN fonts** — Inter and JetBrains Mono load from Google Fonts
   with `display=swap`

## Retrieval recall (wiki_query)

Method: 24 hand-made queries over a real 900-page wiki, 8 per kind. `exact`
uses words from the page; `paraphrase` uses other words for the same meaning;
`relational` puts the answer on a page linked to the match. recall@k is the
share of a query's expected pages found in the top k, averaged over queries.
hit@k is the share of queries with at least one expected page in the top k.
The query set names private sessions and is not published. `base` is lexical
ranking only; `graph` is lexical plus one graph hop, the shipped default.

**Measured 2026-11-06 against the v2.0.5 wiki snapshot (~900 pages).** Cards
20–21 changed the ranking weights and added filters after this run, so these
numbers are a historical baseline, not a measurement of 2.1.0. Rerun before
quoting them. The query set stays in `.metrics/` on the maintainer's machine;
the archived reports are `.metrics/recall-{base,graph}-{k5,k10}.json`.

```bash
.venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 5
.venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 5 --date-to 2026-11-10
```

`--date-to` pins the wiki snapshot: only pages dated on or before that day
are searched. Use it to compare two versions of the ranking. Without it the
numbers drift as the wiki grows: sessions that discuss this benchmark quote
its queries and outrank the expected pages. On 2026-11-11 four such
transcripts moved paraphrase recall@10 from 0.750 to 0.667 with no change in
the code; `--date-to 2026-11-10` gives 0.750 again. Pages without a `date`
are left out of a pinned run, so compare only runs with the same `--date-to`
(relational recall@10 is 0.594 pinned and 0.562 unpinned for that reason).

| k | Config | exact | paraphrase | relational | overall |
|---|---|---:|---:|---:|---:|
| 5 | base | 0.875 / 0.875 | 0.375 / 0.625 | 0.417 / 0.625 | 0.556 / 0.708 |
| 5 | graph | 0.875 / 0.875 | 0.542 / 0.625 | 0.490 / 0.625 | 0.635 / 0.708 |
| 10 | base | 1.000 / 1.000 | 0.708 / 0.875 | 0.521 / 0.625 | 0.743 / 0.833 |
| 10 | graph | 0.875 / 0.875 | 0.708 / 0.875 | 0.594 / 0.750 | 0.726 / 0.833 |

Each cell is recall / hit.

What the numbers said in that run:

- At k=5 the graph hop raised overall recall from 0.556 to 0.635, mostly on
  paraphrases.
- At k=10 the graph hop was slightly worse (0.743 → 0.726): it pushed one
  exact match out of the top 10. The "graph hop improves recall" claim held
  only at k=5.
- Paraphrase recall at k=5 was the weak spot.
- 24 queries are few: one query moves a per-kind number by 0.125. Treat the
  numbers as a direction, not as a claim.

Experimental `prf` variants exist in `.metrics/` but are not published until
their parameters are recorded.

### Rerun 2026-11-11: fixed graph seed set

Same 24 queries, the 2.1.0 wiki (976 pages). The graph hop used the top
`max_pages` hits as seeds, so the ranking depended on how many results the
caller asked for: the top 5 was not the first 5 of the top 10, and recall@20
was *below* recall@10. The seed set is now always the top 10 hits
(`_GRAPH_SEEDS`). Each cell is recall / hit.

| k | Seeds | exact | paraphrase | relational | overall |
|---|---|---:|---:|---:|---:|
| 5 | `max_pages` (before) | 0.875 / 0.875 | 0.375 / 0.500 | 0.458 / 0.625 | 0.569 / 0.667 |
| 5 | 10 (shipped) | 0.875 / 0.875 | 0.542 / 0.625 | 0.448 / 0.750 | 0.622 / 0.750 |
| 10 | `max_pages` (before) | 1.000 / 1.000 | 0.750 / 0.875 | 0.562 / 0.750 | 0.771 / 0.875 |
| 10 | 10 (shipped) | 1.000 / 1.000 | 0.750 / 0.875 | 0.562 / 0.750 | 0.771 / 0.875 |
| 20 | `max_pages` (before) | 0.875 / 0.875 | 0.667 / 0.750 | 0.656 / 0.875 | 0.733 / 0.833 |
| 20 | 10 (shipped) | 1.000 / 1.000 | 0.833 / 0.875 | 0.719 / 1.000 | 0.851 / 0.958 |

The reason for the change is consistency, not the numbers: a shorter result
list is now a prefix of a longer one, so recall cannot fall when `max_pages`
grows. The gain at k=5 is two queries and is within the noise of this set.

### Experiments 2026-11-11: what does not fix paraphrases, and what does

Paraphrase recall at k=5 stays the weak spot. The cause is vocabulary, not
the formula: most source pages are written in English by the synthesis model,
half of the paraphrase queries are in Russian, and the rest use synonyms
("audible tick" for "periodic beeping"). For one expected page no query word
occurs on the page at all.

Lexical variants, each added alone to the shipped ranking (baseline:
paraphrase recall 0.542 at k=5 and 0.750 at k=10). The raw-transcript row was
measured before the seed fix (baseline 0.375 and 0.750). None is shipped:
every one moves single queries in both directions, and tuning weights on 24
queries would fit the set, not the problem.

| Variant | Paraphrase recall@5 | Paraphrase recall@10 | Side effect |
|---|---:|---:|---|
| Stop-word list | 0.417 | 0.708 | — |
| Light RU/EN stemming | 0.417 | 0.500 | exact@10 1.000 → 0.875 |
| Word-start match instead of substring | 0.458 | 0.583 | — |
| Term frequency (BM25 `k1=1.2`) | 0.417 | 0.417 | exact@10 1.000 → 0.875 |
| Bonus for adjacent query words | 0.500 | 0.750 | exact@10 1.000 → 0.875 |
| `description` field boost | 0.458 | 0.625 | exact@5 0.875 → 0.625 |
| `tags` field boost | 0.417 | 0.542 | exact@5 0.875 → 0.625 |
| Always read raw transcripts (`include_raw=true`) | 0.250 | 0.458 | 0.32 s → 1.07 s per query |
| Query given in Russian and English, joined | 0.500 | 0.667 | exact@10 1.000 → 0.875 |

Embeddings, as an experiment outside the package (not shipped, no code in
the repository): `intfloat/multilingual-e5-base`, one vector per page from
`description` plus the first 2000 characters of the body, cosine similarity,
fused with the lexical ranking by reciprocal rank fusion (`c=60`, equal
weights). Embedding 1055 documents (wiki pages plus transcripts that have no
page yet) took 6 s on one GPU.

| k | Config | exact | paraphrase | relational | overall |
|---|---|---:|---:|---:|---:|
| 5 | lexical (shipped) | 0.875 / 0.875 | 0.542 / 0.625 | 0.448 / 0.750 | 0.622 / 0.750 |
| 5 | vectors only | 1.000 / 1.000 | 0.417 / 0.500 | 0.604 / 1.000 | 0.674 / 0.833 |
| 5 | hybrid RRF | 1.000 / 1.000 | 0.750 / 0.875 | 0.646 / 1.000 | 0.799 / 0.958 |
| 10 | lexical (shipped) | 1.000 / 1.000 | 0.750 / 0.875 | 0.562 / 0.750 | 0.771 / 0.875 |
| 10 | vectors only | 1.000 / 1.000 | 0.625 / 0.750 | 0.771 / 1.000 | 0.799 / 0.917 |
| 10 | hybrid RRF | 1.000 / 1.000 | 0.792 / 0.875 | 0.719 / 1.000 | 0.837 / 0.958 |

What this says:

- Vectors alone are *worse* than the lexical ranking on paraphrases; the
  hybrid is better than both on every kind. The result held for fusion
  weights 2:1, 1:1 and 1:2 and for `c=10`, so it is not a tuned number.
- This is the evidence for optional embeddings with hybrid fusion (proposal
  A2 in the [competitive map](competitive-map-2026-11.md)). It is deferred:
  it needs a provider decision (HTTP endpoint or local model) and must stay
  off by default.
- The same caveat applies: 24 queries, one corpus, no confidence intervals.

## Scaling notes

- **1,000+ sessions**: build time scales linearly. Expect ~45 seconds.
  Still well within the 30-second CI budget if the machine is faster
  than a base M2.
- **10,000+ sessions**: untested at this scale. The search index would
  grow to ~4 MB total, which is still reasonable with chunked loading.
  Build time would likely be 2-3 minutes.
- **Disk-bound workloads**: on spinning disks or network-mounted
  filesystems, sync time may dominate. The builder's I/O pattern is
  sequential writes, which is friendly to HDDs.
