---
title: "Session: helm-chart-for-ledger-api — 2026-10-12"
type: source
tags: [zcode, session-transcript, demo]
date: 2026-10-12
source_file: raw/sessions/infra-stack/2026-10-12-helm-chart-for-ledger-api.md
sessionId: demo-947512634365
slug: helm-chart-for-ledger-api
project: infra-stack
started: 2026-10-12T11:30:00+00:00
ended: 2026-10-12T13:30:00+00:00
cwd: /home/dev/code/infra-stack
gitBranch: feat/helm-ledger
permissionMode: default
model: claude-sonnet-4-6
user_messages: 1
tool_calls: 4
tools_used: [Bash, Write]
tool_counts: {"Write": 2, "Bash": 2}
token_totals: {"input": 12000, "cache_creation": 24000, "cache_read": 72000, "output": 4000}
turn_count: 1
hour_buckets: {"2026-10-12T11": 4, "2026-10-12T12": 7, "2026-10-12T13": 10}
duration_seconds: 7200
is_subagent: false
---

# Session: helm-chart-for-ledger-api — 2026-10-12

**Project:** `infra-stack` · **Branch:** `feat/helm-ledger` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Packaged ledger-api as a Helm chart: Deployment with readiness on `/healthz`, HPA on CPU and request rate, PodDisruptionBudget, and an Alembic migration Job run as a pre-upgrade hook.

## Conversation

### Turn 1 — User

Deploy ledger-api to the cluster with Helm. Migrations must run before the new pods.

### Turn 1 — Assistant

Chart with Deployment, Service, HPA, PDB; migrations as a `pre-upgrade` hook Job with `backoffLimit: 0` so a failed migration blocks the rollout.

**Tools used in this turn:**

- `Write`: charts/ledger-api/templates/deployment.yaml
- `Write`: charts/ledger-api/templates/migrate-job.yaml
- `Bash`: helm lint charts/ledger-api — 0 failed
- `Bash`: helm upgrade --install ledger-api ./charts/ledger-api -n staging — deployed

## Connections

- [[infra-stack]]
- [[ledger-api]]
- [[Helm]]
- [[Kubernetes]]
