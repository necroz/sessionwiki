---
title: "Session: fix-rounding-in-tax-calculation — 2026-10-06"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-10-06
source_file: raw/sessions/ledger-api/2026-10-06-fix-rounding-in-tax-calculation.md
sessionId: demo-435153909190
slug: fix-rounding-in-tax-calculation
project: ledger-api
started: 2026-10-06T10:30:00+00:00
ended: 2026-10-06T11:42:00+00:00
cwd: /home/dev/code/ledger-api
gitBranch: fix/tax-rounding
permissionMode: default
model: claude-opus-4-7
user_messages: 1
tool_calls: 4
tools_used: [Bash, Edit, Write]
tool_counts: {"Bash": 2, "Edit": 1, "Write": 1}
token_totals: {"input": 7200, "cache_creation": 14400, "cache_read": 43200, "output": 2400}
turn_count: 1
hour_buckets: {"2026-10-06T10": 4, "2026-10-06T11": 7}
duration_seconds: 4320
is_subagent: false
---

# Session: fix-rounding-in-tax-calculation — 2026-10-06

**Project:** `ledger-api` · **Branch:** `fix/tax-rounding` · **Mode:** `default` · **Model:** `claude-opus-4-7`

## Summary

Tracked down a one-cent mismatch between invoice totals and the PDF: tax was rounded per line instead of per invoice. Switched to `Decimal` with banker's rounding at the invoice level and added a property-based test with Hypothesis.

## Conversation

### Turn 1 — User

Customers report invoices off by one cent vs the PDF.

### Turn 1 — Assistant

Root cause: tax is rounded on every line item, then summed. Rounding once per invoice with `ROUND_HALF_EVEN` fixes it. Adding a Hypothesis test that the sum of lines always equals the invoice total.

**Tools used in this turn:**

- `Bash`: pytest -k tax -q — 1 failed (reproduces)
- `Edit`: ledger/tax.py
- `Write`: tests/test_tax_properties.py
- `Bash`: pytest -q — 41 passed

## Connections

- [[ledger-api]]
- [[Decimal]]
- [[Hypothesis]]
- [[BankersRounding]]
