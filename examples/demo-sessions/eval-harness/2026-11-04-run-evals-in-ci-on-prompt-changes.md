---
title: "Session: run-evals-in-ci-on-prompt-changes — 2026-11-04"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-11-04
source_file: raw/sessions/eval-harness/2026-11-04-run-evals-in-ci-on-prompt-changes.md
sessionId: demo-257994910279
slug: run-evals-in-ci-on-prompt-changes
project: eval-harness
started: 2026-11-04T10:40:00+00:00
ended: 2026-11-04T11:58:00+00:00
cwd: /home/dev/code/eval-harness
gitBranch: chore/ci
permissionMode: default
model: claude-sonnet-4-6
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Write": 1, "Edit": 1, "Bash": 1}
token_totals: {"input": 7800, "cache_creation": 15600, "cache_read": 46800, "output": 2600}
turn_count: 1
hour_buckets: {"2026-11-04T10": 4, "2026-11-04T11": 7}
duration_seconds: 4680
is_subagent: false
---

# Session: run-evals-in-ci-on-prompt-changes — 2026-11-04

**Project:** `eval-harness` · **Branch:** `chore/ci` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Wired the harness into CI: a workflow runs the smoke suite on every PR that touches `prompts/`, posts the score deltas as a PR comment, and fails if faithfulness drops more than two points.

## Conversation

### Turn 1 — User

Run evals automatically when someone changes a prompt.

### Turn 1 — Assistant

Path-filtered workflow on `prompts/**`, smoke suite (200 cases), baseline from the latest main run, comment with the delta table, and a threshold gate on faithfulness.

**Tools used in this turn:**

- `Write`: .github/workflows/evals.yml
- `Edit`: harness/cli.py — --fail-on-drop
- `Bash`: act pull_request -W .github/workflows/evals.yml — ok

## Connections

- [[eval-harness]]
- [[GitHubActions]]
- [[QualityGates]]
