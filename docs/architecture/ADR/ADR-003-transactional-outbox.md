# ADR-003 — Transactional Outbox for Durable Events

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Events that must
survive a crash are written to an outbox table in the same database
transaction as the business write, and delivered by the worker.**

## Context

- In-process domain events (`DomainEventDispatcher`) are fast but not
  durable: a crash between business write and handler run loses the event.
- External/subscriber effects (notifications, integrations, future graph/
  simulation sync) need exactly-once-effort delivery.

## Decision

1. `outbox_events` table (unique `event_id`, payload JSONB, status
   `pending/processing/delivered/failed`, attempts counter).
2. Enqueue happens **in the same transaction** as the business write — no
   dual-write window.
3. `OutboxWorker` claims rows atomically (concurrent workers safe),
   delivers via registered handlers, completes on success, records
   failures; stale `processing` rows are reclaimed after
   `OUTBOX_STALE_AFTER`; attempts capped at `OUTBOX_MAX_ATTEMPTS`
   (dead-letter).
4. Handlers are idempotent (dedup keys, unique event_id); financial
   handlers additionally use the webhook idempotency ledger.

## Consequences

- No lost events; no unintended duplicate effects on retry (verified in
  `docs/enterprise/JOBS-OUTBOX-VERIFICATION.md`).
- Outbox replaces Redis-based queues for durability; Redis stays for rate
  limiting/cache only.

## Evidence

- `apps/api/app/domains/events/outbox.py` (repository, dispatcher, worker),
  `outbox_handlers.py`, `app/config.py` (`OUTBOX_*` settings),
  `docs/enterprise/OUTBOX-JOBS-SECURITY-AUDIT.md`.
