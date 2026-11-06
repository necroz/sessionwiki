"""Measure recall@k of the MCP ``wiki_query`` tool over a hand-made query set.

The query set is a JSON list of
``{"id", "kind", "question", "expected": [repo-relative paths], "why"}``.
It names real sessions, so keep it out of git (``.metrics/`` is ignored).

    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 10 --json out.json

recall@k: share of a query's expected pages found in the top k, averaged
over queries. hit@k: share of queries with at least one expected page in
the top k.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

_RANKED_RE = re.compile(r"^## `([^`]+)`", re.MULTILINE)


def ranked_paths(text: str) -> list[str]:
    """Page paths in the order ``wiki_query`` printed them."""
    return _RANKED_RE.findall(text)


def _summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "queries": n,
        "recall": sum(r["recall"] for r in rows) / n,
        "hit": sum(r["hit"] for r in rows) / n,
    }


def evaluate(queries: list[dict], rank: Callable[[str], list[str]]) -> dict:
    """Score every query; ``rank(question)`` returns the top-k paths."""
    rows = []
    for q in queries:
        found = set(rank(q["question"]))
        expected = q["expected"]
        missed = [p for p in expected if p not in found]
        rows.append({
            "id": q["id"],
            "kind": q["kind"],
            "recall": 1 - len(missed) / len(expected),
            "hit": float(len(missed) < len(expected)),
            "missed": missed,
        })
    kinds = sorted({r["kind"] for r in rows})
    return {
        "by_kind": {k: _summary([r for r in rows if r["kind"] == k]) for k in kinds},
        "overall": _summary(rows),
        "queries": rows,
    }


def format_report(report: dict, k: int) -> str:
    """Table per kind, then one line per query that missed pages."""
    lines = [f"{'kind':<12} {'n':>3} {'recall@' + str(k):>10} {'hit@' + str(k):>8}"]
    for kind, s in [*report["by_kind"].items(), ("overall", report["overall"])]:
        lines.append(f"{kind:<12} {s['queries']:>3} {s['recall']:>10.1%} {s['hit']:>8.1%}")
    lines += [
        f"  {row['id']} ({row['kind']}) missed {len(row['missed'])}: {', '.join(row['missed'])}"
        for row in report["queries"] if row["missed"]
    ]
    return "\n".join(lines)


def _wiki_query_ranker(k: int) -> Callable[[str], list[str]]:
    from sessionwiki.mcp.server import tool_wiki_query

    def rank(question: str) -> list[str]:
        result = tool_wiki_query({"question": question, "max_pages": k})
        return ranked_paths(result["content"][0]["text"])

    return rank


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("queries", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--json", type=Path, help="write the full report here")
    args = parser.parse_args(argv)

    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    report = evaluate(queries, _wiki_query_ranker(args.k))

    print(format_report(report, args.k))
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
