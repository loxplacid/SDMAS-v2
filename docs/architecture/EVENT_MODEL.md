# EVENT MODEL — SDMAS v2 Events, Outbox, and Durable Jobs

Date: 2026-08-17 · Source: `apps/api/app/domains/events/`,
`apps/api/app/domains/jobs/`, `apps/api/app/domains/workflow/`,
`apps/api/app/domains/notifications/` (verified).

SDMAS has **two distinct async mechanisms**, both durable and both consumed
by the dedicated worker process:

1. **Domain events** — in-process `DomainEventDispatcher` (fast, same
   process) and, for anything that must survive a crash, the
   **transactional outbox** (`outbox_events` table → `OutboxWorker`).
2. **Durable jobs** — the `jobs` table with a registry of `BaseJob`
   implementations, claimed and executed by the worker, plus a periodic
   **scheduler**.

Rule (AGENTS.md §10): use these existing mechanisms; never invent a second
queue.

---

## 1. Domain events

### 1.1 Core objects (`events/base.py`, `events/dispatcher.py`)

- `DomainEvent` — base class carrying `event_id`, `event_type`,
  `occurred_at`, `correlation_id`, `actor_user_id`, `school_id`, payload.
- `DomainEventDispatcher` — in-process pub/sub: `register(handler)`,
  `dispatch(event)`; async handlers; a failing handler does not break the
  primary operation.
- `event_context()` — propagates correlation/actor/school context so a
  service can publish events carrying the right metadata.

### 1.2 Event catalog (`events/catalog.py`)

The catalog is the **single source of truth** for event-type strings →
class → entity → handlers. Registered types (27 entries, verified):

| Event type | Entity | Notable handlers |
|---|---|---|
| `student.created` / `student.updated` / `student.status_changed` / `student.enrolled` | student / enrollment | audit |
| `attendance.recorded` | attendance | — |
| `attendance.threshold_breached` | student | risk (`handle_attendance_threshold_risk`) |
| `fee.due_created` | fee_due | notification |
| `payment.recorded` | payment | notification |
| `payment.overdue` | fee_due | — |
| `admission.submitted` / `admission.approved` / `admission.rejected` | admission | lifecycle on approve |
| `leave.submitted` / `leave.approved` / `leave.rejected` | leave | — |
| `document.uploaded` / `document.verified` | document | — |
| `workflow.submitted` / `workflow.approved` / `workflow.rejected` / `workflow.cancelled` | workflow | notification on approve |
| `academic_year.rollover_started` / `rollover_completed` / `rollover_failed` | academic_year | notification on complete |
| `batch.operation_completed` | batch | — |
| `admin.important` | system | broadcast |
| `academic_year.rollover_completed_legacy` | academic_year | legacy |

Handlers are registered at startup in `app/main.py` via
`register_domain_event_handlers(event_bus)` (audit, risk, notification,
lifecycle) and `register_all_handlers(notification_dispatcher)`.

### 1.3 Canonical event envelope (`app/platform/events/`)

The canonical envelope (`envelope.py`) is the **platform-level contract**
for every event that crosses a process boundary (outbox row, worker
rehydration, audit, future brokers). It is layered on the existing
`DomainEvent` foundation — nothing is replaced:

| Field | Source (existing event attr) |
|---|---|
| `event_id` | `event_id` (UUID hex, unique) |
| `tenant_id` / `campus_id` | `tenant_id` / `school_id` (SDMAS campus == tenant) |
| `actor_id` | `actor_user_id` / `actor_id` |
| `entity_type` / `entity_id` | `entity_type` / `entity_id` (auto-derived from `*_id` candidates) |
| `event_type` / `event_version` | `event_type` / class `EVENT_VERSION` (default 1) |
| `timestamp` | `occurred_at` (ISO-8601 UTC) |
| `correlation_id` / `causation_id` | same fields; causation filled by the dispatcher (parent event id) |
| `source` | `source` (default `api`; `worker`/`scheduler` set explicitly) |
| `payload` | business fields (JSON-compatible) |
| `integrity` | SHA-256 over the deterministic canonical body (`{algorithm, version, digest}`) |

