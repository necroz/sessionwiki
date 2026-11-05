---
title: "Session: argo-cd-app-of-apps — 2026-10-16"
type: source
tags: [zcode, session-transcript, demo]
date: 2026-10-16
source_file: raw/sessions/infra-stack/2026-10-16-argo-cd-app-of-apps.md
sessionId: demo-205721047080
slug: argo-cd-app-of-apps
project: infra-stack
started: 2026-10-16T09:30:00+00:00
ended: 2026-10-16T11:00:00+00:00
cwd: /home/dev/code/infra-stack
gitBranch: feat/argocd
permissionMode: default
model: glm-4.6
user_messages: 1
tool_calls: 3
tools_used: [Bash, Write]
tool_counts: {"Write": 2, "Bash": 1}
token_totals: {"input": 9000, "cache_creation": 18000, "cache_read": 54000, "output": 3000}
turn_count: 1
hour_buckets: {"2026-10-16T09": 4, "2026-10-16T10": 7}
duration_seconds: 5400
is_subagent: false
---

# Session: argo-cd-app-of-apps — 2026-10-16

**Project:** `infra-stack` · **Branch:** `feat/argocd` · **Mode:** `default` · **Model:** `glm-4.6`

## Summary

Bootstrapped Argo CD with the app-of-apps pattern: one root Application per environment that syncs every service chart, with automated sync and self-heal in staging and manual sync in prod.

## Conversation

### Turn 1 — User

Stop deploying with helm from laptops.

### Turn 1 — Assistant

Argo CD installed by Terraform, a root app per environment pointing at `apps/<env>`, auto-sync with self-heal in staging, manual in prod.

**Tools used in this turn:**

- `Write`: argocd/root-staging.yaml
- `Write`: apps/staging/ledger-api.yaml
- `Bash`: argocd app sync root-staging — Synced

## Connections

- [[infra-stack]]
- [[ArgoCD]]
- [[GitOps]]
- [[ledger-api]]
