---
title: "Session: customer-api-pagination — 2026-08-20"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-08-20
source_file: raw/sessions/ledger-api/2026-08-20-customer-api-pagination.md
sessionId: demo-866321754907
slug: customer-api-pagination
project: ledger-api
started: 2026-08-20T11:20:00+00:00
ended: 2026-08-20T12:14:00+00:00
cwd: /home/dev/code/ledger-api
gitBranch: feat/pagination
permissionMode: default
model: claude-sonnet-4-6
user_messages: 1
tool_calls: 2
tools_used: [Bash, Edit]
tool_counts: {"Edit": 1, "Bash": 1}
token_totals: {"input": 5400, "cache_creation": 10800, "cache_read": 32400, "output": 1800}
turn_count: 1
hour_buckets: {"2026-08-20T11": 4, "2026-08-20T12": 7}
duration_seconds: 3240
is_subagent: false
---

# Session: customer-api-pagination — 2026-08-20

**Project:** `ledger-api` · **Branch:** `feat/pagination` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Switched the customer list endpoint from offset to keyset pagination with an opaque cursor, so deep pages stay fast and results do not shift when new customers are created.

## Conversation

### Turn 1 — User

Listing customers gets slow past page 200.

### Turn 1 — Assistant

Keyset pagination on `(created_at, id)` with a base64 cursor; the old `page` parameter keeps working for one release with a deprecation header.

**Tools used in this turn:**

- `Edit`: ledger/routes/customers.py
- `Bash`: pytest tests/test_pagination.py -q — 7 passed

## Connections

- [[ledger-api]]
- [[KeysetPagination]]
- [[FastAPI]]