Guarantees:

- **Deterministic serialization** — `canonical_body_bytes()` emits the
  payload with sorted keys and compact separators; identical logical events
  produce identical bytes (and thus identical digests).
- **Backward compatibility** — reading an event never mutates it; legacy
  notification events map with sensible defaults; `serialize_event` output
  is unchanged (verified by tests).
- **Validation** — `validate_envelope()` checks required fields, types,
  version, timestamp format, and recomputes the integrity digest (tampered
  payloads fail).
- **Traceability** — `correlation_id` spans the whole causal chain;
  `causation_id` names the immediate parent event (set by
  `DomainEventDispatcher` around handler dispatch).

Persistence: the outbox table stores `event_version`, `causation_id` and
`source` (migration `052_add_outbox_canonical_fields`); rehydration
restores them onto the event object.

### 1.4 Notifications as event consumers (`notifications/`)

- `notifications/events.py` — legacy notification event classes with an
  `EventDispatcher` (templates, channels).
- `notifications/handlers.py` — bridges domain events to notifications with
  a **dedup key** per event so repeated delivery cannot create duplicate
  notifications.
- `notifications/channels.py` — `InAppChannel`, `PushChannel`,
  `EmailChannel`, `SMSChannel` behind a `NotificationChannel` protocol.
- `notifications/sse_manager.py` — in-app realtime push per user.
- `notifications/preferences.py` — per-user, per-event enable/disable.
- `notifications/email_service.py` — SendGrid email rendering/delivery.

---

## 2. Transactional outbox (`events/outbox.py`)

The outbox makes **durable, exactly-once-effort delivery** of events to
external/subscriber consumers possible:

### 2.1 Write path

- `OutboxRepository.enqueue(...)` inserts an `OutboxEvent` row
  (`event_id` unique, payload JSONB, status `pending`).
- **Atomicity**: business writes + outbox enqueue happen in the **same
  database transaction** — if the business transaction rolls back, the
  event never exists. There is no dual-write window.

### 2.2 Delivery path (worker)

- `OutboxWorker` (started in-process when `WORKER_IN_PROCESS=true`, or by
  the dedicated worker process) polls every `OUTBOX_POLL_INTERVAL` (default
  2 s) in batches of `OUTBOX_BATCH_SIZE` (10).
- `claim_next` — atomically claims a pending event (status `processing`,
  claimed_at set) using a **row-level claim**; concurrent workers cannot
  claim the same row.
- `deliver` — routes to `OutboxDispatcher` handlers registered by
  `register_outbox_handlers` (`outbox_handlers.py` maps event-type →
  handler).
- `complete(event_id)` — mark `delivered`.
- `fail(event_id, ...)` — record error, increment attempts; after
  `OUTBOX_MAX_ATTEMPTS` (10) the event is marked failed (dead-lettered) and
  is not retried.
- `reclaim_stale_processing` — every `OUTBOX_REAP_INTERVAL` (60 s), events
  stuck in `processing` longer than `OUTBOX_STALE_AFTER` (600 s, worker
  died mid-delivery) are re-queued to `pending`.

### 2.3 Guarantees (verified — see `docs/enterprise/JOBS-OUTBOX-VERIFICATION.md`)

- **No lost events** — enqueue is transactional with the business write;
  stale reclaim recovers crashed deliveries.
- **No duplicate *effects*** — handlers are written idempotently (dedup
  keys, unique `event_id`); financial handlers (payment/webhook paths) use
  the idempotency ledger so a re-delivery cannot double-post.
- **Retry safety** — bounded attempts, backoff via attempts counter, stale
  reclaim, dead-letter state is observable via the API.

---

## 3. Durable jobs (`jobs/`)

### 3.1 Model & lifecycle

