---
title: "Session: redis-cluster-failover — 2026-10-27"
type: source
tags: [opencode, session-transcript, demo]
date: 2026-10-27
source_file: raw/sessions/edge-cache/2026-10-27-redis-cluster-failover.md
sessionId: demo-866554593953
slug: redis-cluster-failover
project: edge-cache
started: 2026-10-27T09:45:00+00:00
ended: 2026-10-27T12:27:00+00:00
cwd: /home/dev/code/edge-cache
gitBranch: fix/redis-failover
permissionMode: default
model: gpt-5
user_messages: 1
tool_calls: 4
tools_used: [Bash, Edit, Write]
tool_counts: {"Bash": 2, "Edit": 1, "Write": 1}
token_totals: {"input": 16200, "cache_creation": 32400, "cache_read": 97200, "output": 5400}
turn_count: 1
hour_buckets: {"2026-10-27T09": 4, "2026-10-27T10": 7, "2026-10-27T11": 10, "2026-10-27T12": 6}
duration_seconds: 9720
is_subagent: false
---

# Session: redis-cluster-failover — 2026-10-27

**Project:** `edge-cache` · **Branch:** `fix/redis-failover` · **Mode:** `default` · **Model:** `gpt-5`

## Summary

Debugged cache misses spiking during Redis failovers: the client kept a stale slot map. Enabled `RouteByLatency` with `MaxRedirects`, added a circuit breaker that falls back to the in-memory LRU, and wrote a chaos test with toxiproxy.

## Conversation

### Turn 1 — User

Every Redis failover gives us a minute of 100% misses.

### Turn 1 — Assistant

The client keeps routing to the demoted primary until the slot map refreshes. Refresh on MOVED, add a breaker that degrades to the local LRU, and reproduce with toxiproxy in CI.

**Tools used in this turn:**

- `Bash`: docker compose -f chaos.yml up -d
- `Edit`: store/redis.go
- `Write`: store/breaker.go
- `Bash`: go test ./chaos -run Failover — ok

## Connections

- [[edge-cache]]
- [[Redis]]
- [[CircuitBreaker]]
- [[ChaosTesting]]
