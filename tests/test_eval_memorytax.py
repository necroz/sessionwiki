"""scripts/eval_memorytax.py: MemoryTax-style memory benchmark for sessionwiki."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "eval_memorytax", Path(__file__).resolve().parents[1] / "scripts" / "eval_memorytax.py"
)
mt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mt)


# --- chunking -------------------------------------------------------------

SAMPLE = """---
title: "Session: s1"
date: 2026-09-01
---

# Session: s1

## Conversation

### Turn 1 — User

How many planograms are inWork?

### Turn 1 — Assistant

There are 42 planograms in status inWork.

### Turn 2 — User

Thanks, now check the room layouts.
"""


def test_chunks_split_turns_and_keep_the_speaker():
    blocks = mt.chunk_session(SAMPLE, "s1.md")

    assert [b["speaker"] for b in blocks] == ["User", "Assistant", "User"]
    assert [b["turn"] for b in blocks] == [1, 1, 2]
    assert all(b["source"] == "s1.md" for b in blocks)
    assert "42 planograms" in blocks[1]["text"]


def test_long_turns_split_into_blocks_under_the_cap():
    long_turn = "### Turn 1 — Assistant\n\n" + ("word " * 2000)
    blocks = mt.chunk_session(long_turn, "s.md", max_chars=1000)

    assert len(blocks) > 1
    assert all(len(b["text"]) <= 1100 for b in blocks)  # cap + one word of slack


def test_frontmatter_and_headers_are_not_indexed():
    blocks = mt.chunk_session(SAMPLE, "s1.md")

    joined = " ".join(b["text"] for b in blocks)
    assert "title:" not in joined
    assert "## Conversation" not in joined


# --- BM25 -----------------------------------------------------------------


def test_bm25_ranks_the_matching_document_first():
    docs = ["the cat sat on the mat", "a dog ran in the park", "cats and dogs are pets"]
    index = mt.BM25(docs)

    top = index.search("cat", k=2)

    assert top[0][0] == 0  # exact term beats the plural-only doc


def test_bm25_returns_nothing_for_an_absent_term():
    index = mt.BM25(["alpha beta", "gamma delta"])

    assert index.search("zzzz", k=3) == []


def test_tokenize_keeps_cyrillic_and_lowercases():
    assert mt.tokenize("Скважины НЕФТЬ 42!") == ["скважины", "нефть", "42"]


# --- context assembly -----------------------------------------------------


def test_context_expands_neighbors_and_dedups():
    blocks = [{"text": f"block {i}", "source": "s.md", "turn": 1, "speaker": "User"} for i in range(10)]
    # hits on block 3 and block 4 (adjacent) and block 8
    ctx = mt.assemble_context(blocks, [(3, 1.0), (4, 0.9), (8, 0.5)], window=1)

    assert "block 2" in ctx and "block 5" in ctx and "block 7" in ctx and "block 9" in ctx
    assert ctx.count("block 3") == 1  # overlap of the two windows is not duplicated
    assert "block 0" not in ctx and "block 6" not in ctx


def test_context_labels_the_source_of_each_block():
    blocks = [{"text": "answer here", "source": "raw/sessions/a.md", "turn": 2, "speaker": "Assistant"}]
    ctx = mt.assemble_context(blocks, [(0, 1.0)], window=0)

    assert "raw/sessions/a.md" in ctx
    assert "answer here" in ctx


# --- prompts & judge ------------------------------------------------------


def test_answer_prompt_carries_question_and_context():
    msgs = mt.answer_messages("How many?", "42 planograms")

    assert msgs[0]["role"] == "system"
    assert "How many?" in msgs[1]["content"]
    assert "42 planograms" in msgs[1]["content"]


def test_judge_verdict_parses_correct_and_wrong():
    assert mt.parse_verdict("CORRECT\nthe answer matches") is True
    assert mt.parse_verdict("WRONG\nmissing the number") is False
    assert mt.parse_verdict("verdict: correct") is True


def test_judge_counts_empty_answer_as_wrong_without_calling():
    assert mt.judge_one("q", "gold", "", call=lambda *a: pytest.fail("called")) == {
        "correct": False, "reason": "empty answer", "judged": False,
    }


def test_judge_uses_the_model_otherwise():
    calls = []

    def fake_call(messages, **kw):
        calls.append(messages)
        return {"content": "CORRECT\nok"}

    out = mt.judge_one("q", "gold", "pred", call=fake_call)

    assert out == {"correct": True, "reason": "ok", "judged": True}
    assert "gold" in calls[0][1]["content"] and "pred" in calls[0][1]["content"]


# --- agent scope safety ---------------------------------------------------


def test_scope_rejects_escape(tmp_path: Path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "a.md").write_text("x")

    assert mt.safe_path(root, "a.md") == root / "a.md"
    with pytest.raises(ValueError):
        mt.safe_path(root, "../secret")
    with pytest.raises(ValueError):
        mt.safe_path(root, "/etc/passwd")


def test_grep_tool_finds_lines_within_scope(tmp_path: Path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "a.md").write_text("alpha\nneedle here\nbeta\n")
    (root / "b.md").write_text("nothing\n")

    out = mt.run_tool(root, "grep", {"pattern": "needle"})

    assert "a.md" in out and "needle here" in out
    assert "b.md" not in out


def test_read_tool_returns_file_text(tmp_path: Path):
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "p.md").write_text("hello world")

    assert "hello world" in mt.run_tool(root, "read_file", {"path": "p.md"})


# --- aggregation & report -------------------------------------------------

RECORDS = [
    {"id": "q1", "kind": "single", "method": "wiki", "model": "weak", "correct": True, "cost": 0.001, "tokens": 100},
    {"id": "q2", "kind": "single", "method": "wiki", "model": "weak", "correct": False, "cost": 0.002, "tokens": 200},
    {"id": "q3", "kind": "multi", "method": "wiki", "model": "weak", "correct": True, "cost": 0.003, "tokens": 300},
    {"id": "q1", "kind": "single", "method": "raw", "model": "weak", "correct": True, "cost": 0.004, "tokens": 400},
]


def test_accuracy_is_per_kind_and_overall():
    table = mt.aggregate(RECORDS)

    wiki_weak = table[("wiki", "weak")]
    assert wiki_weak["n"] == 3
    assert wiki_weak["correct"] == 2
    assert wiki_weak["by_kind"]["single"]["accuracy"] == 0.5
    assert wiki_weak["by_kind"]["multi"]["accuracy"] == 1.0
    assert wiki_weak["accuracy"] == pytest.approx(2 / 3)
    assert wiki_weak["cost"] == pytest.approx(0.006)


def test_report_table_has_a_row_per_method_and_model():
    text = mt.format_report(mt.aggregate(RECORDS))

    assert "wiki" in text and "raw" in text and "weak" in text
    assert "single" in text and "multi" in text


def test_checkpoint_round_trips(tmp_path: Path):
    path = tmp_path / "runs.jsonl"
    mt.append_record(path, RECORDS[0])
    mt.append_record(path, RECORDS[1])

    loaded = mt.load_records(path)

    assert loaded == RECORDS[:2]
    assert mt.done_keys(loaded) == {("q1", "wiki", "weak"), ("q2", "wiki", "weak")}