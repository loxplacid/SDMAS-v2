# DOMAIN CONTRACTS — SDMAS v2 Domain Boundaries and Public Contracts

Date: 2026-08-17 · Method: static AST import-graph analysis of
`apps/api/app/domains/` + manual verification of cycle edges, router logic,
and cross-domain writes. Contract rules are enforced by
`apps/api/tests/test_domain_boundaries.py`.

---

## 1. Intended dependency direction

```
Router  (HTTP surface, permissions + tenant guards)
  → Application Service   (business logic, state transitions, audit)
      → Domain Logic       (models, validators, evaluators)
          → Repository / Infrastructure  (data access, platform primitives)

Domain
  → shared platform primitives   (audit, auth deps, events, jobs,
                                  multi_tenant, infrastructure)

AVOID
  Domain A → Domain B internal implementation (B's router / repository /
             service internals without a contract)
```

Rules enforced by tests:

1. **A domain must never import another domain's router** (HTTP surface
   stays at the top of the graph) — `test_no_cross_domain_router_imports`.
2. **Infrastructure must never import `app.domains`** (layering) — sole
   documented exception `app/infrastructure/models.py` (model-registration
   hub for worker/Alembic entrypoints) —
   `test_no_infrastructure_domain_imports`.
3. **Cross-domain import cycles must not grow** beyond the documented
   allowlist — `test_cross_domain_cycles_do_not_grow` +
   `test_cycle_allowlist_is_current`.

Allowed cross-domain coupling patterns (used deliberately by the
codebase):

| Pattern | Allowed? | Examples |
|---|---|---|
| A → B **service class** via its public API | Yes (preferred) | `fees → school_finance.TransactionLogService`; `leave → workflow.WorkflowExecutionService`; `command_center → analytics/DataQuality/CaseService` |
| A → B **repository** for read-only scoped queries | Yes, read-only | `academic → student.StudentRepository`; `attendance → academic repos`; `reports → academic/attendance/fees/student repos` |
| A → B **models** for read-only joins/aggregation | Yes, read-only | `analytics`, `search`, `command_center`, `risk`, `school_finance`, `timeline` read other domains' models |
| A → B **models** and writes B's rows | **No** (flagged) | `cases.service._sync_source_finding` writes `RiskFinding` / `DataQualityFinding` status (documented exception, §4.4) |
| A → B **router** | **Never** | zero occurrences; guarded |

---

## 2. Per-domain public contracts

Each domain exposes the standard layer set (`models.py`, `schemas.py`,
`repository.py`, `service.py`, `router.py`). "Consumers" = cross-domain
importers of its public API (service/repository/models), verified from the
import graph.

| Domain | Models (tables) | Public service API (cross-domain consumers) | Own events | Jobs |
|---|---|---|---|---|
| academic | years, terms, classes, sections, subjects, teachers, assignments, enrollments | repos consumed by attendance, fees, reports, analytics, risk, academic_ops, search | `student.enrolled` | — |
| academic_ops | rooms, slots, timetables | `DAY_NAMES` consumed by student_portal | — | — |
| admission | applications, inquiries, merit lists | service events | `admission.*` | — |
| analytics | (aggregation only) | `AnalyticsService` → command_center | — | — |
| attendance | attendance_records | repos consumed by reports, attendance_intelligence | `attendance.*` | — |
| attendance_intelligence | period_attendances, corrections, thresholds | — | `attendance.threshold_breached` | — |
| audit | audit_logs | `AuditService` consumed by ~14 domains; `AuditActor`, constants | — | — |
| auth | users, roles, permissions, refresh_tokens | `require_permission/require_role`, `User`, `decode_token` consumed by every domain | — | — |
| billing | plans, subscriptions, invoices, webhook_events | `SubscriptionService` → jobs scheduler | — | billing period-end/expiry jobs |
| cases | cases, events, comments, evidence, SLA config | `CaseService` → jobs scheduler, command_center | `workflow.*` (shared) | case escalation job |
| class_360 / teacher_360 / student_360 | (aggregation views) | — | — | — |
| command_center | (aggregation) | — | — | — |
| communications | messages, templates | `CommunicationService` → jobs scheduler | — | scheduled message job |
| data_quality | findings | `DataQualityService` → command_center | — | — |
| documents | documents, categories, shares | — | `document.*` | — |
| events | outbox_events | `publish_event`, `publish_durable`, event bus, catalog | (catalog) | outbox worker |
| fees | fee_types, structures, dues, payments | `Payment`, `FeeDue` models consumed by school_finance, cases, search | `fee.due_created`, `payment.recorded` | — |
| institution | institutions, campuses, schools, departments, programs | `Campus` consumed by auth/membership | — | — |
| jobs | jobs | `JobService`, `Job`, `BaseJob` consumed by migration, report_builder, command_center | — | job worker + scheduler |
| leave | leave_requests | — | `leave.*` | — |
| migration | projects, runs, logs, mappings | engine/migrators (self-contained) | — | `MigrationImportJob` |
| notifications | notifications, device_tokens, preferences | `NotificationService` consumed by risk, cases, communications | (legacy events) | — |
| parent | guardian junctions | — | — | — |
| reports / report_builder / report_cards | report_definitions, export jobs | repos read academic/attendance/fees/student | — | export jobs |
| risk | risk_findings, rule_configs | `RiskFinding` consumed by cases, school_finance; `RiskService` — | — | risk recompute (in-process) |
| school_finance | transaction_logs, receipts, reconciliations, fee_schedules, payment_methods | `TransactionLogService` consumed by fees | — | — |
| search | (index) | — | — | — |
| student | students | `StudentRepository` consumed by academic, attendance, fees, reports | `student.*` | — |
| student_portal / parent | portal views | — | — | — |
| timeline | (aggregation) | — | — | — |
| workflow | workflow instances | `WorkflowExecutionService` consumed by leave | `workflow.*` | — |

