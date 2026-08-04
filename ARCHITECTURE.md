# SDMAS v2 — Architecture

This document describes the **actual** system. It is the single source of
truth for how SDMAS v2 is structured today.

## Overview

SDMAS v2 is a multi-tenant school data-management platform delivered as three
applications in one monorepo:

| App | Path | Stack |
|---|---|---|
| API | `apps/api` | Python 3.11+, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, pydantic-settings |
| Web | `apps/web` | React + Vite + TypeScript, PWA, dark mode |
| Mobile | `apps/mobile` | Expo / React Native |
| Worker | `apps/api/Dockerfile.worker` | Separate process consuming the jobs table and the event outbox |

The canonical runtime is **PostgreSQL 16 + Redis 7 + API + Worker + Web**,
orchestrated with Docker Compose (`infrastructure/docker/`) and operated via
the root `Makefile`.

## API application structure (`apps/api/app`)

```
app/
├── config.py                    # Pydantic-settings configuration (env + .env)
├── main.py                      # FastAPI app: lifespan, middleware chain, routers
├── core/
│   ├── exceptions.py            # Canonical exception hierarchy
│   ├── error_handlers.py        # HTTP mapping for domain exceptions
│   ├── pagination.py            # Pagination primitives (Page, PaginationParams)
│   ├── security/                # auth_gate (default-deny), headers, token helpers
│   ├── observability/           # JSON logging, OpenTelemetry, /health /ready /metrics
│   └── secrets.py               # Secrets backends (env / Vault)
├── infrastructure/
│   └── database.py              # Async engine, session factory, get_session
├── multi_tenant/                # Canonical tenant framework (see TENANCY.md)
│   ├── models.py                # TenantContext (scoped / platform / unscoped)
│   ├── registry.py              # Model classification (tenant-owned vs platform)
│   ├── repository.py            # TenantScopedRepository (query-construction scoping)
│   ├── guards.py                # effective_campus_id / assert_tenant_scope / inject_campus
│   ├── dependencies.py          # require_tenant_context / get_current_tenant
│   ├── middleware.py            # Tenant context resolution per request
│   └── service_mixin.py         # Shared service helpers
└── domains/                     # 33 domain modules, each with models/schemas/
                                 # repository/service/router + domain events
```

### Request lifecycle

1. **Auth gate** (outermost) — every request must carry a valid bearer token
   unless the path is on the public allowlist (login, health, webhooks, …);
   otherwise **401 fail-closed**.
2. **Security headers** + **observability** middleware (request/correlation
   IDs, latency metrics).
3. **Tenant middleware** — resolves the caller's `TenantContext` from the
   token and `user_school_memberships`.
4. **Audit middleware** — records mutating requests to the audit log.
5. **Router / service / repository** — tenant scoping is applied at
   *query-construction time* (see TENANCY.md); resource-level guards run in
   routers.
6. Domain exceptions map to HTTP via `error_handlers.py`
   (`NotFoundError → 404`, `ConflictError → 409`, `ValidationError → 422`,
   `AuthenticationError → 401`, `AuthorizationError → 403`,
   `PaymentRequiredError → 402`).

### Configuration

Single source: `app/config.py` (`Settings(BaseSettings)`), read from
environment variables and `.env` (template: `.env.example`). Notable groups:
app identity, environment, database (`DATABASE_URL`), Redis, JWT, CORS,
Razorpay (`razorpay_key_id/secret/webhook_secret`), outbox/worker tuning,
observability, and domain thresholds (e.g. `attendance_low_threshold`).

### Migrations

Alembic (`apps/api/alembic/`), **41 migrations** today. Migration history is
chain `001` → `036+`; production DDL is applied via `make migrate`
(`alembic upgrade head`). Tests use `Base.metadata.create_all` on SQLite.

## Domain architecture

Each domain (e.g. `fees`, `billing`, `audit`, `jobs`, `attendance`) follows
the same shape:

- `models.py` — SQLAlchemy 2 mapped classes (money stored as integer minor
  units; tenant-owned rows carry `campus_id`).
- `schemas.py` — Pydantic request/response contracts (`from_attributes=True`).
- `repository.py` — data access, subclassing `TenantScopedRepository` for
  tenant-owned data.
- `service.py` — business logic + state transitions (e.g. payment
  `completed → partially_refunded → refunded`).
- `router.py` — HTTP endpoints; permissions + tenant guards as dependencies.
- Domain events are emitted to the in-process event bus / notification
  dispatcher and (for durable work) the outbox.

Cross-cutting domains:

- `auth` — registration, login, JWT access/refresh, users, roles, permissions
  (see AUTHORIZATION.md).
- `multi_tenant` — the tenant framework (see TENANCY.md).
- `events` + `notifications` — in-process event bus, outbox, notification
  dispatcher (email/push).
- `jobs` — durable background jobs; consumed by the **worker process**.
- `audit` — append-only audit log for mutations, logins, and webhooks.
- `billing` + `school_finance` — subscriptions/invoices/Razorpay webhooks and
  receipts/reconciliation/transaction ledger.

### Background workers

Production runs a dedicated worker (`Dockerfile.worker`) that polls the
**jobs** table and the **event outbox**. The API process only starts
in-process workers when `WORKER_IN_PROCESS` is true (development/tests), so
scaling API replicas never competes for the same queues.

## Frontend (`apps/web`)

React + Vite + TypeScript SPA (PWA). Pages: dashboard, login, profile, and
feature pages (student/teacher 360, risk center, command center, timeline,
report cards, notifications). Cross-cutting hooks: `use-auth`, `use-theme`,
`use-permission`, `use-campus`, `use-export`, `use-global-search`,
`use-smart-search`, `use-keyboard-shortcut`, `use-nav-persistence`. The Vite
dev server proxies `/api` to the API.

## Mobile (`apps/mobile`)

Expo React Native app with auth context, typed API client, theme tokens, and
push notifications; shares the same API.

## Infrastructure

- **Docker Compose** — `development`, `staging`, `production` variants; base
  file defines Postgres, Redis, and API.
- **Nginx** — reverse proxy, SSL termination, security headers, rate limits.
- **Monitoring** — Prometheus + Grafana (provisioned datasources/alerts) and
  an OpenTelemetry Collector; the API exposes `/health`, `/ready`, `/metrics`.
- **Ops scripts** (`infrastructure/scripts/`) — deploy, rollback, backup,
  restore, seed, init-db.

## Testing

- **API**: pytest + pytest-asyncio + httpx (in-memory SQLite), **~1,100
  tests** covering domains, multi-tenant isolation (a dedicated security
  suite), finance/webhook security, permissions, audit, and jobs. PostgreSQL
  integration tests (Testcontainers) are gated behind `@pytest.mark.integration`.
- **Web**: vitest + Testing Library.
- **JS/Python v1**: archived at `_archive/legacy-v1/` — no longer run.

## Related docs

- [`SECURITY.md`](SECURITY.md) — auth, tenant isolation, webhooks, secrets.
- [`AUTHORIZATION.md`](AUTHORIZATION.md) — permission model & roles.
- [`TENANCY.md`](TENANCY.md) — the tenant framework in depth.
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — environments, scaling, backup.
- [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — current gaps & risks.
