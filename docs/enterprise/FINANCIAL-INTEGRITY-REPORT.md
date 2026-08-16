# Financial Integrity Audit — SDMAS v2

**Status:** VERIFIED
**Date:** 2026-08-16
**Scope:** fees, payments, ledger, transaction logs, reconciliation, refunds, balances, idempotency, audit — application-level AND database-level protections, plus a verdict on the invoice `(subscription_id, period_start)` uniqueness question.

---

## 1. Executive summary

The finance subsystem already carried strong protections: money is stored as
integer minor units (paise), payments/refunds write inside savepoints with
row locks, idempotency keys are unique **per campus** at the DB level, and
the ledger is the idempotency store for refunds. This audit verified each of
the 12 required scenarios against the implementation and the executed test
suite, and closed one verification gap: **no test previously proved that a
REJECTED payment/refund leaves zero side effects** (no ledger row, no audit
entry, fee-due untouched) and **no direct DB-constraint regression test**
existed for `ck_fee_due_amount_paid_range` / `ck_payment_amount_positive`.

Five regression tests were added; all 228 finance tests pass. **No
production-code defect was found.** The invoice uniqueness question is
**already answered**: `UNIQUE(subscription_id, period_start)` is enforced at
the database (migration `038`, fail-closed duplicate scan, plus a dedicated
5-test suite).

---

## 2. Architecture (what the invariants rest on)

- **Money representation** — every amount is an integer in minor units
  (paise). No float anywhere in the financial write path
  (`test_money_fields_are_integers`, receipt formatter).
- **Payment write path** (`PaymentService.record_payment`) —
  1. idempotency-key lookup (miss → proceed)
  2. student active check, fee-due lock (`get_by_id_for_update`, SELECT …
     FOR UPDATE), due↔student match, due-not-paid check, receipt-number
     uniqueness
  3. overpayment pre-check (`amount_paid + amount <= original_amount`)
  4. **savepoint** (`begin_nested`) containing: payment row, fee-due
     balance/status update, ledger journal, audit entry, durable event
  5. `IntegrityError` → if key exists, return the winner; else ConflictError
- **Refund write path** (`PaymentService.record_refund`) — payment row lock
  first (concurrent refunds serialize), idempotency key resolved against the
  **ledger** (mirroring payments), refundable-balance re-read under the
  lock, then a single savepoint with payment state transition, fee-due
  balance reversal, ledger journal, audit.
- **Ledger** (`TransactionLogService.record`) — serializes per student with
  a row lock, always derives `balance_after` from the recomputed sum (no
  stale last-row reads), unique `(campus_id, idempotency_key)`.
- **Audit** — written with `commit=False` inside the same savepoint, so a
  rejected operation rolls back its audit entry along with the ledger row.
- **Tenancy** — fee types/structures/dues/payments/txn-logs/receipts/
  reconciliations all carry `campus_id`; reads are tenant-scoped via
  `assert_tenant_scope`; idempotency keys are scoped **per campus**.

---

## 3. The 12 scenarios — verdicts

