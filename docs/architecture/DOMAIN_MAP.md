# DOMAIN MAP — SDMAS v2 Backend Domains and Cross-Cutting Layers

Date: 2026-08-17 · Source of truth: `apps/api/app/` (verified against the live
repository, not documentation).

Every domain follows the same shape (`models.py` / `schemas.py` /
`repository.py` / `service.py` / `router.py`, plus domain events where
relevant). Tenant-owned repositories subclass `TenantScopedRepository`
(`app/multi_tenant/repository.py`). Money is stored as integer minor units.
Statuses are `VARCHAR` with app-level validation (no Python enums in models).

---

## 1. Domain inventory (35 domains under `apps/api/app/domains/`)

| # | Domain | Purpose (evidence) | Key files |
|---|---|---|---|
| 1 | `academic` | Academic years, terms, classes, sections, subjects, enrollments, teacher assignments | `academic/router.py`, `academic/service.py` |
| 2 | `academic_ops` | Rooms, time slots, timetables, operational scheduling data (consumed by optimization adapters later) | `academic_ops/*` |
| 3 | `admission` | Applications, inquiries, merit lists, admission lifecycle | `admission/router.py`, `admission/service.py` |
| 4 | `analytics` | Attendance/finance/student/academic analytics endpoints | `analytics/router.py` |
| 5 | `attendance` | Attendance records, daily/section/student attendance, record/update | `attendance/*` |
| 6 | `attendance_intelligence` | Period attendance, corrections, thresholds; low-attendance alerts | `attendance_intelligence/*` |
| 7 | `audit` | Append-only audit log, middleware, export, actors | `audit/middleware.py`, `audit/service.py`, `audit/actors.py` |
| 8 | `auth` | Registration, login, JWT access/refresh, users, roles, permissions; platform admin router | `auth/router.py`, `auth/admin_router.py`, `auth/permissions.py`, `auth/dependencies.py` |
| 9 | `billing` | Subscriptions, invoices, Razorpay webhooks, plan catalog (platform-gated pricing) | `billing/router.py`, `billing/admin_router.py`, `billing/razorpay.py`, `billing/payments.py` |
| 10 | `cases` | Operational case/work items, escalation jobs, bulk assignment | `cases/router.py`, `cases/service.py` |
| 11 | `class_360` | Class 360 view aggregation | `class_360/router.py` |
| 12 | `command_center` | Leadership command-center aggregates | `command_center/router.py` |
| 13 | `communications` | Message templates, composer, sent messages (email/push via notifications) | `communications/*` |
| 14 | `data_quality` | Data-quality checks; uses `app.intelligence.similarity` (name/phone/email normalization) | `data_quality/checks.py` |
| 15 | `documents` | Upload validation (size/ext/MIME), categories, soft-delete (`deleted_at`) | `documents/router.py`, `documents/validation.py`, `documents/service.py` |
| 16 | `events` | In-process domain event bus, event catalog, durable transactional outbox | `events/events.py`, `events/catalog.py`, `events/outbox.py`, `events/outbox_handlers.py` |
| 17 | `fees` | Fee types, structures, dues, payments, refunds, idempotency keys | `fees/router.py`, `fees/service.py`, `fees/models.py` |
| 18 | `institution` | Institutions, campuses, branding metadata, membership roots | `institution/router.py` |
| 19 | `jobs` | Durable background jobs: table, registry, worker, scheduler, periodic jobs | `jobs/worker.py`, `jobs/scheduler.py`, `jobs/registry.py`, `jobs/loader.py`, `jobs/periodic_jobs.py` |
| 20 | `leave` | Leave requests with approval workflow | `leave/*` |
| 21 | `migration` | Enterprise data migration: DISCOVER → PROFILE → IDENTITY MATCH → MAP → TRANSFORM → VALIDATE → DRY RUN → RECONCILE → APPROVE → MIGRATE → VERIFY → CUTOVER (TASK 15 factory stages added over the existing workspace) | `migration/engine.py`, `migration/project_service.py` (factory ops), `migration/factory.py` (pure profiling/matching/classification/verification), `migration/workspace_import.py`, `migration/migrators/` |
| 22 | `notifications` | In-app notifications, device tokens, channels (in-app/push/email/SMS), SSE manager, preferences, templates | `notifications/dispatcher.py`, `notifications/channels.py`, `notifications/sse_manager.py`, `notifications/handlers.py` |
| 23 | `parent` | Parent portal junctions (parent→children) | `parent/router.py` |
| 24 | `reports` | Predefined report endpoints (attendance, fee collection, outstanding, receipts) | `reports/router.py` |
| 25 | `report_builder` | Custom report builder with registry + builders; seeded at startup | `report_builder/registry.py`, `report_builder/builders.py` |
| 26 | `report_cards` | Report card generation | `report_cards/*` |
| 27 | `risk` | Deterministic risk engine (attendance/fees/academic/documents/admissions/operational rules), findings, teacher risk | `risk/evaluator.py`, `risk/rules.py`, `risk/service.py` |
| 28 | `school_finance` | Transaction ledger, receipts, reconciliation, financial exceptions | `school_finance/router.py`, `school_finance/service.py` |
| 29 | `search` | Smart search (Fuse.js-style / trgm-backed) | `search/router.py` |
| 30 | `student` | Student CRUD + lifecycle router (admission approval → enrollment) | `student/router.py`, `student/lifecycle_router.py` |
| 31 | `student_360` | Student 360 aggregation view | `student_360/router.py` |
| 32 | `student_portal` | Student portal: timetable, attendance view, fees view, documents | `student_portal/router.py` |
| 33 | `teacher_360` | Teacher 360 aggregation view | `teacher_360/router.py` |
| 34 | `timeline` | Unified operational timeline | `timeline/router.py` |
| 35 | `workflow` | Approval workflow instances (submit/approve/reject/cancel) with domain events | `workflow/models.py`, `workflow/service.py`, `workflow/router.py` |

