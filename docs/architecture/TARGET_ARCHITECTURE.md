# TARGET ARCHITECTURE — SDMAS v2

Date: 2026-08-17 · This document separates **CURRENT** (verified in the
repository), **IN PROGRESS** (core implemented, not fully wired), and
**PLANNED** (design spec only). Nothing below that is not implemented or
speced in the repository is presented as shipped.

Related: `DOMAIN_MAP.md` (what exists), `ARCHITECTURE.md` (root, canonical
CURRENT description), `docs/GRAPH_LAYER.md`, `docs/SIMULATION_ENGINE.md`,
`docs/OPTIMIZATION_ENGINE.md`, `docs/TEMPORAL_DATABASE_V3.md` (design specs),
`KNOWN_LIMITATIONS.md` (honest gaps).

---

## 1. CURRENT — the running system (verified)

### 1.1 Runtime topology

```
                       ┌──────────────────────────────┐
   Browser (React SPA) │  nginx (reverse proxy)       │
      │                │  /api/* → api:8000           │
      │                │  /auth/* → api:8000          │
      │                │  /*      → web:8080 (SPA)    │
      ▼                └──────────────┬───────────────┘
   apps/web (React 19 + Vite, PWA)    │
      │   /api/*, /auth/* (bare)      │
      ▼                               ▼
   apps/api (FastAPI, uvicorn) ───► PostgreSQL 16 (asyncpg)
      │                                 ▲
      │  jobs table + outbox_events ────┤  (same DB, one transaction)
      ▼                                 │
   worker (Dockerfile.worker) ──────────┘
      │  polls jobs table + outbox      │
      └── Redis 7 (rate limits, cache)  │
      └── SendGrid (email)              │
      └── Razorpay (payments)           │
```

- **API**: FastAPI + SQLAlchemy 2 (async) + Pydantic v2; single process per
  replica; `/health`, `/ready`, `/metrics` exposed; docs disabled in
  production (`ENVIRONMENT=production`).
- **Worker**: `python -m app.domains.jobs.worker` — a background process, not
  a web server; **no HTTP port**, truthful `HEALTHCHECK NONE`; the sole
  consumer of the jobs table and event outbox in production
  (`WORKER_IN_PROCESS=false` default). Periodic scheduler runs inside the
  worker (`SCHEDULER_ENABLED=true`).
- **Web**: React 19 SPA, lazy-loaded routes, PWA. API client handles
  access/refresh rotation and in-flight GET dedup.
- **Mobile**: Expo / React Native with auth context, typed API client, theme
  tokens, push-token registration; shares the same API.
- **PostgreSQL 16** is the source of truth; **Redis 7** is used for rate
  limiting and cache.
- **Nginx** (dev): serves the SPA and proxies `/api/`, `/auth/`, docs,
  health; content-negotiates shared SPA/API prefixes (`/students`,
  `/attendance`, `/migration`, `/admin`) by `Accept: text/html` vs JSON.

### 1.2 Request lifecycle (CURRENT)

1. **Auth gate** (outermost, default-deny) — 401 unless path is on the
   public allowlist (login/refresh/register, health/ready/metrics, docs in
   non-prod, public billing plans, signature-authenticated webhooks).
2. **Security headers** + **observability** middleware (request/correlation
   IDs, latency metrics).
3. **Tenant middleware** — resolves `TenantContext` from token +
   `user_school_memberships`.
4. **Audit middleware** — records mutating requests (best-effort, non-fatal).
5. **Router → service → repository** — permissions via `require_permission`
   / `require_role` / `require_platform_permission`; tenant scoping applied
   at query construction (see TENANCY_MODEL.md).
6. Domain exceptions → HTTP via `error_handlers.py`
   (`AuthenticationError→401`, `PaymentRequiredError→402`,
   `AuthorizationError→403`, `NotFoundError→404`, `ConflictError→409`,
   `ValidationError→422`, `FileValidationError→400`).

### 1.3 Data layer (CURRENT)

- 137 ORM tables, single Alembic head `060_add_migration_factory_tables`,
  67 migration files; additive-migration policy (see CURRENT_STATE.md,
  DATA_MODEL.md).
