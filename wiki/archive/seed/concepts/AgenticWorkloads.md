---
title: "Agentic Workloads"
type: concept
tags: [llm, agents, workloads]
last_updated: 2026-04-23
sources: []
confidence: 0.55
lifecycle: archived
archived: 2026-11-09
archive_reason: "demo seed page from the upstream template; not derived from sessions (tasks card 10)"
---

# Agentic Workloads

Long-running LLM-driven tasks that involve tool use, iterative
reasoning, and heavy context reuse across many turns — as opposed to
one-shot completions. Examples: coding agents that edit files and run
tests, research agents that browse and synthesise, customer support
agents that chain tool calls to resolve tickets.

Cost economics differ from chat: prompt-caching reads dominate total
spend because the same system prompt, tool schemas, and prior-turn
history are re-sent on every iteration.

## Connections

- [[ClaudeSonnet4]] — current primary model choice for this use case
- [[CachePricing]] — why agentic workloads are so sensitive to cache cost
