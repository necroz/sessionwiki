---
title: "Session: html-report-for-eval-runs — 2026-10-30"
type: source
tags: [codex-cli, session-transcript, demo]
date: 2026-10-30
source_file: raw/sessions/eval-harness/2026-10-30-html-report-for-eval-runs.md
sessionId: demo-772966262901
slug: html-report-for-eval-runs
project: eval-harness
started: 2026-10-30T14:10:00+00:00
ended: 2026-10-30T15:46:00+00:00
cwd: /home/dev/code/eval-harness
gitBranch: feat/html-report
permissionMode: default
model: gpt-5-codex
user_messages: 1
tool_calls: 3
tools_used: [Bash, Write]
tool_counts: {"Write": 2, "Bash": 1}
token_totals: {"input": 9600, "cache_creation": 19200, "cache_read": 57600, "output": 3200}
turn_count: 1
hour_buckets: {"2026-10-30T14": 4, "2026-10-30T15": 7}
duration_seconds: 5760
is_subagent: false
---

# Session: html-report-for-eval-runs — 2026-10-30

**Project:** `eval-harness` · **Branch:** `feat/html-report` · **Mode:** `default` · **Model:** `gpt-5-codex`

## Summary

Generated a self-contained HTML report per eval run: summary table, per-metric distributions, a diff view against the previous run, and drill-down into failing cases with judge rationales.

## Conversation

### Turn 1 — User

Give me a report I can share, comparing this run with the last one.

### Turn 1 — Assistant

Single HTML file with inline CSS/JS, metrics summary, histogram per metric, regressions highlighted against the baseline run, and expandable failing cases.

**Tools used in this turn:**

- `Write`: harness/report/html.py
- `Write`: harness/report/template.html
- `Bash`: python -m harness report runs/latest --baseline runs/prev — report.html

## Connections

- [[eval-harness]]
- [[Reporting]]
- [[RegressionTracking]]
