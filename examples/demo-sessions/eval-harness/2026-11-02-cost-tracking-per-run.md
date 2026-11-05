---
title: "Session: cost-tracking-per-run — 2026-11-02"
type: source
tags: [zcode, session-transcript, demo]
date: 2026-11-02
source_file: raw/sessions/eval-harness/2026-11-02-cost-tracking-per-run.md
sessionId: demo-262977739397
slug: cost-tracking-per-run
project: eval-harness
started: 2026-11-02T15:25:00+00:00
ended: 2026-11-02T16:25:00+00:00
cwd: /home/dev/code/eval-harness
gitBranch: feat/cost
permissionMode: default
model: qwen3-coder
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Edit": 1, "Write": 1, "Bash": 1}
token_totals: {"input": 6000, "cache_creation": 12000, "cache_read": 36000, "output": 2000}
turn_count: 1
hour_buckets: {"2026-11-02T15": 4, "2026-11-02T16": 7}
duration_seconds: 3600
is_subagent: false
---

# Session: cost-tracking-per-run — 2026-11-02

**Project:** `eval-harness` · **Branch:** `feat/cost` · **Mode:** `default` · **Model:** `qwen3-coder`

## Summary

Tracked token usage and cost per eval run and per metric, with prices loaded from a versioned table, and added a budget flag that stops a run before it exceeds a limit.

## Conversation

### Turn 1 — User

How much does one full eval run cost us?

### Turn 1 — Assistant

Record usage per judge call, price it from `prices.yaml` (versioned by date), aggregate per metric, and add `--budget` that aborts cleanly with partial results.

**Tools used in this turn:**

- `Edit`: harness/runner.py
- `Write`: harness/cost.py
- `Bash`: python -m harness run suites/support.yaml --budget 5 — $3.12

## Connections

- [[eval-harness]]
- [[CostTracking]]
- [[Budgets]]
