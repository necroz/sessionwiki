---
title: "ledger-api"
type: entity
entity_type: project
project: ledger-api
topics: [python, fastapi, postgres, sqlalchemy, stripe, billing, pdf]
description: "Invoicing service in FastAPI and Postgres — money as integer minor units, idempotent Stripe webhooks, exact tax rounding, PDF export."
homepage: "https://example.com/ledger-api"
cache_tier: L2
---

# ledger-api

Billing backend demo. Four sessions across three agents show a service growing from a scaffold to production concerns: idempotency, rounding bugs, and document export.

## Connections

- Python
- FastAPI
- PostgreSQL
- Stripe
