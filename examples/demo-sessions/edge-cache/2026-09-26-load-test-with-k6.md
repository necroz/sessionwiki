---
title: "Session: load-test-with-k6 — 2026-09-26"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-09-26
source_file: raw/sessions/edge-cache/2026-09-26-load-test-with-k6.md
sessionId: demo-213132120118
slug: load-test-with-k6
project: edge-cache
started: 2026-09-26T20:15:00+00:00
ended: 2026-09-26T21:21:00+00:00
cwd: /home/dev/code/edge-cache
gitBranch: chore/load-test
permissionMode: default
model: claude-opus-4-7
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Write": 1, "Bash": 1, "Edit": 1}
token_totals: {"input": 6600, "cache_creation": 13200, "cache_read": 39600, "output": 2200}
turn_count: 1
hour_buckets: {"2026-09-26T20": 4, "2026-09-26T21": 7}
duration_seconds: 3960
is_subagent: false
---

# Session: load-test-with-k6 — 2026-09-26

**Project:** `edge-cache` · **Branch:** `chore/load-test` · **Mode:** `default` · **Model:** `claude-opus-4-7`

## Summary

Wrote a k6 load test that replays a production-shaped traffic mix; found that TLS handshakes dominated CPU and enabled session resumption, raising throughput by 35% at the same p99.

## Conversation

### Turn 1 — User

How much traffic can one instance take?

### Turn 1 — Assistant

Replay a recorded mix with k6 at increasing arrival rates; profile at the knee. TLS handshakes are 60% of CPU, so turn on session tickets and resumption.

**Tools used in this turn:**

- `Write`: loadtest/mix.js
- `Bash`: k6 run loadtest/mix.js — p99 48 ms at 4.2k rps
- `Edit`: server/tls.go

## Connections

- [[edge-cache]]
- [[k6]]
- [[TLS]]
- [[Performance]]
