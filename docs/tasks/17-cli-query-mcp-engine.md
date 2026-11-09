# 17 — `sessionwiki query` on the MCP ranking engine

- Priority: P0
- Roadmap: Phase 0, E7 (query part)
- Depends on: none
- Size: M (2–3 h)
- Files: `sessionwiki/mcp/server.py`, `sessionwiki/cli.py`,
  `tests/test_cli_query.py` (new), `docs/reference/cli.md`
- Branch: `feat/cli-query-ranked`
- PR title: `feat(cli): query uses the same ranking as MCP wiki_query`

## Read first

- `sessionwiki/mcp/server.py`: `tool_wiki_query` (around line 462) and
  `_ranked_hits` (around line 662)
- `sessionwiki/cli.py`: `cmd_query` (around line 764) and the `query`
  parser (search for `sub.add_parser("query"`)
- `tests/test_mcp_recall.py`: `_page`, `_ranked` helpers and how tests
  patch `server.REPO_ROOT`
- `docs/reference/cli.md`, the `query` section
- `scripts/eval_recall.py`, `_RANKED_RE` — the MCP text format must not change

## Problem

`sessionwiki query` calls the optional graphify engine and fails with
"graphify not installed" by default. MCP `wiki_query` uses the ranked
lexical search with a graph hop. The CLI and the MCP answer the same
question differently, and the CLI has no `--json` or `--limit`.

## Required change

### 1. Structured core in `server.py`

`_ranked_hits` now returns `(header, snippet)` strings. Change it to return
dicts and move the header formatting into `tool_wiki_query`:

```python
def _ranked_hits(...) -> list[dict[str, Any]]:
    """Top pages after the graph hop."""
    ...
    for page, score in sorted(totals.items(), key=lambda item: -item[1])[:max_pages]:
        via_name = via[page] if bonus.get(page, 0.0) > lexical.get(page, 0.0) else ""
        snippet = scored[page][1] if page in scored else _page_snippet(page, tokens)
        hits.append({
            "path": str(page.relative_to(REPO_ROOT)),
            "score": round(score, 1),
            "via": via_name,
            "snippet": snippet,
        })
    return hits
```

Split `tool_wiki_query` into two functions:

```python
def rank_query(
    question: str,
    max_pages: int = 5,
    include_raw: Optional[bool] = None,
) -> dict[str, Any]:
    """Ranked wiki search shared by MCP wiki_query and `sessionwiki query`.

    Returns {"hits": [...], "scan_incomplete": bool, "index": str,
    "overview": str}. Each hit is {"path", "score", "via", "snippet"}.
    """
```

`rank_query` holds everything from reading `index.md` down to the call to
`_ranked_hits`. `tool_wiki_query` keeps the argument checks
(`question is required`, `wiki/ does not exist yet`), calls `rank_query`,
and builds the same text as today. The header line must stay
byte-identical:

```python
linked = f", via {hit['via']}" if hit["via"] else ""
out.append(f"## `{hit['path']}` (score: {hit['score']:.1f}{linked})\n")
```

Do not change scoring, budgets, constants or the text layout.

### 2. CLI

Replace the `query` parser with:

```python
qry = sub.add_parser("query", help="Search the wiki (same ranking as MCP wiki_query)")
qry.add_argument("question", nargs="+", help="The question to ask")
qry.add_argument("--limit", type=int, default=5, help="Pages to return (default 5)")
qry.add_argument("--json", action="store_true", help="Print hits as JSON")
raw = qry.add_mutually_exclusive_group()
raw.add_argument("--raw", dest="include_raw", action="store_const", const=True,
                 help="Always rank raw transcripts too")
raw.add_argument("--no-raw", dest="include_raw", action="store_const", const=False,
                 help="Never read raw transcripts")
qry.add_argument("--graph", action="store_true",
                 help="Use the optional graphify engine instead (needs sessionwiki[graph])")
qry.add_argument("--depth", type=int, default=3, help="graphify BFS depth (with --graph)")
qry.add_argument("--budget", type=int, default=2000, help="graphify token budget (with --graph)")
qry.set_defaults(func=cmd_query, include_raw=None)
```

New `cmd_query`:

```python
def cmd_query(args: argparse.Namespace) -> int:
    """Search the wiki with the MCP ranking, or graphify with --graph."""
    question = " ".join(args.question)
    if args.graph:
        from sessionwiki.graphify_bridge import is_available, query_graph
        if not is_available():
            print("error: graphify not installed. Run: pip install sessionwiki[graph]", file=sys.stderr)
            return 2
        print(query_graph(question, depth=args.depth, token_budget=args.budget))
        return 0
    from sessionwiki.mcp.server import rank_query, tool_wiki_query
    if args.json:
        result = rank_query(question, max_pages=args.limit, include_raw=args.include_raw)
        result.pop("index", None)
        result.pop("overview", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    out = tool_wiki_query({"question": question, "max_pages": args.limit,
                           "include_raw": args.include_raw})
    print(out["content"][0]["text"])
    return 1 if out.get("isError") else 0
```

Check how `_ok` / `_err` build the result in `server.py` and adapt the
`isError` check to the real key. `rank_query` reads the server's
`REPO_ROOT`; check that it resolves to the same folder as the CLI's
`REPO_ROOT` (both read `SESSIONWIKI_HOME`). If they differ, say so in the
PR body and stop.

### 3. Docs

Update the `query` section of `docs/reference/cli.md` with the new flags.
If `tests/test_cli_doc_parity.py` fails, update the doc it names.

## Tests

New `tests/test_cli_query.py`. Seed a tiny wiki in `tmp_path` like
`tests/test_mcp_recall.py` does, and patch both `sessionwiki.cli.REPO_ROOT`
and `sessionwiki.mcp.server.REPO_ROOT`.

- `--json` returns the same paths, in the same order, as
  `tool_wiki_query` for the same question.
- `--limit 1` returns one hit.
- Text mode output contains `## \`` headers in the MCP format.
- `--graph` without graphify returns 2 (patch `is_available` to `False`).

## Verification

```bash
.venv/bin/python -m pytest tests/test_cli_query.py tests/test_mcp_recall.py tests/test_mcp_search_quality.py tests/test_query_graph.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m sessionwiki query chunking large sessions --limit 3
.venv/bin/python -m sessionwiki query chunking large sessions --limit 3 --json
```

If `.metrics/recall-queries.json` exists, also run the eval and confirm the
numbers did not change:

```bash
.venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 5
```

## Acceptance criteria

- [ ] `rank_query` exists and `tool_wiki_query` uses it.
- [ ] MCP text output is unchanged (existing tests and eval numbers).
- [ ] `sessionwiki query` works without graphify; `--graph` keeps the old path.
- [ ] `--json` and `--limit` work.
- [ ] Docs updated; `CHANGELOG.md` updated.

## Out of scope

- Filters (card 20).
- Any ranking change.

## Rollback

Revert `server.py`, `cli.py`, the docs and the new test.
