# ADR-005 — Money as Integer Minor Units

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **All monetary
values are stored as integer minor units (paise/cents), never floats.**

## Context

- Financial correctness is a critical invariant; float arithmetic causes
  rounding drift (payments, ledger, reconciliation).
- The legacy system and several domains carry money amounts.

## Decision

1. Money columns are integers in minor units (e.g. `amount_minor`),
   converted to/from rupees in the API layer.
2. Financial operations use the existing fees/school_finance services with
   idempotency keys, webhook idempotency ledger, and reconciliation;
   DB-level unique constraints protect invoice/dues invariants.
3. Any amount conversion is explicit at the boundary; never implicit float.

## Consequences

- No decimal drift; deterministic rounding; ledger totals reconcile
  (verified in `docs/enterprise/FINANCIAL-INTEGRITY-REPORT.md`).
- Client-facing values are converted to decimal only for display/IO.

## Evidence

- `apps/api/app/domains/fees/models.py`, `app/domains/school_finance/`,
  `app/domains/billing/` (webhook amount handling, fail-closed on
  missing/unparseable amounts), `docs/enterprise/FINANCIAL-LEDGER-AUDIT.md`.