## 2. Cross-cutting layers (outside `domains/`)

| Layer | Path | Role |
|---|---|---|
| Configuration | `app/config.py` | Pydantic-settings; env + `.env`; prod refuses default secrets |
| Application factory | `app/main.py` | Lifespan (OTel, payment provider, event handlers, report/doc seeding, in-process workers), middleware chain, router registration, exception handlers |
| Core exceptions | `app/core/exceptions.py`, `error_handlers.py` | Canonical hierarchy → HTTP mapping (401/402/403/404/409/422/400) |
| Pagination | `app/core/pagination.py` | `Page` / `PaginationParams` primitives |
| Security | `app/core/security/` | `auth_gate.py` (default-deny), `headers.py`, `rate_limiter.py`, `client_ip.py`, `audit.py` |
| Observability | `app/core/observability/` | JSON logging, OpenTelemetry, `/health` `/ready` `/metrics` |
| Secrets | `app/core/secrets.py` | Env / Vault backends |
| Database | `app/infrastructure/database.py`, `models.py` | Async engine, session factory, `get_session`, `Base` aggregate |
| Tenancy | `app/multi_tenant/` | `TenantContext`, model registry, `TenantScopedRepository`, guards, middleware (see TENANCY_MODEL.md) |
| Intelligence | `app/intelligence/` | Deterministic detection library: similarity (Jaro-Winkler, Jaccard), clustering (DBSCAN, label propagation, PageRank), detectors (attendance anomaly, cheating cluster, favoritism, social cluster, duplicates), scoring, pipeline |
| Graph | `app/graph/` | **Scaffold only** — `graph_enabled=false`, no behaviour wired (see TARGET_ARCHITECTURE.md §4) |
| Simulation | `app/simulation/` | **Working core, not wired to API** — scenario/lever model, snapshot, coefficient registry, DAG engine, 9 deterministic forecasts |
| Optimization | `app/optimization/` | **Working core, not wired to API** — CP-SAT variable model, constraints, objective, explainer, invigilation adapter |
| Temporal | `app/temporal/` | **Partial** — `txn_log` append-only ledger + `TxnManager` close-open writes implemented (migration `create_temporal_txn_log`); full bitemporal is design spec |
| Identities | `app/platform/identities/` | **Canonical identity layer (TASK 8)** — `CanonicalPerson` referencing existing entities, external identities (ERP/biometric/RFID/transport), aliases, deterministic rule-based matching (no AI), manual review, merge with snapshots, append-only history; six tenant-owned tables (migration `053`); not yet exposed through a router |
| Lineage | `app/platform/lineage/` | **Data lineage foundation (TASK 9)** — data sources, assets, transformations, directed polymorphic edges, versioned calculation definitions, evidence references; answers "where did this value come from?"; six tenant-owned tables (migration `054`); wired into the migration engine (`import_job.py` records lineage on import); not yet exposed through a router |
| Reconciliation | `app/platform/reconciliation/` | **Universal reconciliation engine (TASK 10)** — generic framework: runs, configurable rule configs, deterministic side-aware matching, tolerance/exact comparison, exceptions with severity + status, approvals, evidence; six tenant-owned tables (migration `055`); not yet exposed through a router |
| Policy | `app/platform/policy/` | **Policy-as-code foundation (TASK 11)** — versioned policies (stable `policy_id`, scope, sequential versions, effective-date windows, approval metadata); deterministic JSON rule DSL over a closed operator set (no code eval, fails closed); persisted evaluation trace (version + input + result); registry catalogs scopes (attendance/fees/admissions/approvals/compliance/security/workflow/global) without hard-coding board policies; three tenant-owned tables (migration `056`); not yet exposed through a router |
| Evidence | `app/platform/evidence/` | **Enterprise evidence foundation (TASK 12)** — application-level evidence storage: claim packages, items (with policy version), references (pointers, never copies), immutable snapshots with canonical-JSON SHA-256 content hashes, per-package hash chain (tamper detection via `verify_package`), approval trail; answers what was claimed / what data supported it / what calculation / which policy version / who approved / when / whether it changed; six tenant-owned tables (migration `057`); not yet exposed through a router |
| Audit chain | `app/platform/cryptography/` | **Tamper-evident audit chain (TASK 13)** — chained cryptographic integrity over `audit_logs`: every audit event gets a chain entry (prev/payload/current hash + HMAC signature) and periodic signed checkpoints; per-campus chains (tenant-isolated); detects modification / deletion / reordering / missing rows via the shared pure verifier; integrated into `AuditService.record()` (guarded, non-fatal); two tenant-owned tables (migration `058`); standalone `scripts/audit_verify.py` verifier (exit 0/1); honest guarantee: tamper-evident, not absolute immutability |
| Extensions | `app/platform/extensions/` | **Zero-fork extension architecture (TASK 14)** — controlled extension system: versioned manifest contract (identity, permissions, routes, events, config schema, migrations, frontend registration, policy) validated against closed registry catalogs; lifecycle register → publish (core-compat semver check) → grant → enable; extensions cannot bypass tenant isolation, authorization (grants gate enable; revoke auto-disables), audit (every mutation audited), policy (deny raises through `PolicyService`), or data validation (manifests + configs validated before persist); pure stdlib semver (`compat.py`); four tenant-owned tables (migration `059`); not yet exposed through a router |
| Migration factory | `app/domains/migration/factory.py` | **Migration factory stages (TASK 15)** — source profiling (entity distribution, quality scorecard, PII, duplicate-key candidates), deterministic identity matching ladder (number/email/phone/name+DOB/fuzzy, ambiguous detection), dry-run classification (CREATE/UPDATE/SKIP/ERROR) persisted as immutable snapshots, post-import verification (per-entity counts + spot checks), cutover with rollback-live guard, optional approval gate; mapping versioning on every save; evidence packaging via the TASK 12 evidence foundation; migration `060` (additive: `migration_snapshots` + six JSON columns on `migration_projects`) |
| Platform events | `app/platform/events/` | Canonical event envelope (TASK 7) — `CanonicalEnvelope` + integrity hashing over the existing domain-event system |

