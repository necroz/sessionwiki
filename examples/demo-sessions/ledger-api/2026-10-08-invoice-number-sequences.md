---
title: "Session: invoice-number-sequences — 2026-10-08"
type: source
tags: [codex-cli, session-transcript, demo]
date: 2026-10-08
source_file: raw/sessions/ledger-api/2026-10-08-invoice-number-sequences.md
sessionId: demo-400084459172
slug: invoice-number-sequences
project: ledger-api
started: 2026-10-08T13:50:00+00:00
ended: 2026-10-08T14:50:00+00:00
cwd: /home/dev/code/ledger-api
gitBranch: feat/invoice-numbers
permissionMode: default
model: gpt-5-codex
user_messages: 1
tool_calls: 3
tools_used: [Bash, Write]
tool_counts: {"Write": 2, "Bash": 1}
token_totals: {"input": 6000, "cache_creation": 12000, "cache_read": 36000, "output": 2000}
turn_count: 1
hour_buckets: {"2026-10-08T13": 4, "2026-10-08T14": 7}
duration_seconds: 3600
is_subagent: false
---

# Session: invoice-number-sequences — 2026-10-08

**Project:** `ledger-api` · **Branch:** `feat/invoice-numbers` · **Mode:** `default` · **Model:** `gpt-5-codex`

## Summary

Gap-free invoice numbers per legal entity and year, allocated from a Postgres row lock instead of a sequence, because sequences can skip numbers on rollback.

## Conversation

### Turn 1 — User

Accounting needs invoice numbers without gaps.

### Turn 1 — Assistant

Postgres sequences are not gap-free. Use a `numbering` table per entity and year, `SELECT … FOR UPDATE` inside the invoice transaction.

**Tools used in this turn:**

- `Write`: ledger/numbering.py
- `Write`: migrations/versions/0007_numbering.py
- `Bash`: pytest tests/test_numbering.py -q — 5 passed

## Connections

- [[ledger-api]]
- [[PostgreSQL]]
- [[RowLocks]]