| # | Scenario | Mechanism | DB-level? | Test evidence | Result |
|---|---|---|---|---|---|
| 1 | Duplicate payment (same key) | key pre-check + `uq_payment_idempotency_key` | ✅ unique (campus, key) | `test_payment_idempotent_replay_returns_same_payment` | ✅ |
| 2 | Double click | same as #1 — second click resolves to the first payment | ✅ | `test_payment_idempotency_does_not_double_charge` | ✅ |
| 3 | Retry after partial failure | savepoint rollback + key replay; clean retry for a new period | ✅ | `test_retry_after_failed_duplicate_is_clean` (invoice); new `test_concurrent_different_keys_cannot_overpay_due` | ✅ |
| 4 | Duplicate webhook/event | `uq_webhook_event_delivery` (provider, event_id); outbox idempotent handlers | ✅ | `test_webhook_duplicate_delivery_deduped`, `test_payment_event_replay_single_notification` | ✅ |
| 5 | Concurrent payment | row lock + unique key; loser recovers to winner | ✅ | `test_concurrent_same_idempotency_key_single_payment`, new different-key race test | ✅ |
| 6 | Partial failure | single savepoint; failure rolls back payment + fee-due + ledger + audit together | ✅ (savepoint) | **NEW** `test_rejected_payment_leaves_no_side_effects` | ✅ |
| 7 | Rollback | savepoint semantics; no partial state ever visible | ✅ | `test_retry_after_failed_duplicate_is_clean`, ledger invariants suite | ✅ |
| 8 | Refund | payment row lock, ledger-as-idempotency-store, savepoint | ✅ | full/partial/over/zero/unknown/concurrent refund tests | ✅ |
| 9 | Overpayment | app pre-check + `ck_fee_due_amount_paid_range` + `ck_payment_amount_positive` | ✅ | `test_record_payment_overpayment`, webhook overpayment, **NEW** `test_db_rejects_fee_due_amount_out_of_range` | ✅ |
| 10 | Underpayment | explicit `partially_paid` state; ledger records actual amount | — (app) | `test_record_payment_partial`, webhook underpayment | ✅ |
| 11 | Decimal / rounding | integer minor units throughout; receipts render ₹ formatting | ✅ | `test_money_fields_are_integers` | ✅ |
| 12 | Tenant isolation | `campus_id` on every financial row + `assert_tenant_scope`; idempotency keys scoped per campus | ✅ FKs on campuses | receipt/reconciliation/dashboard/idempotency scoping tests + adversarial three-tenant suite | ✅ |

---

## 4. Database-level protections verified (live PostgreSQL)

Constraint inventory on the financial tables (queried from the running DB):

| Table | Constraint | Type | Purpose |
|---|---|---|---|
| `payments` | `ck_payment_amount_positive` | CHECK | amount > 0 |
| `payments` | `ck_payment_refunded_amount_range` | CHECK | 0 ≤ refunded ≤ amount |
| `payments` | `uq_payment_idempotency_key` | UNIQUE (campus_id, key) | per-campus idempotency |
| `payments` | `uq_payment_receipt_number` | UNIQUE | receipt uniqueness |
| `fee_dues` | `ck_fee_due_amount_paid_range` | CHECK | 0 ≤ paid ≤ original |
| `fee_dues` | `uq_fee_due_per_student_structure` | UNIQUE | one due per (student, structure) |
| `transaction_logs` | `uq_transaction_idempotency` | UNIQUE (campus_id, key) | ledger replay protection |
| `invoices` | `uq_invoices_subscription_period` | UNIQUE (subscription_id, period_start) | **no double-billing per period** |
| `usage_records` | `uq_usage_period_metric` | UNIQUE (campus, metric, period) | usage aggregation integrity |
| `webhook_events` | `uq_webhook_event_delivery` | UNIQUE (provider, event_id) | webhook dedup |
| `receipts` | `receipts_receipt_number_key`, `receipts_payment_id_key` | UNIQUE | one receipt per payment/number |
| `subscriptions` | `uq_subscriptions_campus` | UNIQUE (campus_id) | one subscription per tenant |

All were created by Alembic migrations (`004_create_fees`,
`036_harden_finance_ledger`, `038_add_invoice_period_unique`,
`047_scope_idempotency_keys_by_campus`) and verified live against the
running PostgreSQL instance. FKs on `payments.fee_due_id` /
`transaction_logs.payment_id` / `receipts.payment_id` / all `campus_id`
columns are enforced (see the schema-integrity suite,
`tests/test_schema_integrity.py`).

### 4.1 The invoice uniqueness question — ANSWERED

**`UNIQUE(subscription_id, period_start)` is already enforced at the
database level** and should stay there:

- **Migration `038_add_invoice_period_unique`** creates `uq_invoices_subscription_period`
  fail-closed: it scans for duplicate periods first and *aborts* with the
  offending query if any exist — it never silently merges or deletes
  financial records.
