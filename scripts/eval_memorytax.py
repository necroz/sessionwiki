"""MemoryTax-style benchmark: does the curated wiki beat searching raw sessions?

Reproduces the method of MemoryTax (arXiv 2610.29823) on this repo's own
history. Four methods answer the same questions:

    wiki        wiki_query over curated pages, one answer call (Mem0 analogue)
    raw         BM25 over raw session turns, one answer call (BM25 analogue)
    agent-raw   a tool loop scoped to raw/sessions/ (coding-agent analogue)
    agent-wiki  the same tool loop scoped to wiki/

Two reader models (weak, strong) and an LLM judge grade every answer. Cost is
the list price of every answer call; the judge is excluded, as in the paper.
Full context is not a method here: the raw corpus is far larger than any
context window, which is exactly where designed memory could pay off.

    .venv/bin/python scripts/eval_memorytax.py run .metrics/memorytax-questions.json \
        --methods wiki,raw --models weak,strong --date-to 2026-11-10
    .venv/bin/python scripts/eval_memorytax.py judge .metrics/memorytax-runs.jsonl
    .venv/bin/python scripts/eval_memorytax.py report .metrics/memorytax-runs.jsonl

The question set names real sessions, so keep it out of git (.metrics/ is
ignored). --date-to pins both the wiki snapshot and the raw corpus so pages
about this benchmark cannot leak into the answers.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROVIDER_CONFIG = Path.home() / ".zcode" / "v2" / "provider_config.json"

MODELS = {
    "strong": {"provider": "dashscope-qwen", "model": "qwen4-max-preview"},
    "weak": {"provider": "b9a10eea-1aaf-40b1-8493-d5f2457287d3", "model": "deepseek-v4.1-flash"},
    "judge": {"provider": "b9a10eea-1aaf-40b1-8493-d5f2457287d3", "model": "glm-5.3-flash"},
}
# DashScope's token-plan endpoint returns no price; estimate from public
# qwen-max list prices and label it an estimate in the report.
EST_PRICE_PER_M = {"strong": (1.6, 6.4)}  # (input, output) $/M tokens

METHODS = ("wiki", "raw", "agent-raw", "agent-wiki")
KINDS = ("single", "multi", "temporal", "open")

_TURN_RE = re.compile(r"^### Turn (\d+) — (User|Assistant)\s*$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)


# --- corpus ---------------------------------------------------------------


def session_date(name: str) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})T", name)
    return m.group(1) if m else None


def chunk_session(text: str, source: str, max_chars: int = 1200) -> list[dict]:
    """Split a transcript into speaker-labelled blocks under max_chars."""
    body = text.split("---", 2)[-1] if text.startswith("---") else text
    matches = list(_TURN_RE.finditer(body))
    blocks: list[dict] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        turn_text = body[start:end].strip()
        if not turn_text:
            continue
        for piece in _split_chars(turn_text, max_chars):
            blocks.append({
                "text": piece, "source": source,
                "turn": int(m.group(1)), "speaker": m.group(2),
            })
    return blocks


def _split_chars(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces, cur = [], ""
    for word in text.split(" "):
        if cur and len(cur) + len(word) + 1 > max_chars:
            pieces.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def load_raw(date_to: str | None) -> list[dict]:
    out = []
    for path in sorted((REPO / "raw" / "sessions").glob("*.md")):
        day = session_date(path.name)
        if date_to and day and day > date_to:
            continue
        out.append({"path": path, "date": day, "text": path.read_text(encoding="utf-8", errors="replace")})
    return out


# --- BM25 -----------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tokens = [tokenize(d) for d in docs]
        self.dl = [len(t) for t in self.tokens]
        self.avgdl = sum(self.dl) / len(self.dl) if self.dl else 0.0
        self.tf: list[dict[str, int]] = []
        df: dict[str, int] = defaultdict(int)
        for toks in self.tokens:
            counts: dict[str, int] = defaultdict(int)
            for t in toks:
                counts[t] += 1
            self.tf.append(dict(counts))
            for t in counts:
                df[t] += 1
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 8) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for t in tokenize(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avgdl or 1))
                scores[i] += idf * f * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        return ranked[:k]


def assemble_context(blocks: list[dict], hits: list[tuple[int, float]], window: int = 2) -> str:
    """Top blocks plus ±window neighbours, deduped, in document order."""
    wanted: set[int] = set()
    for idx, _ in hits:
        wanted.update(range(max(0, idx - window), min(len(blocks), idx + window + 1)))
    parts = []
    for i in sorted(wanted):
        b = blocks[i]
        parts.append(f"[{b['source']} · turn {b['turn']} · {b['speaker']}]\n{b['text']}")
    return "\n\n".join(parts)


# --- prompts --------------------------------------------------------------

ANSWER_SYSTEM = (
    "You are a helpful assistant that can answer questions based on the provided context. "
    "If the question involves timing, use the conversation date for reference. "
    "Provide the shortest possible answer. Use words directly from the context when possible. "
    "Avoid using subjects in your answer. If the context does not contain the answer, say so."
)


def answer_messages(question: str, context: str) -> list[dict]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": f"# Question: {question}\n\n# Context:\n{context}\n\n# Short answer:"},
    ]


JUDGE_SYSTEM = (
    "You grade answers to questions about a session history. Given the question, the gold "
    "answer and a predicted answer, decide if the prediction is semantically correct. Be "
    "lenient about wording and formatting, strict about facts: a wrong number, name or date "
    "is WRONG. An answer that says the information is missing is WRONG unless the gold answer "
    "also says it is unanswerable. Reply with exactly one line 'CORRECT' or 'WRONG', then a "
    "second line with a short reason."
)


def judge_messages(question: str, gold: str, answer: str) -> list[dict]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"# Question: {question}\n# Gold answer: {gold}\n# Predicted answer: {answer}\n# Verdict:"},
    ]


def parse_verdict(text: str) -> bool:
    low = text.lower()
    c, w = low.find("correct"), low.find("wrong")
    if c == -1 and w == -1:
        return False
    if c == -1:
        return False
    if w == -1:
        return True
    return c < w


def judge_one(question: str, gold: str, answer: str, call) -> dict:
    if not answer or not answer.strip():
        return {"correct": False, "reason": "empty answer", "judged": False}
    result = call(judge_messages(question, gold, answer))
    content = result.get("content", "")
    reason = content.split("\n", 1)[1].strip() if "\n" in content else ""
    return {"correct": parse_verdict(content), "reason": reason, "judged": True}


# --- agent tools ----------------------------------------------------------

AGENT_SYSTEM = (
    "You answer questions about a session history stored in markdown files under your working "
    "root. Use the tools to find the evidence, then give the shortest possible answer. Use words "
    "directly from the files when possible. If the question involves timing, use the session dates. "
    "If the files do not contain the answer, say so. Do not guess. When you have the answer, reply "
    "with the answer text only, with no tool call."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a markdown file under the root. Optional offset/limit are line numbers.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "grep", "description": "Case-insensitive regex search over .md files under the root (or a subpath). Returns file:line: text.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "List entries of a directory under the root.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
]


def safe_path(root: Path, rel: str) -> Path:
    root = root.resolve()
    p = (root / rel).resolve()
    if not p.is_relative_to(root):
        raise ValueError(f"path escapes the scope root: {rel!r}")
    return p


def run_tool(root: Path, name: str, args: dict) -> str:
    try:
        if name == "read_file":
            p = safe_path(root, args["path"])
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            offset = int(args.get("offset", 1)) - 1
            limit = int(args.get("limit", 400))
            return "\n".join(lines[offset:offset + limit])[:20000] or "(empty file)"
        if name == "grep":
            base = safe_path(root, args.get("path", "."))
            rx = re.compile(args["pattern"], re.IGNORECASE)
            files = [base] if base.is_file() else sorted(base.rglob("*.md"))
            out, n = [], 0
            for f in files:
                if not f.is_file():
                    continue
                for ln, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        out.append(f"{f.relative_to(root.resolve())}:{ln}: {line[:200]}")
                        n += 1
                        if n >= 50:
                            return "\n".join(out) + "\n... (truncated at 50 matches)"
            return "\n".join(out) or "(no matches)"
        if name == "list_dir":
            base = safe_path(root, args.get("path", "."))
            entries = sorted(base.iterdir())[:200]
            return "\n".join(e.name + ("/" if e.is_dir() else "") for e in entries) or "(empty)"
        return f"(unknown tool {name})"
    except (ValueError, OSError, re.error) as e:
        return f"(error: {e})"


# --- LLM client -----------------------------------------------------------


def load_providers() -> dict:
    data = json.loads(PROVIDER_CONFIG.read_text(encoding="utf-8"))
    out = {}
    for r in data["config"]["providerConfigRules"]["providerRules"]:
        cfg = r.get("config", {})
        out[r["providerId"]] = {
            "base_url": cfg.get("api", {}).get("baseUrl", ""),
            "api_key": cfg.get("access", {}).get("apiKey", ""),
        }
    return out


_PROVIDERS: dict | None = None


def _provider(name: str) -> dict:
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = load_providers()
    return _PROVIDERS[name]


def llm_call(messages: list[dict], model_key: str = "weak", tools: list | None = None,
             max_tokens: int = 1024, retries: int = 3) -> dict:
    """One OpenAI-compatible chat call via curl (system CA handles the proxy)."""
    spec = MODELS[model_key]
    prov = _provider(spec["provider"])
    base = prov["base_url"].rstrip("/")
    headers = ["-H", f"Authorization: Bearer {prov['api_key']}", "-H", "Content-Type: application/json"]
    if "opencode.ai" in base:
        headers += ["-H", "x-opencode-session: sess-memorytax-eval",
                    "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"]
    body: dict = {"model": spec["model"], "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
    payload = json.dumps(body, ensure_ascii=False)
    last = ""
    for attempt in range(retries):
        t0 = time.monotonic()
        proc = subprocess.run(
            ["curl", "-s", "--max-time", "300", base + "/chat/completions", *headers, "-d", payload],
            capture_output=True, text=True,
        )
        latency = time.monotonic() - t0
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last = proc.stdout[:200] or proc.stderr[:200]
            time.sleep(2 * (attempt + 1))
            continue
        if "error" in data or "choices" not in data:
            last = str(data.get("error", data))[:200]
            time.sleep(2 * (attempt + 1))
            continue
        msg = data["choices"][0]["message"]
        usage = data.get("usage", {})
        cost = usage.get("opencode", {}).get("list_cost")
        if cost is None and model_key in EST_PRICE_PER_M:
            pin, pout = EST_PRICE_PER_M[model_key]
            cost = (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6
        return {
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls"),
            "usage": usage, "cost": cost or 0.0, "latency": latency,
            "model": data.get("model", spec["model"]),
        }
    raise RuntimeError(f"LLM call failed after {retries} tries: {last}")


# --- methods --------------------------------------------------------------


def wiki_context(question: str, date_to: str | None, k: int = 5) -> str:
    from sessionwiki.mcp.server import tool_wiki_query
    args = {"question": question, "max_pages": k, "include_raw": False}
    if date_to:
        args["date_to"] = date_to
    return tool_wiki_query(args)["content"][0]["text"]


class RawIndex:
    def __init__(self, date_to: str | None):
        self.blocks: list[dict] = []
        for s in load_raw(date_to):
            self.blocks.extend(chunk_session(s["text"], str(s["path"].relative_to(REPO))))
        self.bm25 = BM25([b["text"] for b in self.blocks])

    def context(self, question: str, k: int = 8, window: int = 2) -> str:
        return assemble_context(self.blocks, self.bm25.search(question, k), window)


def agent_answer(question: str, root: Path, model_key: str, max_steps: int = 12) -> dict:
    # A user turn is required: deepseek-v4.1-flash emits raw tool markup as
    # content (no tool_calls) when the prompt is a lone system message.
    messages = [
        {"role": "system", "content": AGENT_SYSTEM + f"\n\nWorking root: {root.name}/."},
        {"role": "user", "content": question},
    ]
    total = {"cost": 0.0, "tokens": 0, "latency": 0.0, "steps": 0}
    for _ in range(max_steps):
        res = llm_call(messages, model_key, tools=TOOLS, max_tokens=2048)
        total["cost"] += res["cost"]
        total["tokens"] += res["usage"].get("total_tokens", 0)
        total["latency"] += res["latency"]
        total["steps"] += 1
        if not res["tool_calls"]:
            return {"answer": res["content"].strip(), **total}
        messages.append({"role": "assistant", "content": res["content"] or None, "tool_calls": res["tool_calls"]})
        for tc in res["tool_calls"]:
            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            out = run_tool(root, fn["name"], args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
    return {"answer": "", **total}


def run_one(q: dict, method: str, model_key: str, date_to: str | None, raw_index: RawIndex | None) -> dict:
    t0 = time.monotonic()
    if method == "wiki":
        ctx = wiki_context(q["question"], date_to)
        res = llm_call(answer_messages(q["question"], ctx), model_key)
        answer, cost, tokens, steps = res["content"].strip(), res["cost"], res["usage"].get("total_tokens", 0), 1
        ctx_chars = len(ctx)
    elif method == "raw":
        assert raw_index is not None
        ctx = raw_index.context(q["question"])
        res = llm_call(answer_messages(q["question"], ctx), model_key)
        answer, cost, tokens, steps = res["content"].strip(), res["cost"], res["usage"].get("total_tokens", 0), 1
        ctx_chars = len(ctx)
    elif method in ("agent-raw", "agent-wiki"):
        root = REPO / ("raw/sessions" if method == "agent-raw" else "wiki")
        out = agent_answer(q["question"], root, model_key)
        answer, cost, tokens, steps = out["answer"], out["cost"], out["tokens"], out["steps"]
        ctx_chars = 0
    else:
        raise ValueError(f"unknown method {method}")
    return {
        "id": q["id"], "kind": q["kind"], "method": method, "model": model_key,
        "answer": answer, "cost": cost, "tokens": tokens, "steps": steps,
        "context_chars": ctx_chars, "latency": time.monotonic() - t0,
    }


# --- checkpoint -----------------------------------------------------------


def append_record(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a partial line left by an interrupted run
    return out


def done_keys(records: list[dict]) -> set:
    return {(r["id"], r["method"], r["model"]) for r in records}


# --- aggregation & report -------------------------------------------------


def aggregate(records: list[dict]) -> dict:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["method"], r["model"])].append(r)
    table = {}
    for key, rows in groups.items():
        by_kind = {}
        for kind in sorted({r["kind"] for r in rows}):
            kr = [r for r in rows if r["kind"] == kind]
            by_kind[kind] = {"n": len(kr), "correct": sum(r["correct"] for r in kr),
                             "accuracy": sum(r["correct"] for r in kr) / len(kr)}
        n = len(rows)
        table[key] = {
            "n": n, "correct": sum(r["correct"] for r in rows),
            "accuracy": sum(r["correct"] for r in rows) / n,
            "by_kind": by_kind,
            "cost": sum(r.get("cost", 0) for r in rows),
            "tokens": sum(r.get("tokens", 0) for r in rows),
        }
    return table


def format_report(table: dict) -> str:
    kinds = sorted({k for cell in table.values() for k in cell["by_kind"]})
    head = ["method", "model", "n", *kinds, "all", "cost$", "tokens"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    for (method, model), cell in sorted(table.items()):
        accs = [f"{cell['by_kind'][k]['accuracy']:.0%}" if k in cell["by_kind"] else "–" for k in kinds]
        lines.append("| " + " | ".join([
            method, model, str(cell["n"]), *accs, f"{cell['accuracy']:.0%}",
            f"{cell['cost']:.3f}", str(cell["tokens"]),
        ]) + " |")
    return "\n".join(lines)


# --- commands -------------------------------------------------------------


def cmd_run(args) -> int:
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    methods = args.methods.split(",")
    models = args.models.split(",")
    out = Path(args.out)
    records = load_records(out)
    done = done_keys(records)
    raw_index = RawIndex(args.date_to) if "raw" in methods else None
    tasks = [(q, m, mo) for q in questions for m in methods for mo in models
             if (q["id"], m, mo) not in done]
    total = len(tasks)
    lock = threading.Lock()
    counter = {"n": 0}

    def work(task):
        q, method, model = task
        try:
            rec = run_one(q, method, model, args.date_to, raw_index)
        except Exception as e:  # keep the run going; record the failure
            rec = {"id": q["id"], "kind": q["kind"], "method": method, "model": model,
                   "answer": "", "cost": 0.0, "tokens": 0, "steps": 0, "error": str(e)[:200]}
        with lock:
            append_record(out, rec)
            counter["n"] += 1
            print(f"[{counter['n']}/{total}] {q['id']} {method}/{model}: {rec['answer'][:70]!r}", flush=True)

    if args.workers <= 1:
        for t in tasks:
            work(t)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, tasks))
    print(f"done: {out} ({total} new, {len(records)} resumed)")
    return 0


def cmd_judge(args) -> int:
    questions = {q["id"]: q for q in json.loads(Path(args.questions).read_text(encoding="utf-8"))}
    runs = Path(args.runs)
    records = load_records(runs)
    out = Path(args.out)
    judged = {(r["id"], r["method"], r["model"]) for r in load_records(out)}
    call = lambda msgs: llm_call(msgs, "judge", max_tokens=200)  # noqa: E731
    pending = [r for r in records if (r["id"], r["method"], r["model"]) not in judged]
    total = len(pending)
    lock = threading.Lock()
    counter = {"n": 0}

    def work(r):
        q = questions[r["id"]]
        verdict = judge_one(q["question"], q["answer"], r.get("answer", ""), call)
        with lock:
            append_record(out, {**r, **verdict})
            counter["n"] += 1
            print(f"[{counter['n']}/{total}] {r['id']} {r['method']}/{r['model']}: {'OK' if verdict['correct'] else 'MISS'}", flush=True)

    if args.workers <= 1:
        for r in pending:
            work(r)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, pending))
    print(f"done: {out}")
    return 0


def cmd_report(args) -> int:
    records = load_records(Path(args.judged))
    table = aggregate(records)
    print(format_report(table))
    misses = [r for r in records if not r.get("correct")]
    if misses:
        print("\nMisses:")
        for r in misses:
            print(f"  {r['id']} ({r['kind']}) {r['method']}/{r['model']}: {r.get('answer', '')[:80]!r}")
    if args.json:
        Path(args.json).write_text(json.dumps(
            {f"{m}/{mo}": cell for (m, mo), cell in table.items()}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="answer questions with the chosen methods/models")
    p_run.add_argument("questions")
    p_run.add_argument("--methods", default="wiki,raw")
    p_run.add_argument("--models", default="weak,strong")
    p_run.add_argument("--date-to", default=None)
    p_run.add_argument("--workers", type=int, default=1, help="parallel rollouts (endpoint permitting)")
    p_run.add_argument("--out", default=".metrics/memorytax-runs.jsonl")
    p_run.set_defaults(fn=cmd_run)

    p_judge = sub.add_parser("judge", help="grade every answer with the judge model")
    p_judge.add_argument("questions")
    p_judge.add_argument("--runs", default=".metrics/memorytax-runs.jsonl")
    p_judge.add_argument("--workers", type=int, default=1)
    p_judge.add_argument("--out", default=".metrics/memorytax-judged.jsonl")
    p_judge.set_defaults(fn=cmd_judge)

    p_report = sub.add_parser("report", help="accuracy and cost table from judged runs")
    p_report.add_argument("judged", nargs="?", default=".metrics/memorytax-judged.jsonl")
    p_report.add_argument("--json", default=None)
    p_report.set_defaults(fn=cmd_report)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())