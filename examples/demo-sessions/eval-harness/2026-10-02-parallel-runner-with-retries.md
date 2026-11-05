---
title: "Session: parallel-runner-with-retries — 2026-10-02"
type: source
tags: [zcode, session-transcript, demo]
date: 2026-10-02
source_file: raw/sessions/eval-harness/2026-10-02-parallel-runner-with-retries.md
sessionId: demo-756515094518
slug: parallel-runner-with-retries
project: eval-harness
started: 2026-10-02T09:20:00+00:00
ended: 2026-10-02T11:14:00+00:00
cwd: /home/dev/code/eval-harness
gitBranch: feat/parallel-runner
permissionMode: default
model: qwen3-coder
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Edit": 1, "Write": 1, "Bash": 1}
token_totals: {"input": 11400, "cache_creation": 22800, "cache_read": 68400, "output": 3800}
turn_count: 1
hour_buckets: {"2026-10-02T09": 4, "2026-10-02T10": 7, "2026-10-02T11": 10}
duration_seconds: 6840
is_subagent: false
---

# Session: parallel-runner-with-retries — 2026-10-02

**Project:** `eval-harness` · **Branch:** `feat/parallel-runner` · **Mode:** `default` · **Model:** `qwen3-coder`

## Summary

Rewrote the runner to evaluate cases concurrently with `asyncio` and a bounded semaphore, exponential backoff with jitter on 429/5xx, and resumable runs from a JSONL checkpoint. A 2,000-case suite went from 46 to 7 minutes.

## Conversation

### Turn 1 — User

The eval suite takes 46 minutes. Make it parallel and resumable.

### Turn 1 — Assistant

Async runner with a semaphore (default 16), retries with full jitter on 429 and 5xx only, and a JSONL checkpoint so a crashed run resumes from the last finished case.

**Tools used in this turn:**

- `Edit`: harness/runner.py
- `Write`: harness/checkpoint.py
- `Bash`: python -m harness run suites/support.yaml — 2000 cases in 7m02s

## Connections

- [[eval-harness]]
- [[Asyncio]]
- [[Backoff]]
- [[Checkpointing]]
