---
title: "Session: github-actions-oidc-deploy — 2026-09-14"
type: source
tags: [copilot-cli, session-transcript, demo]
date: 2026-09-14
source_file: raw/sessions/infra-stack/2026-09-14-github-actions-oidc-deploy.md
sessionId: demo-042235809631
slug: github-actions-oidc-deploy
project: infra-stack
started: 2026-09-14T13:20:00+00:00
ended: 2026-09-14T14:26:00+00:00
cwd: /home/dev/code/infra-stack
gitBranch: feat/oidc-deploy
permissionMode: default
model: gpt-5
agent: copilot-cli
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Write": 1, "Edit": 1, "Bash": 1}
token_totals: {"input": 6600, "cache_creation": 13200, "cache_read": 39600, "output": 2200}
turn_count: 1
hour_buckets: {"2026-09-14T13": 4, "2026-09-14T14": 7}
duration_seconds: 3960
is_subagent: false
---

# Session: github-actions-oidc-deploy — 2026-09-14

**Project:** `infra-stack` · **Branch:** `feat/oidc-deploy` · **Mode:** `default` · **Model:** `gpt-5`

## Summary

Replaced long-lived AWS keys in CI with GitHub Actions OIDC: an IAM role trusted only for this repo's `main` branch and environment, scoped to the deploy bucket and the EKS cluster.

## Conversation

### Turn 1 — User

Get rid of the AWS access keys in our GitHub secrets.

### Turn 1 — Assistant

Create an OIDC provider and a role whose trust policy pins `repo:<org>/infra-stack:environment:prod`. The workflow uses `aws-actions/configure-aws-credentials` with `role-to-assume`.

**Tools used in this turn:**

- `Write`: iam/github-oidc.tf
- `Edit`: .github/workflows/deploy.yml
- `Bash`: terraform apply -target=module.github_oidc — 3 added

## Connections

- [[infra-stack]]
- [[GitHubActions]]
- [[OIDC]]
- [[LeastPrivilege]]
