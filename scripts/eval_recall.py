"""Measure recall@k of the MCP ``wiki_query`` tool over a hand-made query set.

The query set is a JSON list of
``{"id", "kind", "question", "expected": [repo-relative paths], "why"}``.
It names real sessions, so keep it out of git (``.metrics/`` is ignored).

    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --k 10 --json out.json
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --date-to 2026-11-10
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --bootstrap 2000
    .venv/bin/python scripts/eval_recall.py .metrics/recall-queries.json --validate

``--bootstrap`` adds a percentile confidence interval over queries (the set
is a sample, so a point estimate alone overstates precision). ``--validate``
checks the schema and that every expected path exists, then exits without
searching.

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
import random
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


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile; ``q`` is in [0, 1]."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def bootstrap_ci(
    values: list[float],
    resamples: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean of ``values``.

    The query set is a sample from an unbounded population of possible
    questions, so the mean alone hides how much one query can move it.
    Deterministic for a given seed: two runs with the same seed return
    the same interval.
    """
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(resamples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    alpha = (1 - level) / 2
    return (_percentile(means, alpha), _percentile(means, 1 - alpha))


def _report_ci(report: dict, resamples: int, seed: int, level: float = 0.95) -> dict:
    rows = report["queries"]
    recall = bootstrap_ci([r["recall"] for r in rows], resamples, seed, level)
    hit = bootstrap_ci([r["hit"] for r in rows], resamples, seed, level)
    return {
        "level": level,
        "resamples": resamples,
        "seed": seed,
        "recall": list(recall),
        "hit": list(hit),
    }


_KINDS = {"exact", "paraphrase", "relational"}


def validate_queries(queries: list[dict], root: Path | None = None) -> list[str]:
    """Schema and path checks; returns one message per problem."""
    base = Path(root or ".")
    errors: list[str] = []
    seen: set[str] = set()
    for index, q in enumerate(queries, start=1):
        qid = q.get("id") if isinstance(q.get("id"), str) else f"#{index}"
        if not isinstance(q.get("id"), str) or not q.get("id"):
            errors.append(f"{qid}: missing id")
        elif q["id"] in seen:
            errors.append(f"duplicate id {q['id']}")
        else:
            seen.add(q["id"])
        if q.get("kind") not in _KINDS:
            errors.append(f"{qid}: unknown kind {q.get('kind')!r}")
        if not isinstance(q.get("question"), str) or not q["question"].strip():
            errors.append(f"{qid}: missing question")
        expected = q.get("expected")
        if not isinstance(expected, list) or not expected:
            errors.append(f"{qid}: expected must be a non-empty list")
            continue
        for path in expected:
            if not isinstance(path, str) or not (base / path).is_file():
                errors.append(f"{qid}: missing expected path {path}")
    return errors


def format_report(report: dict, k: int, ci: dict | None = None) -> str:
    """Table per kind, then one line per query that missed pages."""
    lines = [f"{'kind':<12} {'n':>3} {'recall@' + str(k):>10} {'hit@' + str(k):>8}"]
    for kind, s in [*report["by_kind"].items(), ("overall", report["overall"])]:
        lines.append(f"{kind:<12} {s['queries']:>3} {s['recall']:>10.1%} {s['hit']:>8.1%}")
    if ci:
        level = ci["level"] * 100
        lines.append(
            f"{level:.0f}% CI ({ci['resamples']} resamples, seed {ci['seed']}): "
            f"recall {ci['recall'][0]:.1%}-{ci['recall'][1]:.1%}, "
            f"hit {ci['hit'][0]:.1%}-{ci['hit'][1]:.1%}"
        )
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
    parser.add_argument(
        "--bootstrap", type=int, default=0, metavar="N",
        help="add a 95%% bootstrap CI over queries with N resamples",
    )
    parser.add_argument("--seed", type=int, default=0, help="bootstrap seed")
    parser.add_argument(
        "--validate", action="store_true",
        help="check the schema and expected paths, then exit",
    )
    args = parser.parse_args(argv)

    queries = json.loads(args.queries.read_text(encoding="utf-8"))

    if args.validate:
        errors = validate_queries(queries)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if errors:
            return 2
        print(f"ok: {len(queries)} queries")
        return 0

    report = evaluate(queries, _wiki_query_ranker(args.k, args.date_to))
    report["date_to"] = args.date_to
    if args.bootstrap:
        report["ci"] = _report_ci(report, args.bootstrap, args.seed)

    if args.date_to:
        print(f"wiki snapshot: pages dated on or before {args.date_to}")
    print(format_report(report, args.k, report.get("ci")))
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
