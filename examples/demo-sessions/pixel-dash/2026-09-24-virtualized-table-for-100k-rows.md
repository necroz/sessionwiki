---
title: "Session: virtualized-table-for-100k-rows — 2026-09-24"
type: source
tags: [gemini-cli, session-transcript, demo]
date: 2026-09-24
source_file: raw/sessions/pixel-dash/2026-09-24-virtualized-table-for-100k-rows.md
sessionId: demo-398722992153
slug: virtualized-table-for-100k-rows
project: pixel-dash
started: 2026-09-24T13:40:00+00:00
ended: 2026-09-24T15:52:00+00:00
cwd: /home/dev/code/pixel-dash
gitBranch: perf/table
permissionMode: default
model: gemini-2.5-pro
user_messages: 1
tool_calls: 4
tools_used: [Bash, Edit, Write]
tool_counts: {"Bash": 2, "Write": 1, "Edit": 1}
token_totals: {"input": 13200, "cache_creation": 26400, "cache_read": 79200, "output": 4400}
turn_count: 1
hour_buckets: {"2026-09-24T13": 4, "2026-09-24T14": 7, "2026-09-24T15": 10}
duration_seconds: 7920
is_subagent: false
---

# Session: virtualized-table-for-100k-rows — 2026-09-24

**Project:** `pixel-dash` · **Branch:** `perf/table` · **Mode:** `default` · **Model:** `gemini-2.5-pro`

## Summary

The events table froze with 100k rows. Replaced it with a virtualized table (TanStack Virtual), moved sorting into a Web Worker and memoized row renderers; scroll stays at 60 fps and initial render dropped from 4.1 s to 120 ms.

## Conversation

### Turn 1 — User

The events table is unusable with 100k rows.

### Turn 1 — Assistant

Profile shows 100k DOM rows and sorting on the main thread. Virtualize rows, sort in a worker, memoize cells.

**Tools used in this turn:**

- `Bash`: pnpm add @tanstack/react-virtual
- `Write`: src/workers/sort.worker.ts
- `Edit`: src/tables/EventsTable.tsx
- `Bash`: pnpm bench — render 4100 ms → 120 ms

## Connections

- [[pixel-dash]]
- [[TanStackVirtual]]
- [[WebWorkers]]
- [[Performance]]
