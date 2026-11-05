---
title: "Session: cache-key-normalization — 2026-09-17"
type: source
tags: [opencode, session-transcript, demo]
date: 2026-09-17
source_file: raw/sessions/edge-cache/2026-09-17-cache-key-normalization.md
sessionId: demo-629394716828
slug: cache-key-normalization
project: edge-cache
started: 2026-09-17T10:05:00+00:00
ended: 2026-09-17T10:53:00+00:00
cwd: /home/dev/code/edge-cache
gitBranch: fix/cache-keys
permissionMode: default
model: claude-sonnet-4-6
user_messages: 1
tool_calls: 2
tools_used: [Bash, Edit]
tool_counts: {"Edit": 1, "Bash": 1}
token_totals: {"input": 4800, "cache_creation": 9600, "cache_read": 28800, "output": 1600}
turn_count: 1
hour_buckets: {"2026-09-17T10": 4}
duration_seconds: 2880
is_subagent: false
---

# Session: cache-key-normalization — 2026-09-17

**Project:** `edge-cache` · **Branch:** `fix/cache-keys` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Normalized cache keys: query parameters are sorted, tracking parameters (utm_*, fbclid) are dropped, and `Vary` headers are folded into the key. Hit ratio on the marketing routes went from 41% to 78%.

## Conversation

### Turn 1 — User

Marketing pages barely hit the cache.

### Turn 1 — Assistant

Every utm variant is a separate key. Sort params, strip tracking params from an allow-list config, include only the headers listed in `Vary`.

**Tools used in this turn:**

- `Edit`: cache/key.go
- `Bash`: go test ./cache -run Key — ok

## Connections

- [[edge-cache]]
- [[CacheKeys]]
- [[HTTPVary]]
