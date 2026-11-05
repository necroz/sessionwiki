---
title: "Session: scaffold-invoice-service — 2026-08-18"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-08-18
source_file: raw/sessions/ledger-api/2026-08-18-scaffold-invoice-service.md
sessionId: demo-346671779290
slug: scaffold-invoice-service
project: ledger-api
started: 2026-08-18T09:10:00+00:00
ended: 2026-08-18T11:40:00+00:00
cwd: /home/dev/code/ledger-api
gitBranch: main
permissionMode: default
model: claude-sonnet-4-6
user_messages: 2
tool_calls: 5
tools_used: [Bash, Edit, Write]
tool_counts: {"Write": 2, "Bash": 2, "Edit": 1}
token_totals: {"input": 15000, "cache_creation": 30000, "cache_read": 90000, "output": 5000}
turn_count: 2
hour_buckets: {"2026-08-18T09": 4, "2026-08-18T10": 7, "2026-08-18T11": 10}
duration_seconds: 9000
is_subagent: false
---

# Session: scaffold-invoice-service — 2026-08-18

**Project:** `ledger-api` · **Branch:** `main` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Bootstrapped the invoicing service: FastAPI app factory, SQLAlchemy 2.0 models for customers, invoices and line items, Alembic baseline migration, and a pytest fixture that spins up Postgres in Docker. Money is stored as integer minor units from day one.

## Conversation

### Turn 1 — User

Scaffold a FastAPI service for invoices. Postgres, SQLAlchemy 2.0, Alembic. Money must never be a float.

### Turn 1 — Assistant

Plan: app factory in `ledger/app.py`, typed models in `ledger/models.py`, amounts as `BIGINT` minor units plus an ISO-4217 currency column, Alembic baseline, Docker-based Postgres fixture for tests.

```python
class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(default=1)
    unit_amount: Mapped[int]  # minor units (cents)
    currency: Mapped[str] = mapped_column(String(3))
```

**Tools used in this turn:**

- `Write`: ledger/app.py
- `Write`: ledger/models.py
- `Bash`: alembic init migrations — exit 0

### Turn 2 — User

Add the line-item total as a computed column.

### Turn 2 — Assistant

Done as a SQLAlchemy `column_property` summing `quantity * unit_amount`; invoice totals are derived, never stored, so they cannot drift. 9 tests pass.

**Tools used in this turn:**

- `Edit`: ledger/models.py — column_property for totals
- `Bash`: pytest -q — 9 passed

## Connections

- [[ledger-api]]
- [[FastAPI]]
- [[SQLAlchemy]]
- [[Alembic]]
- [[MoneyAsMinorUnits]]
