# SDMAS v2 — Roadmap

## Status

The v1 → v2 migration is complete (see `docs/migration.md`). This roadmap
tracks the **current** v2 system: what is shipped today and what is planned
next. It reflects actual behavior, not intended behavior.

## Shipped

- **Backend** (`apps/api/`)
  - FastAPI + SQLAlchemy 2 (async) + Pydantic v2 + Alembic
  - Domains: student, academic, academic_ops, attendance, fees, billing,
    school_finance, admission, analytics, reports/report_builder/report_cards,
    notifications, jobs, workflow, leave, documents, audit, class_360,
    student_360, teacher_360, student_portal, parent, command_center, timeline
  - JWT auth (access + refresh), RBAC permissions, platform roles
  - Structural multi-tenancy (tenant → campus scoping at the repository layer)
  - Event system (domain events + outbox), background jobs, audit trail
  - Payment integration (Razorpay) with HMAC-verified webhooks and idempotency
- **Web** (`apps/web/`): React + Vite + TypeScript, PWA, dark mode,
  dashboards, student/teacher 360, report cards, notifications, risk center
- **Mobile** (`apps/mobile/`): Expo / React Native
- **Infrastructure**: Docker Compose (dev/staging/prod), Nginx, Prometheus,
  Grafana, OpenTelemetry, backup/restore/deploy scripts

## Next (in priority order)

1. **Billing worker scheduling** — wire `process_period_end` /
   `expire_past_due` into a scheduled worker (cron / Celery beat / APScheduler)
   so subscription billing cycles actually run on time.
2. **Invoice uniqueness at the DB layer** — add a
   `(subscription_id, period_start)` UNIQUE constraint on `invoices` to make
   double-invoicing structurally impossible (currently guarded by app-layer row
   locks).
3. **Tenant-scope remaining reads** — finish converting any service-level
   queries that bypass `TenantScopedRepository` (audit queries, jobs, exports)
   to the canonical scoped pattern.
4. **Webhook ordering** — handle out-of-order payment events (e.g.
   `payment.failed` arriving after `payment.captured`) via event-version or
   state-machine guards.
5. **Financial audit coverage** — add audit entries for invoice/subscription
   state transitions (currently only webhook deliveries are audited).

## Known limitations

See `KNOWN_LIMITATIONS.md` for the authoritative, maintained list.
