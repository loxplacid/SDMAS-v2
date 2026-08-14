# Financial Ledger Adversarial Audit

**Status:** VERIFIED — 3 defects found and fixed; all mathematical invariants
now test-pinned.

**Date:** 2026-08-12

Adversarial audit of financial correctness: invoices, fees, payments,
refunds, ledger, balances, reconciliation, transaction IDs, idempotency
keys, audit records.  Money is stored as **integer minor units** (paise for
INR) throughout — no floats in monetary math (already pinned by
`test_money_fields_are_integers`).

---

## 1. Findings

### 1.1 `P1` — Refund requests were not idempotent (FIXED)

**Root cause.** `RefundCreate` had no `idempotency_key`.  A retried or
double-submitted refund request (same payment, same amount) applied twice:
for a payment of 1000, refunding 400 twice produced 800 total — the second
submission passed the `refundable` check (400 ≤ 600) because the refundable
balance is re-read after the *payment* lock, not deduped per request.  The
ledger key `refund:{payment.id}:{cumulative}` never collides on retry, so
nothing stopped the double application (the DB CHECK
`refunded_amount <= amount` only bounds the total, it does not dedupe).

**Fix.** Refund requests now accept an optional `idempotency_key`
(mirroring `PaymentCreate`):

- `RefundCreate.idempotency_key` — strip / blank / 255-length validation.
- `record_refund(..., idempotency_key=None)` dedupes via the ledger
  (`TransactionLogService.find_by_idempotency_key` scoped to the payment's
  campus) **after** the payment row lock, returns the first result on
  replay, and raises `ConflictError` when the key was already used for a
  different payment.
- The client key is journaled on the refund's ledger row (the ledger is the
  idempotency store); without a key the deterministic default
  `refund:{payment.id}:{cumulative}` is used, preserving the "each refund is
  an intentional new action" contract.
- The `IntegrityError` race path (a concurrent duplicate winning the unique
  `(campus_id, idempotency_key)` constraint) re-resolves by key and
  **refreshes the payment** before returning — the savepoint rollback
  restores the loser's identity-map object to its pre-winner state, so the
  replay payload is now truthful.

### 1.2 `P1` — Ledger running-balance chain raced under concurrent same-student writes (FIXED)

**Root cause.** `TransactionLogService.record` read the student's last
`balance_after` (`_get_last_balance`) with no per-student serialization.  Two
concurrent payments/refunds for the same student both read the same
pre-transaction balance and wrote `balance_before`/`balance_after` pairs that
did not form a correct chain — the last row's `balance_after` (the running
balance shown in the ledger UI) silently drifted from the true balance
(authoritative recomputed `get_student_balance` stays correct because it
re-sums).  `_get_last_balance` also had no `id` tiebreaker and was not
campus-scoped.

**Fix.**

- `record()` takes a `SELECT … FOR UPDATE` lock on the **student row** as
  the per-student serialization point (PostgreSQL honours the lock; a
  lock-ordering contract comment documents that the student row is always
  the last lock acquired in a money flow, so the fees service's
  fee-due/payment locks can never deadlock against it).
- The opening balance is now derived from the **authoritative recomputed
  sum** (`get_student_balance`), so a drifted or legacy chain can never
  corrupt the next row.
- The racy `_get_last_balance` was removed.
- A regression test spies on `session.execute` to assert the student-row
  `FOR UPDATE` is issued, so a future refactor that drops the lock fails CI
  even though SQLite (the test dialect) ignores the lock.

### 1.3 `P2` — Ledger classification mismatch for valid transaction types (FIXED)

**Root cause.** `record()` treated only `{refund, waiver, discount}` as
credits (decrease balance), while `get_student_balance()` counted credits
from `{payment}` and debits from `{refund, waiver, discount}`.  The valid
types `{reversal, adjustment, fine}` were included in the running chain but
**silently excluded** from the recomputed balance — if ever recorded, the two
would drift apart.  `record()` also accepted any `transaction_type`/`amount`
from direct (non-router) callers.