---

## 3. Circular dependency findings

### 3.1 Cycles fixed in this audit

| Cycle | Root cause | Fix |
|---|---|---|
| `billing ↔ jobs` | `billing/models.py` imported `JSONType` from `jobs/models.py`; `jobs/periodic_jobs.py` imports `billing.service` | Consolidated the `JSONType` TypeDecorator (which was **duplicated in 3 files** — `jobs/models.py`, `events/outbox.py`, plus a 4th copy in `temporal/models.py`) into `app/infrastructure/types.py`; `billing`/`migration` models now import from infrastructure. Direction is now one-way `jobs → billing` (the scheduler triggering billing jobs), which is correct |

### 3.2 Remaining cycles (documented allowlist — enforced by tests)

All are tolerated by Python's import machinery (the app boots; imports
resolve by order) but represent coupling worth tracking. Each is
deliberate or a platform-primitive coupling; none is a router import.

| Cycle | Edge A → B | Edge B → A | Classification |
|---|---|---|---|
| `audit ↔ auth` | audit middleware/utils/export need `decode_token`, `User`, auth deps (audit runs outside auth) | auth services/routers record audits via `AuditService` | Platform-primitive coupling (both are core platform layers). Acceptable; a future refactor could move `decode_token` to `core/security` |
| `audit ↔ events` | audit service reads correlation id from `events.context` | event handlers write audits | Platform-primitive coupling. Acceptable |
| `auth ↔ institution` | auth/membership needs `Campus` model | institution router needs auth deps | Legitimate read of a platform entity. Acceptable |
| `cases ↔ risk` | cases validates/syncs `RiskFinding` | risk reads `Case` for linked-case lookup | Cross-domain model read + the documented finding-sync exception (§4.4). Acceptable with contract |
| `cases ↔ school_finance` | cases validates financial sources (`PaymentReconciliation`/`ReconciliationItem`) | school_finance reads `Case` for linked cases | Read-only cross-domain references. Acceptable |
| `fees ↔ school_finance` | fees calls `TransactionLogService` (correct service-to-service) | school_finance reads `Payment` for receipts/exceptions/reconciliation | The A→B direction is the *preferred* pattern; the reverse is read-only. Acceptable |

**Rule for the future**: a new domain-level cycle fails CI
(`test_cross_domain_cycles_do_not_grow`). Adding one requires fixing the
direction first; the allowlist is only updated for genuinely platform-level
couplings with a written justification in this section.

---

## 4. Findings beyond cycles

### 4.1 Domain logic inside routers (documented, not refactored — larger scope)

| Router | Size | Finding |
|---|---|---|
| `billing/router.py` | 610 | **Webhook state machine in the router**: `_apply_webhook_event`, `_apply_payment_captured`, `_apply_payment_failed` (~250 lines of financial domain logic: idempotency, amount fail-closed, subscription transitions). Deliberately self-contained (public, signature-authenticated, no user session). Moving to a service is a **security-critical refactor** — recommended next step, not done here |
| `institution/router.py` | 977 | Direct `session.execute(select(...))` hierarchy queries in route handlers (campus→school→department→program); hierarchy-building logic lives in the router rather than a service |
| `documents/router.py` | 307 | Direct `svc.session.get(DocumentShare, id)` in two routes — bypasses the repository layer |
| `communications/router.py` | 430 | One direct `svc.session.execute` in a route |
| `school_finance/router.py` | 720 | Large; mixes query building with orchestration (mostly thin, but large) |

**Guidance**: move webhook handling into `billing/service.py` first
(highest value, security-critical), then institution hierarchy queries into
`institution/service.py`. Both are medium-risk refactors with existing test
coverage to lean on — do them as dedicated tasks.

### 4.2 Duplicated business logic