- Multi-tenancy: `campus_id` on tenant-owned aggregate roots; child tables
  scoped through parents; structural default-deny.
- Durability: transactional outbox (`outbox_events`) + durable jobs
  (`jobs`) — the worker consumes both (see EVENT_MODEL.md).
- Money: integer minor units; dual-layer (DB + app) status defaults;
  app-level `created_at`/`updated_at` defaults.

### 1.4 Security posture (CURRENT)

- JWT HS256 access (30 min) + rotating refresh (7 days, reuse detection
  revokes the family); password hashing; login rate limiting; default-deny
  auth gate.
- RBAC permission strings `<resource>.<action>`; platform permissions are
  the only cross-tenant grant; tenant admin never satisfies platform checks.
- Webhook signature verification (HMAC, constant-time), replay protection +
  idempotency ledger; upload validation (size/ext/MIME); append-only audit;
  secrets via env / Vault; CORS restricted; security headers.
- Verified by acquisition-grade suites: 28-test multi-tenant security suite,
  64-test `test_security_acquisition` suite, finance-security and outbox/job
  suites (see docs/enterprise/*).

### 1.5 Frontend (CURRENT)

- Routes: dashboard, command-center, risk, action-center, data-quality,
  work queue + case detail, timeline, students (+360), academic (years/
  classes/360/sections/enrollments/terms/assignments), teachers (+360),
  subjects, attendance (+intelligence), fees, school-finance, users,
  profile, reports (+cards/builder), analytics, notifications, operations
  (exports/rollover/batch), admin (audit logs, approvals), migration center
  + wizard, leave, admissions, communications, and role workspaces
  (principal/accountant/staff/teacher/student/parent).
- Role-gated routes via `RoleGuard`; tenant context via `use-campus`;
  universal + smart search; motion/delight layer (MotionProvider,
  anime.js); design tokens in `index.css`.

---

## 2. IN PROGRESS — implemented cores, not fully wired

These are **real code** in the repository with their own tests, but none is
exposed through an API router or consumed by a domain yet. Do not describe
them as shipped product surfaces.

### 2.1 Temporal `txn_log` ledger — IN PROGRESS

- **Implemented**: `app/temporal/` — `TxnLog` model (`txn_log` table, created
  by migration `create_temporal_txn_log`), `TxnManager` close-open writes
  (current + history + txn_log committed atomically), `TimeContext`,
  `ChangeEnvelope`, table registry.
- **Tests**: `tests/test_temporal/` (atomicity proven by injecting a failure
  into the last statement).
- **Not wired**: no domain router consumes `TxnManager`; the full bitemporal
  query surface ("The Archive", `docs/TEMPORAL_DATABASE_V3.md`) is PLANNED.
- **Gap**: which tables register for close-open tracking, and when the
  ledger is written from domain services, is not yet defined in code.

### 2.2 Intelligence detection pipeline — IN PROGRESS

- **Implemented**: `app/intelligence/` — similarity (Jaro-Winkler, token
  Jaccard, phone/email normalization), clustering (DBSCAN, label
  propagation, PageRank), detectors (attendance anomaly, cheating cluster,
  favoritism, social cluster, duplicates), `DetectionPipeline`,
  `EvidenceScorer`.
- **Wired**: `app.intelligence.similarity` is consumed by
  `data_quality/checks.py`.
- **Not wired**: detectors/pipeline have no router or job; they run only in
  tests (`tests/test_intelligence/`).

### 2.3 Simulation engine core — IN PROGRESS

- **Implemented** (`app/simulation/`): scenario/lever model, baseline
  snapshot, coefficient registry, DAG engine with default graph, 9
  deterministic forecasts (revenue, workload, attendance, dropout, budget,
  rooms, transport, performance, resource), comparison with composite score.
- **Golden tests**: exact float pins + run-twice determinism
  (`tests/test_simulation/`).
- **Not wired**: no persistence (snapshot/run/result tables), no router, no
  worker runner, no tenant guards. Per `docs/SIMULATION_ENGINE.md`:
  "Persistence, tenancy guards, API router, worker runner, visualization —
  Spec only".

### 2.4 Optimization engine core — IN PROGRESS

- **Implemented** (`app/optimization/`): CP-SAT variable model + named
  registry, constraint abstraction (hard/soft/gateable), objectives
  (weighted + lexicographic), solver facade, conflict explainer via
  assumption cores, `ProblemAdapter` protocol, working invigilation adapter.
- **Tests**: `tests/test_optimization/` (golden determinism, hard-constraint
  audit).
- **Not wired**: no persistence, no router, no worker runner, other
  adapters spec-only. OR-Tools is deliberately a worker-only dependency in
  the plan; the API must never import it.

---

## 3. PLANNED — design specs (no runnable behaviour yet)

| Capability | Spec | Key points | Enabling trigger |
|---|---|---|---|
| Graph layer | `docs/GRAPH_LAYER.md` | Derived read-optimised graph over Postgres; outbox-driven sync; embedded `networkx` default; `graph_enabled=false`; tenancy-default-deny preserved | Scaffold exists in `app/graph/`; flip flag + migration adds adjacency tables |
| Bitemporal database ("The Archive") | `docs/TEMPORAL_DATABASE_V3.md` | Every table bitemporal (valid + transaction time); as-of queries; coexists with `audit_logs`; built on the existing `txn_log` ledger | Extend the IN PROGRESS temporal core |
| Full simulation product surface | `docs/SIMULATION_ENGINE.md` | Persistence, router, worker runner, comparison/sensitivity endpoints, exports | Wire the implemented core |
| Full optimization product surface | `docs/OPTIMIZATION_ENGINE.md` | Job/result persistence, API router, worker runner, benchmark gate, viz | Wire the implemented core |

**Rule**: a PLANNED capability must not appear in user-facing docs, menus,
or API surface until it is wired and verified. This document will be updated
as each item moves to IN PROGRESS / CURRENT.

---

## 4. Target architecture direction (where the roadmap points)

The strategic target (per `docs/ROADMAP.md` and the product briefs) is an
extensible enterprise platform, **not** a rewrite:

1. **Canonical data/identity** — CURRENT: institutions/campuses/users/
   memberships, tenant framework. Keep as the identity substrate.
2. **Migration & reconciliation** — CURRENT: enterprise migration engine
   verified end-to-end (see MIGRATION-VERIFICATION.md). Extend domains,
   not the engine.
3. **Financial integrity** — CURRENT: integer minor units, idempotency
   keys, webhook ledger, reconciliation. Back with DB-level invariants
   where appropriate (see FINANCIAL-INTEGRITY-REPORT.md).
4. **Deterministic engines** — IN PROGRESS: simulation + optimization cores;
   PLANNED: graph layer. All deterministic, tenancy-preserving, audited;
   no AI/LLM dependency.
5. **Temporal/compliance** — IN PROGRESS: `txn_log`; PLANNED: full
   bitemporal.
6. **Offline-first / hardware / device / digital twin / SSO / BYOK /
   zero-trust** — PLANNED or not yet specced; do not claim existence.

**Constraint**: every addition must reuse the existing jobs/outbox, tenant
framework, audit, and event bus. No new queues, no second engines, no
customer forks.

---

## 5. Cross-cutting invariants (apply to CURRENT and all targets)

1. **Tenant isolation at every layer** — structural default-deny
   (TENANCY_MODEL.md). Graph/simulation/optimization/temporal must inherit
   the same scoping.
2. **Financial correctness** — money in minor units; idempotency; atomic
   outbox; reconciliation evidence.
3. **Auditability** — every mutating operation on production-important
   entities writes an audit event with an explicit actor.
4. **Determinism** — no randomness in risk/simulation/optimization; golden
   tests.
5. **PostgreSQL for production, SQLite only for unit tests** — migration
   chain is PostgreSQL-only (documented limitation).
6. **Additive migrations, single head** — never edit historical revisions.
7. **No AI/LLM runtime dependency** — mapping/similarity/detection are
   deterministic algorithms (see docs/enterprise migration reports).
