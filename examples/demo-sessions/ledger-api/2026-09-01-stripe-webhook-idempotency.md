---
title: "Session: stripe-webhook-idempotency — 2026-09-01"
type: source
tags: [codex-cli, session-transcript, demo]
date: 2026-09-01
source_file: raw/sessions/ledger-api/2026-09-01-stripe-webhook-idempotency.md
sessionId: demo-287992980054
slug: stripe-webhook-idempotency
project: ledger-api
started: 2026-09-01T14:00:00+00:00
ended: 2026-09-01T15:48:00+00:00
cwd: /home/dev/code/ledger-api
gitBranch: feat/stripe-webhooks
permissionMode: default
model: gpt-5-codex
user_messages: 1
tool_calls: 3
tools_used: [Bash, Edit, Write]
tool_counts: {"Edit": 1, "Write": 1, "Bash": 1}
token_totals: {"input": 10800, "cache_creation": 21600, "cache_read": 64800, "output": 3600}
turn_count: 1
hour_buckets: {"2026-09-01T14": 4, "2026-09-01T15": 7}
duration_seconds: 6480
is_subagent: false
---

# Session: stripe-webhook-idempotency — 2026-09-01

**Project:** `ledger-api` · **Branch:** `feat/stripe-webhooks` · **Mode:** `default` · **Model:** `gpt-5-codex`

## Summary

Made Stripe webhook handling idempotent: every event id is recorded in a `processed_events` table inside the same transaction as the side effect, so retries from Stripe can never double-credit an invoice.

## Conversation

### Turn 1 — User

Stripe retries webhooks. Make sure we never apply the same event twice.

### Turn 1 — Assistant

Insert the event id into `processed_events` (unique) in the same transaction as the invoice update; on a unique-violation, return 200 and skip. Signature verification stays first.

```python
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    event = verify_signature(await request.body(), request.headers)
    try:
        with db.begin():
            db.add(ProcessedEvent(id=event.id))
            apply_event(db, event)
    except IntegrityError:
        return {"status": "duplicate"}   # already handled
    return {"status": "ok"}
```

**Tools used in this turn:**

- `Edit`: ledger/webhooks.py
- `Write`: migrations/versions/0004_processed_events.py
- `Bash`: pytest tests/test_webhooks.py -q — 6 passed

## Connections

- [[ledger-api]]
- [[Stripe]]
- [[Idempotency]]
- [[PostgreSQL]]
