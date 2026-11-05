---
title: "Session: add-pdf-invoice-export — 2026-11-03"
type: source
tags: [zcode, session-transcript, demo]
date: 2026-11-03
source_file: raw/sessions/ledger-api/2026-11-03-add-pdf-invoice-export.md
sessionId: demo-602028134175
slug: add-pdf-invoice-export
project: ledger-api
started: 2026-11-03T16:20:00+00:00
ended: 2026-11-03T18:20:00+00:00
cwd: /home/dev/code/ledger-api
gitBranch: feat/pdf-export
permissionMode: default
model: glm-4.6
user_messages: 1
tool_calls: 4
tools_used: [Bash, Edit, Write]
tool_counts: {"Write": 2, "Edit": 1, "Bash": 1}
token_totals: {"input": 12000, "cache_creation": 24000, "cache_read": 72000, "output": 4000}
turn_count: 1
hour_buckets: {"2026-11-03T16": 4, "2026-11-03T17": 7, "2026-11-03T18": 10}
duration_seconds: 7200
is_subagent: false
---

# Session: add-pdf-invoice-export — 2026-11-03

**Project:** `ledger-api` · **Branch:** `feat/pdf-export` · **Mode:** `default` · **Model:** `glm-4.6`

## Summary

Added PDF export for invoices with WeasyPrint and a Jinja2 template; PDFs are rendered in a background task and cached by invoice revision, so re-downloads are instant.

## Conversation

### Turn 1 — User

Export invoices as PDF. It should look like the HTML preview.

### Turn 1 — Assistant

Reuse the HTML preview template, render with WeasyPrint in a background task, store under `invoices/<id>/<revision>.pdf`. The download endpoint streams the cached file.

**Tools used in this turn:**

- `Write`: ledger/pdf.py
- `Write`: templates/invoice.html
- `Edit`: ledger/routes/invoices.py
- `Bash`: pytest tests/test_pdf.py -q — 4 passed

## Connections

- [[ledger-api]]
- [[WeasyPrint]]
- [[Jinja2]]
- [[BackgroundTasks]]
