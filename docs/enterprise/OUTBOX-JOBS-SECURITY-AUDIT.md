# Outbox & Background-Job Adversarial Audit

**Status:** VERIFIED (one P1 defect found, fixed, regression-tested)

**Date:** 2026-08-12

This document records the adversarial audit of the transactional outbox and
durable job system: the full lifecycle from business transaction → database
commit → outbox record → worker pickup → processing → acknowledgement →
retry → failure → dead-letter → audit/reconciliation.

---

## 1. Lifecycle under test

```
business transaction → DB commit → outbox row (atomic) → worker claim (atomic
UPDATE … RETURNING) → handler delivery → complete → retry w/ backoff →
dead-letter → reaper (stale-processing reclaim)
```

Both durable queues share the same architecture:

| Concern | Job queue (`jobs`) | Outbox (`events/outbox.py`) |
|---|---|---|
| Atomic claim | `UPDATE … WHERE status='pending' RETURNING` | identical pattern |
| Duplicate producer | `uq_jobs_identity_key` | `uq_outbox_events_event_id` |
| Retry | exponential backoff, `max_retries` | exponential backoff, `max_attempts` |
| Dead-letter | `dead_letter` status | `dead_letter` status |
| Crash reaper | yes | yes (`reclaim_stale_processing`) |
| Tenant pinning | `event_context(school_id=job.campus_id)` | `event_context(school_id=…)` at delivery |
| Worker session | committed at end of poll cycle | committed at end of poll cycle |

---

## 2. Findings

### 2.1 `P1` — Partial writes survive a failed job/handler (FIXED)

**Root cause.** `JobService.execute_job` and `OutboxDispatcher.deliver` caught
exceptions but never rolled back the worker session. The session's
`async with` context managers *do* roll back on exception, but the worker's
own `except Exception` blocks swallow the exception, so control never reaches
the context-manager rollback — and the worker commits the session at the end
of its poll cycle. A job that mutated state and then raised therefore leaked
its partial rows into the database (e.g. an orphan ledger row), where a retry
could then duplicate or conflict with them.

**Evidence (reproduced, red tests before fix):**

```
tests/test_async_hardening/test_transactional_safety.py
  test_failed_job_does_not_leak_partial_ledger_write   → FAILED (leak present)
tests/test_outbox/test_adversarial.py
  test_failed_handler_does_not_leak_partial_notification → FAILED (leak present)
```

**Fix.** Both execution paths now run inside a manual SAVEPOINT
(`session.begin_nested()`):

- `apps/api/app/domains/jobs/service.py` — `before_run`/`run`/`after_run`
  run inside the savepoint; on any `BaseException` the savepoint is rolled
  back before the failure path (`on_failure` → audit → `_handle_failure`)
  touches the session, so those bookkeeping writes start clean.
- `apps/api/app/domains/events/outbox.py` — each handler runs inside its own
  savepoint; a poisoned handler cannot leak partial side effects that the
  poll-cycle commit would otherwise persist.

**Commit tolerance.** Some jobs commit internally for progress checkpoints
(e.g. `ReportExportJob` → `process_export_job`). That closes the savepoint, so
rollback/commit become no-ops — the job's own commit defines durability for
that job type. This is documented in the code comments.

**Cancellation safety.** The rollback branch uses `except BaseException`
(not `except Exception`) so `asyncio.CancelledError` during a worker shutdown
also rolls back the savepoint.

**Known limitation (documented, not a defect).** A job that commits
internally and *then* raises leaves any writes made after its last internal
commit in the session — the savepoint is already gone. The backstop is the
existing retry machinery plus idempotency keys (`uq_transaction_idempotency`,
`uq_payments_idempotency_key`, outbox `event_id` uniqueness).

### 2.2 Verified secure (already test-pinned)

