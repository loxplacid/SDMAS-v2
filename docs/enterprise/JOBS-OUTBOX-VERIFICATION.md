# JOBS-OUTBOX-VERIFICATION.md

Transactional outbox + durable background job verification under failure.
Date: 2026-08-16 · Verdict: **VERIFIED** (no production-code defect found; two
verification gaps closed with new regression tests)

---

## 1. Architecture under test

```
business transaction  ──►  database commit  ──►  outbox row (pending)
                                                        │
                                              claim_next()  (atomic claim)
                                                        │
                                              worker delivers (handler)
                                                        │
                                                   complete() / fail()
```

* **Storage**: PostgreSQL only. `outbox_events` table with an explicit state
  machine — `pending → processing → completed` and `processing → dead_letter`
  (or `pending` again after reaper reclaim). States: `pending`, `processing`,
  `completed`, `dead_letter`.
* **Claiming**: `claim_next()` atomically claims a pending row (`processing`)
  so two workers can never deliver the same row; delivery is at-least-once.
* **Retry / dead-letter**: a failing handler records `last_error` and a
  backoff (`next_attempt_at`); after `max_attempts` the row is dead-lettered —
  never silently dropped.
* **Reaper**: `reclaim_stale_processing()` requeues rows stuck in
  `processing` past a staleness window, and dead-letters rows that have also
  exhausted their retry budget. Both branches write an observable `last_error`
  reason.
* **Redis** is used **only** by the distributed rate limiter — it is *not* in
  the outbox/jobs delivery path. A Redis outage therefore cannot lose or
  duplicate events; its only blast radius is login/endpoint throttling, which
  fails open by default (`503` only when `RATE_LIMIT_FAIL_CLOSED=true`).

## 2. The 12 scenarios — evidence

| # | Scenario | How it is guaranteed | Test evidence |
|---|----------|---------------------|---------------|
| 1 | Normal event | publish → claim → deliver → complete | `test_event_survives_api_restart`, outbox deliver tests |
| 2 | Duplicate event | consumer dedup on `event_key` (e.g. notifications); delivery replay proven idempotent | `test_replay_delivers_notification_exactly_once` |
| 3 | Worker crash | row stays `processing`; reaper requeues; fresh worker delivers; exactly-once effect | `test_crashed_delivery_is_reclaimed_and_redelivered`, `test_crash_reclaim_redeliver_exactly_once` (new) |
| 4 | API crash | event persisted in the outbox table inside the business transaction — survives process restart | `test_event_survives_api_restart` |
| 5 | Database rollback | outbox row shares the business transaction; rollback removes it (no ghost side effects) | `test_rolled_back_transaction_loses_event` |
| 6 | Redis failure | Redis is not in the delivery path; rate limiter fails open (`200`) / fail-closed (`503`), never `500` | `test_login_fails_open_when_redis_down`, `test_login_fails_closed_when_redis_down` (new) |
| 7 | Network interruption | retry state machine (`attempts`, `next_attempt_at`, `last_error`) survives; backoff re-attempts | `test_dead_letter_after_max_attempts` (backoff assertions) |
| 8 | Worker restart | delivery is claimed from the DB — a new worker picks up where the old one stopped | `test_crashed_delivery_is_reclaimed_and_redelivered` |
| 9 | Repeated delivery | at-least-once delivery + consumer idempotency (dedup on `event_key`); replay produces exactly one notification | `test_replay_delivers_notification_exactly_once` |
| 10 | Concurrent workers | atomic claim — one winner per row | `test_delivery_claim_is_atomic_across_workers` |
| 11 | Poison message | handler raises → `fail()` records error + backoff → dead-letter after max attempts (never dropped) | `test_dead_letter_after_max_attempts` |
| 12 | Partially completed operation | delivery effect + `complete()` are committed together; a crash mid-delivery is reclaimed and re-delivered exactly-once | `test_crash_reclaim_redeliver_exactly_once` (new) |

## 3. Financial idempotency under retry

Retries cannot create duplicate financial effects because:

* financial writes (payments, refunds, ledger) are committed in the same
  transaction as their outbox row (no event exists without its effect);
* consumers dedup on `event_key` (proven for notifications);
* payment/ledger idempotency keys are enforced at DB level (see
  `FINANCIAL-INTEGRITY-REPORT.md` for the duplicate-payment / duplicate-webhook
  proofs).

## 4. Observability of recovery

Reclaim and reaper-dead-letter write **distinct, queryable reasons**:

* requeued: `"Reclaimed: worker stopped before completion"`
* dead-lettered: `"Reclaimed after max attempts: worker stopped before completion"`
* handler failure: the handler's error message in `last_error`

`test_reaper_records_observable_reasons` (new) asserts both reasons are
recorded — recovery is observable, not silent.

## 5. Gaps found and closed (this pass)

No production-code defect was found. Two **verification gaps** were closed:

| Gap | Why it mattered | Fix |
|-----|-----------------|-----|
| End-to-end crash → reclaim → redeliver → exactly-once loop was not covered in one test (only the pieces separately) | the full recovery path could regress without any single test failing | `test_crash_reclaim_redeliver_exactly_once` |
| Reaper `last_error` reasons were never asserted | operators could not be confident recovery is observable | `test_reaper_records_observable_reasons` |
| Endpoint-level Redis-outage behavior (login) was untested — only the limiter class in isolation | a production Redis restart must degrade login gracefully (never `500`) | `test_login_fails_open_when_redis_down`, `test_login_fails_closed_when_redis_down`, `test_login_other_endpoints_unaffected_by_limiter_outage` |

## 6. Tests executed

```
uv run pytest tests/test_async_hardening tests/test_outbox tests/test_jobs \
             tests/test_domain_events.py tests/test_security_acquisition -q
```

**Result: 179 passed, 0 failed** (305.7 s). Includes the new tests above.
`ruff check` clean on both changed test files.

## 7. Files changed (this pass)

* `tests/test_async_hardening/test_event_durability.py` — +2 tests
  (crash-reclaim-redeliver exactly-once; reaper observability); removed a
  pre-existing unused import.
* `tests/test_security_acquisition/test_redis_rate_limiter.py` — +3 endpoint-level
  Redis-outage tests.

## 8. Reproduction commands

```bash
# New regression tests
uv run pytest tests/test_async_hardening/test_event_durability.py -q
uv run pytest tests/test_security_acquisition/test_redis_rate_limiter.py -q

# Full jobs/outbox/events regression
uv run pytest tests/test_async_hardening tests/test_outbox tests/test_jobs \
             tests/test_domain_events.py tests/test_security_acquisition -q
```

## 9. Known limitations (documented, accepted)

* Delivery is **at-least-once**; exactly-once is achieved by consumer
  idempotency (`event_key` dedup), not by the transport. Every handler must
  be idempotent — enforced by convention + the dedup tests.
* The in-memory rate limiter is per-process (dev); production uses the
  Redis-backed limiter, which is fail-open by default. Operators who prefer
  strictness over availability can set `RATE_LIMIT_FAIL_CLOSED=true` (then a
  Redis outage yields deliberate `503`s, never `500`s).
