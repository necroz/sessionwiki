---
title: "Session: stale-while-revalidate — 2026-09-10"
type: source
tags: [opencode, session-transcript, demo]
date: 2026-09-10
source_file: raw/sessions/edge-cache/2026-09-10-stale-while-revalidate.md
sessionId: demo-621475971874
slug: stale-while-revalidate
project: edge-cache
started: 2026-09-10T10:15:00+00:00
ended: 2026-09-10T12:39:00+00:00
cwd: /home/dev/code/edge-cache
gitBranch: feat/swr
permissionMode: default
model: claude-sonnet-4-6
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Edit": 1, "Write": 1, "Bash": 1}
token_totals: {"input": 14400, "cache_creation": 28800, "cache_read": 86400, "output": 4800}
turn_count: 1
hour_buckets: {"2026-09-10T10": 4, "2026-09-10T11": 7, "2026-09-10T12": 10}
duration_seconds: 8640
is_subagent: false
---

# Session: stale-while-revalidate — 2026-09-10

**Project:** `edge-cache` · **Branch:** `feat/swr` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Implemented `stale-while-revalidate` in the Go caching proxy: stale entries are served immediately while a single background refresh per key runs under `singleflight`, so a hot key never stampedes the origin.

## Conversation

### Turn 1 — User

Add stale-while-revalidate. Origin must not get a thundering herd.

### Turn 1 — Assistant

Serve stale within the SWR window, trigger one refresh per key through `singleflight.Group`, and cap refresh concurrency with a semaphore.

```go
func (c *Cache) serve(w http.ResponseWriter, r *http.Request, key string) {
	entry, ok := c.store.Get(key)
	if ok && entry.Fresh(time.Now()) {
		entry.WriteTo(w)
		return
	}
	if ok && entry.WithinSWR(time.Now()) {
		entry.WriteTo(w) // serve stale now
		go c.group.Do(key, func() (any, error) { return c.refresh(key, r) })
		return
	}
	c.fetchAndStore(w, r, key)
}
```

**Tools used in this turn:**

- `Edit`: cache/handler.go
- `Write`: cache/refresh.go
- `Bash`: go test ./... -race — ok

## Connections

- [[edge-cache]]
- [[Go]]
- [[Singleflight]]
- [[StaleWhileRevalidate]]