- **No lost events** — outbox row commits atomically with the business
  mutation (`publish_durable` uses the caller's session); producer crash is
  safe (`test_event_durability.py`).
- **No duplicate financial effects** — `Payment.idempotency_key` and
  `TransactionLog.idempotency_key` are unique per campus at the DB level
  (`uq_payments_idempotency_key`, `uq_transaction_idempotency`) and
  double-checked in `TransactionLogService.record`; duplicate payment
  requests return the existing receipt (`test_finance_security/`).
- **Repeated webhook / replay** — replaying `PaymentReceivedEvent` creates at
  most one notification thanks to the DB-level `event_key` dedup guard in the
  notification channel (survives restarts and multi-worker delivery).
- **Duplicate outbox event** — pre-check + unique `event_id` collapse to one
  row (`test_outbox/`).
- **Worker crash** — atomic `UPDATE … RETURNING` claim means the row stays
  `processing` and the reaper reclaims/dead-letters it after staleness.
- **Concurrent workers** — race-safe claim tested in
  `test_jobs_multi_worker.py`.
- **Poison message** — unknown event type raises → retries with backoff →
  dead-letters after `max_attempts` (new `test_outbox/test_adversarial.py`).
- **Redis failure / network interruption** — jobs and outbox are
  DB-durable queues with no Redis dependency; delivery retries with backoff.
- **Idempotent enqueue** — `identity_key` returns the existing job row for
  any status (`test_scheduler.py`).
- **Tenant pinning** — a job/event for campus A delivers under
  `event_context(school_id=A)`; a campus-B job cannot touch campus-A data
  (`test_event_durability.py`).

### 2.3 The 12-scenario matrix

| # | Scenario | Result |
|---|---|---|
| 1 | Successful event | Verified — delivered + completed, audit entry |
| 2 | Duplicate event | Verified — collapsed via unique `event_id` |
| 3 | Worker crash mid-delivery | Verified — reaper reclaims stale `processing` rows |
| 4 | API crash after commit | Verified — outbox row committed atomically; no loss |
| 5 | Database rollback | Verified — outbox row rolls back with business tx |
| 6 | Redis failure | Verified — no Redis dependency on the durable path |
| 7 | Network interruption | Verified — retry with backoff; idempotent consumers |
| 8 | Worker restart | Verified — pending rows re-claimed; no double effects |
| 9 | Repeated delivery | Verified — notification `event_key` DB dedup |
| 10 | Concurrent workers | Verified — atomic claim; multi-worker tests green |
| 11 | Poison message | Verified — retry → dead-letter (new test) |
| 12 | Partially completed operation | **FIXED** — SAVEPOINT rollback (new tests) |

---

## 3. Changes

| File | Change |
|---|---|
| `apps/api/app/domains/jobs/service.py` | `execute_job` wraps job body in commit-tolerant SAVEPOINT; `BaseException` rollback |
| `apps/api/app/domains/events/outbox.py` | `deliver` wraps each handler in commit-tolerant SAVEPOINT; `BaseException` rollback |
| `apps/api/tests/test_async_hardening/test_transactional_safety.py` | NEW — failed job does not leak partial ledger write; successful job still commits |
| `apps/api/tests/test_outbox/test_adversarial.py` | NEW — poison message retries then dead-letters; failed handler does not leak partial notification; payment-replay dedup |

---

## 4. Tests executed

| Suite | Result |
|---|---|
| `test_async_hardening` + `test_outbox` + `test_jobs` + `test_domain_events.py` + `test_finance_security` + `test_fees` | **291 passed** |
| New adversarial tests (transactional safety + outbox) | **6 passed** (red before fix, green after) |
| Ruff (E9/F821/F822/F811/I001) on changed files | clean |

Financial idempotency (duplicate payment, repeated webhook, campus-scoped
idempotency keys, retry correctness) was already pinned by
`tests/test_finance_security/` and re-passed in the 291-test regression.

---

## 5. Remaining risks / limitations

- Internal-commit-then-raise jobs have a partial-leak window after their last
  internal commit (mitigated by idempotency keys + retry).
- `_JSON` TypeDecorator lacks `cache_ok` (SQLAlchemy cache-key warning) —
  cosmetic performance note, not a correctness issue.
