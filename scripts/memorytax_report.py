"""Assemble the MemoryTax benchmark report from judged cheap + agent runs.

    .venv/bin/python scripts/memorytax_report.py \
        --judged .metrics/memorytax-judged-cheap.jsonl .metrics/memorytax-judged-agents.jsonl \
        --out .metrics/memorytax-report.md

Computes the cost-accuracy table, the Pareto frontier, empty-answer rates and
a wiki build-cost amortization estimate. The narrative is added by hand after
the numbers are in.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "eval_memorytax", Path(__file__).resolve().parents[1] / "scripts" / "eval_memorytax.py"
)
mt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mt)

KINDS = ("single", "multi", "temporal", "open")
METHOD_ORDER = ("wiki", "raw", "agent-wiki", "agent-raw")
MODEL_ORDER = ("weak", "strong")


def load_all(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        out.extend(mt.load_records(p))
    return out


def frontier(table: dict) -> set:
    """Cells no other cell beats on both cost and accuracy."""
    keys = list(table)
    strong = set()
    for k in keys:
        c, a = table[k]["cost"], table[k]["accuracy"]
        dominated = any(
            table[o]["cost"] <= c and table[o]["accuracy"] >= a
            and (table[o]["cost"] < c or table[o]["accuracy"] > a)
            for o in keys if o != k
        )
        if not dominated:
            strong.add(k)
    return strong


def empty_rate(records: list[dict], method: str, model: str) -> float:
    rows = [r for r in records if r["method"] == method and r["model"] == model]
    if not rows:
        return 0.0
    return sum(1 for r in rows if not (r.get("answer") or "").strip()) / len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--judged", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    records = load_all(args.judged)
    table = mt.aggregate(records)
    front = frontier(table)

    lines = ["# MemoryTax benchmark — sessionwiki", "",
             f"Questions: {len({r['id'] for r in records})} · "
             f"Methods: {len({r['method'] for r in records})} · "
             f"Models: weak (deepseek-v4.1-flash), strong (qwen4-max-preview) · "
             f"Judge: glm-5.3-flash", "",
             "## Cost-accuracy table", "",
             "| method | model | n | single | multi | temporal | open | all | cost$ | tokens | $/correct | empty% | frontier |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for method in METHOD_ORDER:
        for model in MODEL_ORDER:
            cell = table.get((method, model))
            if not cell:
                continue
            accs = [f"{cell['by_kind'][k]['accuracy']:.0%}" if k in cell["by_kind"] else "–" for k in KINDS]
            per_correct = cell["cost"] / cell["correct"] if cell["correct"] else float("inf")
            er = empty_rate(records, method, model)
            mark = "★" if (method, model) in front else ""
            lines.append("| " + " | ".join([
                method, model, str(cell["n"]), *accs, f"{cell['accuracy']:.0%}",
                f"{cell['cost']:.3f}", str(cell["tokens"]), f"{per_correct:.3f}",
                f"{er:.0%}", mark,
            ]) + " |")

    lines += ["", "★ = on the cost-accuracy Pareto frontier (no cell beats it on both).",
              "", "## Per-category correct counts", ""]
    for method in METHOD_ORDER:
        for model in MODEL_ORDER:
            cell = table.get((method, model))
            if not cell:
                continue
            parts = [f"{k} {cell['by_kind'][k]['correct']}/{cell['by_kind'][k]['n']}"
                     for k in KINDS if k in cell["by_kind"]]
            lines.append(f"- **{method}/{model}**: " + ", ".join(parts))

    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())