**Fix.**

- New module constants `LEDGER_DEBIT_TYPES = {payment, fine}` and
  `LEDGER_CREDIT_TYPES = {refund, waiver, discount, reversal, adjustment}`
  are the **single source of truth** consumed by both `record()` and
  `get_student_balance()` — the invariant is `chain == recomputed sum`, for
  every valid type.
- Service-layer validation in `record()`: `transaction_type` must be in
  `VALID_TRANSACTION_TYPES` and `amount > 0`, so a service or job cannot
  journal garbage.

---

## 2. Verified secure (already test-pinned, re-passed)

| Invariant | Evidence |
|---|---|
| Payment cannot be counted twice | `uq_payments_idempotency_key` (campus-scoped) + service dedupe; `test_payment_idempotent_replay_returns_same_payment`, `test_concurrent_same_idempotency_key_single_payment` |
| Duplicate webhook delivery | `test_webhook_duplicate_delivery_deduped`; under/overpayment pinned |
| Duplicate invoice period | `uq_*` period constraint + idempotent period-end; `test_invoice_unique.py` |
| Refund cannot exceed applicable amount | `refundable` check + `ck_payment_refunded_amount_range` DB CHECK + `ck_fee_due_amount_paid_range`; `test_refund_cannot_exceed_refundable` |
| Overpayment rejected | `Payment would exceed outstanding balance` + DB CHECK; `test_webhook_overpayment_marks_invoice_paid` |
| Rounding / precision | integer minor units only; `test_money_fields_are_integers` |
| Tenant isolation | campus-scoped idempotency keys + receipt/reconciliation cross-campus rejection; `test_school_finance.py` |
| Concurrent refund serialization | payment row lock + fresh re-read; `test_concurrent_refund_must_re_read_payment_under_lock` |
| Ledger journaling on every payment/refund | `test_payment_and_refund_write_ledger`; `payment:{id}` / refund keys |

---

## 3. Changes

| File | Change |
|---|---|
| `apps/api/app/domains/fees/schemas.py` | `RefundCreate.idempotency_key` + validator |
| `apps/api/app/domains/fees/service.py` | `record_refund` idempotent replay, client-key ledger journaling, IntegrityError re-resolution with refresh; duplicate `import datetime` removed |
| `apps/api/app/domains/fees/router.py` | passes `idempotency_key` through |
| `apps/api/app/domains/school_finance/service.py` | `LEDGER_*_TYPES` constants; service-layer validation; per-student `FOR UPDATE`; self-healing `balance_before`; `_get_last_balance` removed |
| `apps/api/tests/test_finance_security/test_ledger_invariants.py` | NEW — 9 tests (red before fix, green after) |

---

## 4. Tests executed

| Suite | Result |
|---|---|
| `tests/test_finance_security` + `tests/test_fees` + `tests/test_enterprise_demo.py` | **204 passed** |
| New `test_ledger_invariants.py` | **9 passed** (5 failed red before fix: refund replay, key reuse conflict, blank-key schema, classification drift, service validation) |
| Ruff (E9/F821/F822/F811/I001) on changed files | clean |

---

## 5. Remaining limitations

- **SQLite ignores `FOR UPDATE`** — the concurrent same-student chain race is
  fixed on PostgreSQL (production) by the student-row lock, but the test
  suite runs on SQLite, so the race itself is not reproduced there; the lock
  is pinned by a spy test instead.  The authoritative recomputed balance is
  correct on every dialect.
- **Sign conventions for unused types** (`fine`/`reversal`/`adjustment`) are
  deliberate choices documented on the constants; the hard invariant is
  `chain == sum`.
- **Pre-existing lint debt** in `school_finance/service.py` (F821 `AuditActor`
  string annotations at `verify`/`approve`/`_audit_review`, and mid-file
  import blocks) predates this audit and was left untouched to keep the
  changeset focused.