| Duplication | Locations | Risk | Status |
|---|---|---|---|
| `JSONType` TypeDecorator | was in `jobs/models.py`, `events/outbox.py`, `temporal/models.py` (+ imported by billing/migration) | low | **FIXED** — now `app/infrastructure/types.py` |
| `valid_email` validators | `auth/schemas.py` (×2), `migration/validators.py` | low | documented — different contexts (Pydantic vs migration rule engine) |
| `_parse_date` | `migration/migrators/academic.py`, `migration/transforms.py` | low | documented — same domain, different input shapes |
| ledger sign classification | `school_finance/service.py` `LEDGER_DEBIT_TYPES`/`LEDGER_CREDIT_TYPES` | critical-if-diverged | single source of truth already (both `record` and balance recompute consume the constants) — good |

### 4.3 Direct cross-domain table manipulation

| Site | What it does | Verdict |
|---|---|---|
| `school_finance` `_validate_payment`, `ReceiptService`, `FinancialExceptionService` | reads `fees.Payment` (+ `student`, `cases`) rows directly | Acceptable read-only aggregation; campus-scoped. Prefer `PaymentRepository` in future |
| `cases._validate_source` / `_source_priority` | reads `risk.RiskFinding`, `data_quality.DataQualityFinding`, `fees.Payment`, `school_finance.*` for reference validation | Acceptable read-only reference checks |
| `cases._sync_source_finding` | **writes** `RiskFinding.status` and `DataQualityFinding.status` | Documented exception (P11 loop: resolving a case resolves its source finding; reopening reopens it). Guarded: campus-scoped, audited, idempotent, never overrides external resolution. A future contract could route this through `RiskService`/`DataQualityService` public methods |
| `risk.linked_cases_for_findings`, `school_finance` linked-case lookup | read `cases.Case` | Acceptable read-only |

### 4.4 Inconsistent error handling

- 23 of 32 domain services import the canonical `app.core.exceptions`
  (`NotFoundError`, `ValidationError`, `ConflictError`, …) → mapped to
  deliberate 4xx by `error_handlers.py`.
- 9 services **do not** import core exceptions: `analytics`, `audit`,
  `class_360`, `command_center`, `institution`, `jobs`, `notifications`,
  `search`, `teacher_360`. Most are aggregation/read services where raw
  exceptions are acceptable today, but **`institution` and `jobs` handle
  user-facing mutations** and should adopt core exceptions so failures
  become deliberate 4xx instead of 500s.
- Recommended follow-up: `institution` + `jobs` service error normalization
  (small, targeted).

---

## 5. Contract guarantees verified

| Guarantee | Evidence |
|---|---|
| No domain imports another domain's router | `test_no_cross_domain_router_imports` (0 occurrences) |
| Infrastructure never imports domains (except the model hub) | `test_no_infrastructure_domain_imports` |
| Cycle set frozen at 6 documented pairs | `test_cross_domain_cycles_do_not_grow`, `test_cycle_allowlist_is_current` |
| `fees → school_finance` uses the service API, not the table | `fees/service.py` `TransactionLogService(self.repo.session)` |
| Scheduler → billing/communications/cases is one-way (jobs → domains) | import graph; cycle broken for billing |
| Money/ledger invariants are single-sourced | `school_finance` constants consumed by both write and recompute paths |

## 6. Changes made in this audit

| File | Change |
|---|---|
| `apps/api/app/infrastructure/types.py` | **new** — canonical `JSONType` (optional `json_default`) |
| `apps/api/app/domains/jobs/models.py` | use shared `JSONType`; removed local copy |
| `apps/api/app/domains/events/outbox.py` | use shared `JSONType`; removed local copy; fixed pre-existing mypy narrowing in `stop()` |
| `apps/api/app/domains/billing/models.py` | import `JSONType` from infrastructure (breaks billing→jobs) |
| `apps/api/app/domains/migration/models.py` | import `JSONType` from infrastructure |
| `apps/api/app/temporal/models.py` | use shared `JSONType(json_default=_json_default)`; removed local copy |
| `apps/api/tests/test_domain_boundaries.py` | **new** — 4 architectural guard tests |

## 7. Verification

- `tests/test_domain_boundaries.py` — 4 passed.
- Affected suites (`test_outbox`, `test_jobs`, `test_domain_events`,
  `test_temporal`, `test_schema_integrity`, boundary tests) — **101 passed**.
- Migration + fees + finance-security + async-hardening regression —
  **319 passed**.
- `ruff check` / `ruff format --check` / `mypy` clean on all changed files.

## 8. Recommended follow-ups (not done — scoped refactors)

1. Move the billing webhook state machine into `billing/service.py`
   (security-critical; highest value).
2. Move institution hierarchy query building into `institution/service.py`.
3. Normalize error handling in `institution` and `jobs` services to core
   exceptions (deliberate 4xx).
4. Route `cases._sync_source_finding` through `RiskService` /
   `DataQualityService` public methods to remove the cross-domain write.
5. Consider moving `decode_token` to `app/core/security` to break
   `audit ↔ auth`.