## 3. Wiring status (who calls what — verified)

- `app.main` includes **40 `include_router` calls** (39 domain/admin routers
  plus the observability router); every domain router is registered.
- `app.intelligence.similarity` is consumed by `data_quality/checks.py`. The
  intelligence **detectors/pipeline** are an implemented library not yet
  exposed through a router (tested in `tests/test_intelligence/`).
- `app.temporal.TxnManager` and `txn_log` are implemented and tested
  (`tests/test_temporal/`); no domain router calls them yet.
- `app.graph`, `app.simulation`, `app.optimization` are **not imported by
  any router** (verified by import search); simulation/optimization cores
  are exercised only by their own test suites.
- The migration domain is fully wired: workspace wizard (upload → discovery
  → mapping → validation → preview → execute via the durable jobs worker →
  progress → reconcile → report → rollback) — verified end-to-end in
  `docs/enterprise/MIGRATION-VERIFICATION.md`.

## 4. Status legend used across this documentation set

- **CURRENT** — implemented, wired, and verified.
- **IN PROGRESS** — implemented core exists but is not fully wired (no
  router / not consumed by a domain), or partially wired.
- **PLANNED** — design spec exists (`docs/*.md`); no runnable behaviour.

| Capability | Status |
|---|---|
| 35 backend domains, multi-tenant, RBAC, audit, jobs/outbox, fees/ledger, migration, risk, reports | CURRENT |
| Intelligence detection pipeline | IN PROGRESS (library; similarity wired, detectors not yet routed) |
| Temporal `txn_log` ledger | IN PROGRESS (ledger + manager implemented; full bitemporal PLANNED) |
| Simulation engine core | IN PROGRESS (core + forecasts; no persistence/API) |
| Optimization engine core | IN PROGRESS (core + invigilation adapter; no persistence/API) |
| Graph layer | PLANNED (empty scaffold, flag `graph_enabled=false`) |
| Bitemporal "The Archive" (full) | PLANNED (design spec `docs/TEMPORAL_DATABASE_V3.md`) |