- The model (`Invoice.__table_args__`) mirrors the constraint so test
  schemas match production.
- A dedicated suite (`tests/test_finance_security/test_invoice_unique.py`,
  5 tests) proves: normal insert, duplicate rejected by the DB, invariant
  across separate sessions (the realistic worker race), `process_period_end`
  idempotency, and clean retry after a failed duplicate.

No additional work is needed here; the application-level pending-invoice
guard + row lock is complemented by this structural backstop.

---

## 5. Verification gaps closed this pass (new tests)

No production defect was found, but five regression tests were added to
`tests/test_finance_security/test_payments.py` (all pass):

| Test | What it proves |
|---|---|
| `test_rejected_payment_leaves_no_side_effects` | a payment rejected by a business rule (already-paid due) leaves **zero** ledger rows, **zero** audit entries, and an untouched fee-due — even a direct out-of-range mutation is rejected by the DB |
| `test_rejected_refund_leaves_no_side_effects` | a refund exceeding the refundable balance leaves no refund ledger row, no audit entry, payment `refunded_amount=0`, fee-due unchanged |
| `test_db_rejects_fee_due_amount_out_of_range` | `ck_fee_due_amount_paid_range` fires at the **database** with no service code involved |
| `test_db_rejects_non_positive_payment_amount` | `ck_payment_amount_positive` rejects a zero-amount payment at the DB |
| `test_concurrent_different_keys_cannot_overpay_due` | two different idempotency keys racing on one due cannot jointly overpay — the row lock forces the loser to re-read the committed balance and the app pre-check rejects it |

---

## 6. Regression evidence

- `tests/test_finance_security` + `tests/test_fees` + `tests/test_outbox`:
  **228 passed, 0 failed** (4m03s)
- Payment suite incl. the 5 new tests: **21 passed**
- ruff: clean on all changed lines (7 pre-existing findings at untouched
  lines — F401/E741/F841 — left as-is; no new findings introduced)
- Parser/import check: OK

---

## 7. Files changed

- `apps/api/tests/test_finance_security/test_payments.py` — 5 new regression
  tests (217 added lines, 0 deleted)
- `docs/enterprise/FINANCIAL-INTEGRITY-REPORT.md` — this document

No production code required a change; the subsystem's application- and
database-level protections were already correct.

---

## 8. Known limitations (documented, not defects)

- `get_by_id_for_update` (SELECT … FOR UPDATE) is a no-op on SQLite, so the
  concurrent tests model the PostgreSQL lock behavior explicitly (fresh-read
  semantics) rather than relying on the in-memory engine.
- Ledger `balance_before`/`balance_after` are derived from the recomputed
  sum; there is no separate double-entry debit/credit table — the
  `transaction_logs` table is the single source of truth and is covered by
  `test_ledger_invariants.py` (chain consistency, replay, per-student
  serialization).
- Idempotency keys are per-campus by design; two tenants may legitimately
  reuse the same key (verified by `test_payment_idempotency_keys_are_campus_scoped`).

---

## 9. Reproduction commands

```bash
cd apps/api

# Full finance regression (incl. the 5 new atomicity/constraint tests)
uv run pytest tests/test_finance_security tests/test_fees tests/test_outbox -q

# The specific new tests
uv run pytest tests/test_finance_security/test_payments.py -q -k "rejected or db_rejects or concurrent_different"

# Invoice uniqueness suite
uv run pytest tests/test_finance_security/test_invoice_unique.py -q

# Schema-integrity (DB constraints incl. finance tables)
uv run pytest tests/test_schema_integrity.py -q
```

**Verdict:** financial integrity is **VERIFIED** at both the application and
database layers. All 12 mandated scenarios hold; five new tests close the
previously-unproven atomicity and DB-constraint verification gap; the
invoice `(subscription_id, period_start)` uniqueness is enforced at the
database and should remain so.
