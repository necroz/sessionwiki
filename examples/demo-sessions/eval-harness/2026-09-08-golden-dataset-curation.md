---
title: "Session: golden-dataset-curation — 2026-09-08"
type: source
tags: [gemini-cli, session-transcript, demo]
date: 2026-09-08
source_file: raw/sessions/eval-harness/2026-09-08-golden-dataset-curation.md
sessionId: demo-396184606023
slug: golden-dataset-curation
project: eval-harness
started: 2026-09-08T12:10:00+00:00
ended: 2026-09-08T13:34:00+00:00
cwd: /home/dev/code/eval-harness
gitBranch: data/golden-set
permissionMode: default
model: gemini-2.5-pro
user_messages: 1
tool_calls: 2
tools_used: [Bash, Write]
tool_counts: {"Write": 1, "Bash": 1}
token_totals: {"input": 8400, "cache_creation": 16800, "cache_read": 50400, "output": 2800}
turn_count: 1
hour_buckets: {"2026-09-08T12": 4, "2026-09-08T13": 7}
duration_seconds: 5040
is_subagent: false
---

# Session: golden-dataset-curation — 2026-09-08

**Project:** `eval-harness` · **Branch:** `data/golden-set` · **Mode:** `default` · **Model:** `gemini-2.5-pro`

## Summary

Curated a 300-case golden dataset from support tickets: de-duplicated near-identical questions with embeddings, stratified by product area, and stored expected answers with source citations.

## Conversation

### Turn 1 — User

Our eval set is 80% password-reset questions.

### Turn 1 — Assistant

Cluster ticket questions by embedding similarity, sample per product area, and keep the citation for each expected answer so faithfulness can be checked.

**Tools used in this turn:**

- `Write`: scripts/curate_golden.py
- `Bash`: python scripts/curate_golden.py --target 300 — suites/golden.yaml

## Connections

- [[eval-harness]]
- [[Datasets]]
- [[Embeddings]]
