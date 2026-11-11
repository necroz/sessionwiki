"""Measure recall@k of the MCP ``wiki_query`` tool over a hand-made query set.

The query set is a JSON list of
``{"id", "kind", "question", "expected": [repo-relative paths], "why"}``.
It names real sessions, so keep it out of git (``.metrics/`` is ignored).

    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 10 --json out.json
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --date-to 2026-11-10

The wiki grows every day, and sessions that discuss this benchmark quote its
queries, so they outrank the expected pages. ``--date-to`` searches only
pages dated on or before that day: two runs then see the same pages, and a
change in the numbers is a change in the code. Pages without a ``date`` are
left out, so compare only runs that use the same ``--date-to``.

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
from datetime import date
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


def _day(value: str) -> str:
    """argparse type: a YYYY-MM-DD date. wiki_query ignores a bad date
    filter silently, which here would measure the live wiki unnoticed."""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a YYYY-MM-DD date: {value!r}") from None


def _wiki_query_ranker(k: int, date_to: str | None = None) -> Callable[[str], list[str]]:
    from sessionwiki.mcp.server import tool_wiki_query

    snapshot = {"date_to": date_to} if date_to else {}

    def rank(question: str) -> list[str]:
        result = tool_wiki_query({"question": question, "max_pages": k, **snapshot})
        return ranked_paths(result["content"][0]["text"])

    return rank


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("queries", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--json", type=Path, help="write the full report here")
    parser.add_argument(
        "--date-to", type=_day, metavar="YYYY-MM-DD",
        help="search only pages dated on or before this day (pins the wiki snapshot)",
    )
    args = parser.parse_args(argv)

    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    report = evaluate(queries, _wiki_query_ranker(args.k, args.date_to))
    report["date_to"] = args.date_to

    if args.date_to:
        print(f"wiki snapshot: pages dated on or before {args.date_to}")
    print(format_report(report, args.k))
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
