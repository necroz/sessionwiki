---
title: "Session: rag-faithfulness-metric — 2026-09-04"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-09-04
source_file: raw/sessions/eval-harness/2026-09-04-rag-faithfulness-metric.md
sessionId: demo-914618410062
slug: rag-faithfulness-metric
project: eval-harness
started: 2026-09-04T16:00:00+00:00
ended: 2026-09-04T18:36:00+00:00
cwd: /home/dev/code/eval-harness
gitBranch: feat/faithfulness
permissionMode: default
model: claude-opus-4-7
user_messages: 1
tool_calls: 3
tools_used: [Bash, Write]
tool_counts: {"Write": 2, "Bash": 1}
token_totals: {"input": 15600, "cache_creation": 31200, "cache_read": 93600, "output": 5200}
turn_count: 1
hour_buckets: {"2026-09-04T16": 4, "2026-09-04T17": 7, "2026-09-04T18": 10}
duration_seconds: 9360
is_subagent: false
---

# Session: rag-faithfulness-metric — 2026-09-04

**Project:** `eval-harness` · **Branch:** `feat/faithfulness` · **Mode:** `default` · **Model:** `claude-opus-4-7`

## Summary

Added a faithfulness metric for RAG answers: claims are extracted from the answer, each claim is checked against the retrieved passages by an LLM judge with a fixed rubric, and the score is the supported-claim ratio with per-claim evidence in the report.

## Conversation

### Turn 1 — User

I want a faithfulness score for our RAG answers, with evidence I can inspect.

### Turn 1 — Assistant

Two stages: claim extraction, then claim-vs-context judgment with a strict JSON rubric. Cache judge calls by hash so re-runs are free. Report keeps the supporting passage per claim.

```python
def faithfulness(answer: str, contexts: list[str], judge: Judge) -> MetricResult:
    claims = extract_claims(answer)
    verdicts = [judge.supported(claim, contexts) for claim in claims]
    supported = sum(v.supported for v in verdicts)
    return MetricResult(
        name="faithfulness",
        score=supported / len(claims) if claims else 1.0,
        details=[v.as_dict() for v in verdicts],
    )
```

**Tools used in this turn:**

- `Write`: harness/metrics/faithfulness.py
- `Write`: harness/judge/rubrics/faithfulness.md
- `Bash`: pytest tests/metrics -q — 14 passed

## Connections

- [[eval-harness]]
- [[RAG]]
- [[LLMAsJudge]]
- [[Faithfulness]]