- `Job` (`jobs/models.py`) — `job_type`, status (`pending` → `running` →
  `completed` / `failed` / `cancelled`), `payload` JSONB, `result` JSONB,
  `progress` float, `identity_key` (idempotency), `attempts`, `claimed_by`,
  timestamps.
- `JobRepository` (`jobs/repository.py`, `TenantScopedRepository`) —
  `create`, `get_by_identity_key` (idempotent enqueue), `acquire_next`
  (atomic claim), `reclaim_stale_running`, `complete`, `fail`, `cancel`,
  `update_progress`, `list`, `count_pending`.

### 3.2 Registry & implementations

- `registry.py` — `BaseJob` ABC with `before_run` / `run` / `after_run` /
  `on_failure` hooks; `register_job` decorator; `get_job_class(type)`.
- `loader.py` — `load_all_jobs()` imports all job modules at startup.
- Registered jobs include: `MigrationImportJob`
  (`app/domains/migration/import_job.py` — the enterprise migration
  executor), `BillingPeriodEndJob`, `BillingExpirePastDueJob`,
  `CommunicationsScheduledJob`, `CasesEscalationJob` (`periodic_jobs.py`),
  plus job types enqueued by domains (exports, report runs, etc.).

### 3.3 Worker (`jobs/worker.py`)

- `main()` — entrypoint of `Dockerfile.worker`
  (`python -m app.domains.jobs.worker`): loads jobs, registers outbox
  handlers, starts `JobWorker` + `OutboxWorker` (+ `Scheduler` when
  `SCHEDULER_ENABLED`).
- `JobWorker` — poll loop (`WORKER_POLL_INTERVAL`, default 5 s), claims one
  job at a time, executes via `JobService.execute_job`, records audit
  (`_audit_run`), handles failure → retry/dead-letter via `_handle_failure`.
- In-process mode (`WORKER_IN_PROCESS=true`) starts the same workers inside
  the API (development/tests only); production uses the dedicated worker so
  API replicas never compete for the queues.

### 3.4 Scheduler (`jobs/scheduler.py`)

- `Scheduler` — periodic cycle (default 60 s) enqueues recurring jobs using
  **daily / five-minute bucket keys** in Redis so the cycle is idempotent
  across worker restarts and replicas (billing period-end, past-due
  expiration, scheduled message dispatch, case escalation).

---

## 4. Workflow (`workflow/`)

- Approval workflow instances: submit → approve / reject / cancel, with
  matching domain events (`workflow.submitted` etc.) and notifications.
- Used by leave requests, admissions, and general approvals; `ApprovalInbox`
  frontend page surfaces pending items.
- Business rules live in `workflow/service.py`; state transitions emit
  events through the shared dispatcher.

---

## 5. End-to-end trace (as built)

```
API request (e.g. record payment)
  └─ service: business write (payment, ledger)  ┐
  └─ same txn: outbox.enqueue(payment.recorded) ┘  ← atomic
       ↓ (worker polls outbox every 2 s)
  OutboxWorker.claim → deliver → OutboxDispatcher
       └─ notification handler (dedup key) → in-app + email + push
  ── and ──
  service: JobService.create_job(MigrationImportJob, identity_key=…)
       ↓ (worker polls jobs every 5 s)
  JobWorker.claim → execute → progress updates → complete
       └─ audit event on run
```

**Financial path note**: retries and re-deliveries cannot duplicate ledger
effects — payment capture is guarded by the webhook idempotency ledger and
outbox/dues handlers use dedup keys (verified in
`docs/enterprise/FINANCIAL-INTEGRITY-REPORT.md` and
`docs/enterprise/JOBS-OUTBOX-VERIFICATION.md`).

---

## 6. Observability of events/jobs

- Jobs: `GET /jobs` list, status, progress, result; cancel/retry endpoints.
- Outbox: pending/failed counts observable via job/outbox endpoints and
  `count_pending`; failures surface in worker logs and audit.
- Every job run and outbox delivery is audit-logged with an explicit actor
  (`worker`).
