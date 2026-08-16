# SDMAS-v2 — API Verification Matrix

**Status:** Evidence-based audit (no code changes) · **Date:** 2026-08-16
**Scope:** Every route registered by the actual FastAPI application (`app.main`), cross-checked against OpenAPI, the web frontend's API client, the mobile app, repository documentation, and the test suite.

Companion machine-readable artifact: [`API-VERIFICATION-MATRIX-ROUTES.csv`](./API-VERIFICATION-MATRIX-ROUTES.csv) — one row per operation (495), with method, path, domain, authentication, role/permission, tenant scope, expected success status, expected failure statuses, audit requirement, idempotency, and test coverage.

---

## 1. Method

1. **Enumeration:** introspected the live FastAPI app in-process (`app.routes`, unwrapping lazy `_IncludedRouter` wrappers → `original_router`) — not a grep, not the docs. 495 operations / 361 paths.
2. **Dependencies resolved per route:** walked each route's `Dependant` tree and resolved `get_current_user`, `require_role(...)`, `require_permission(...)`, `require_platform_permission(...)`, `require_tenant_context`, `get_school_context`, `get_current_tenant` to concrete callables (including callable-class instances, so roles/permissions appear literally).
3. **Cross-checks:** OpenAPI (`/openapi.json` from the running API), frontend API layer (`apps/web/src/api/**`, 227 URL patterns), mobile app (`apps/mobile`), tests (`apps/api/tests`).
4. **Status codes:** success status from `route.status_code`; failure contract from the registered exception handlers in `app/main.py`.

---

## 2. Global summary

| Metric | Value |
|---|---|
| Operations | **495** (361 paths) |
| Domains | 36 (incl. `auth.admin_router`, `core` observability) |
| Public (no auth) | **11** |
| Authenticated | **484** |
| — with role/permission gate | **380** |
| — auth-only (no role gate) | **104** |
| Tenant-scoped via dependency | **432** |
| — handler/user-scoped or platform | **63** |
| Success statuses | 200 × 387 · 201 × 67 · 204 × 41 |

### Public endpoints (11)

`POST /auth/login`, `POST /auth/refresh`, `POST /auth/register`, `GET /billing/plans`, `GET /billing/plans/{code}`, `POST /billing/webhook/{provider_name}` (signature-verified), `GET /health`, `GET /ready`, `GET /metrics`, `GET /api/communications/meta/channels`, `GET /api/communications/meta/message-types`.

All are intentionally public. The two `communications/meta/*` catalog endpoints and `billing/plans` are read-only static data; the webhook is provider-signature-authenticated; observability routes expose no data.

---

## 3. Security model

### Authentication
Every non-public route resolves `auth.dependencies.get_current_user` (Bearer access token, `type=access` enforced; refresh tokens rejected as bearer credentials — `domains/auth/service.py:394`). Unauthenticated → **401** via `AuthenticationError` handler. The `auth` domain additionally enforces refresh-token rotation + reuse detection.

### Role/permission gates
- **380** routes are gated by `require_role(...)` (195 instances) or `require_permission(...)`.
- Role gate distribution (top): `admin` × 74, `admin,staff` × 28, `admin,staff,teacher,accountant,principal` × 21, `admin,principal,staff` × 18, `admin,principal` × 13, `parent` × 11, `student` × 8, plus permission gates such as `fees.view`, `students.write`.
- `require_role` checks across **all** the user's roles (primary `role` + `assigned_roles` M2M); `require_permission` is DB-backed via `PermissionService` with an in-memory registry fallback.
- **104 auth-only routes** are not role-gated. Breakdown:
  - **91** are tenant-scoped dependencies with per-object authorization in the service layer (e.g. a route that lists data scoped to the caller's campus).
  - **13** are user self-service and legitimately role-less: `GET/PATCH /auth/me`, `PATCH /auth/me/password`, `POST /auth/logout`, `GET /auth/schools`, `POST /auth/schools/switch`, `GET/POST/PATCH /api/communications/inbox|preferences|read`, `GET/PUT/PUT /api/notifications/preferences*`.

### Tenant scoping
- **432** routes resolve tenant via `require_tenant_context` (364), `get_school_context` (56), or `get_current_tenant` (12).
- **52 authenticated routes without a tenant dependency** were individually reviewed:
  - **Platform-level** (correctly unscoped): `billing/admin/*`, `auth/admin_router/*`, platform-permission routes (2).
  - **Static catalogs**: `report-builder/definitions|registry|categories`, `documents/categories`, `migration/entities`.
  - **User-identity-scoped handlers** (tenant comes from the caller, not a path parameter): `student/portal/*` (student's own data), `communications/messages*` (spot-checked: `svc.list_messages(user=current_user, ...)`), `report-builder/execute|saved|exports` (spot-checked: `campus_id = current_user.campus_id` passed into the builder), `notifications` device/preferences, `auth/me|schools`.
- **No route was found that resolves a tenant from a path/query parameter without a tenant dependency or handler-level scope assertion.** Cross-tenant object access is additionally rejected by `NotFoundError` (404) for foreign-tenant IDs in tenant-scoped repositories (verified by the multi-tenant security suite).

---

## 4. Status-code contract

Global exception handlers (`app/main.py:262–271`) map domain exceptions to deliberate 4xx responses — **no generic 500s for expected conditions**:

| Exception | Status | Used for |
|---|---|---|
| `AuthenticationError` | **401** | missing/invalid/expired token, wrong token type |
| `AuthorizationError` | **403** | role/permission denied, cross-tenant platform access |
| `NotFoundError` | **404** | missing resource; **foreign-tenant IDs resolve to 404 (no existence leak)** |
| `ConflictError` | **409** | duplicate codes, state conflicts |
| `ValidationError` | **422** | input/parameter validation (request-body schema 422 from FastAPI) |
| `PaymentRequiredError` | **402** | billing gating |
| `FileValidationError` | 400 | upload validation |

Success: **200** list/detail (387), **201** create (67), **204** delete/void (41).

---

## 5. Per-domain matrix

`ops` = operations · `pub` = public · `role` = role/permission-gated · `depTenant` = tenant dependency · `201/204` = create/no-content counts · `audit` = routes marked audit-recording (non-GET in an audit-recording domain) · `DIRECT` = dedicated test dir.

| domain | ops | pub | role | depTenant | 201 | 204 | audit | DIRECT |
|---|---|---|---|---|---|---|---|---|
| academic_ops | 46 | 0 | 46 | 46 | 8 | 8 | 0 | 0 |
| academic | 36 | 0 | 20 | 36 | 8 | 5 | 0 | 36 |
| institution | 35 | 0 | 21 | 35 | 7 | 7 | 0 | 0 |
| school_finance | 34 | 0 | 34 | 34 | 5 | 2 | 11 | 0 |
| attendance_intelligence | 27 | 0 | 27 | 27 | 4 | 3 | 0 | 0 |
| communications | 24 | 2 | 18 | 10 | 2 | 2 | 13 | 0 |
| fees | 24 | 0 | 24 | 24 | 4 | 0 | 8 | 24 |
| migration | 24 | 0 | 24 | 23 | 1 | 0 | 0 | 0 |
| admission | 23 | 0 | 2 | 23 | 5 | 2 | 13 | 0 |
| analytics | 20 | 0 | 20 | 20 | 0 | 0 | 0 | 0 |
| cases | 18 | 0 | 18 | 18 | 1 | 0 | 12 | 18 |
| workflow | 18 | 0 | 10 | 18 | 5 | 4 | 12 | 18 |
| billing | 17 | 3 | 6 | 8 | 0 | 0 | 0 | 0 |
| report_builder | 15 | 0 | 15 | 0 | 2 | 1 | 0 | 0 |
| auth | 14 | 3 | 5 | 5 | 2 | 1 | 10 | 14 |
| notifications | 13 | 0 | 1 | 10 | 1 | 3 | 0 | 13 |
| documents | 12 | 0 | 12 | 11 | 3 | 1 | 6 | 0 |
| reports | 12 | 0 | 12 | 12 | 3 | 0 | 0 | 12 |
| parent | 11 | 0 | 11 | 11 | 1 | 1 | 0 | 0 |
| risk | 9 | 0 | 9 | 9 | 0 | 0 | 4 | 9 |
| attendance | 9 | 0 | 9 | 9 | 2 | 0 | 3 | 9 |
| student_portal | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 |
| jobs | 8 | 0 | 2 | 8 | 1 | 0 | 4 | 8 |
| student | 8 | 0 | 8 | 8 | 1 | 1 | 4 | 8 |
| data_quality | 6 | 0 | 6 | 6 | 0 | 0 | 3 | 6 |
| search | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| leave | 4 | 0 | 0 | 4 | 1 | 0 | 0 | 0 |
| report_cards | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 4 |
| audit | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 3 |
| core (health/ready/metrics) | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| command_center / timeline / class_360 / student_360 / teacher_360 | 1 each | 0 | 1 | 1 | 0 | 0 | 0 | 4 of 5 |

**Notes**
- `migration` (24 ops) is tenant-scoped via `require_tenant_context` on 23; `GET /migration/entities` is a static catalog (the 1 exception) — verified it returns the fixed entity-type list, not tenant data.
- `report_builder` (15 ops) has no tenant dependency by design: definitions/registry/categories are catalogs; `execute`/`saved`/`exports` are scoped to `current_user` inside the handlers (spot-checked `campus_id = current_user.campus_id`).
- `student_portal` (8 ops) is gated to role `student` and scoped to the caller's own enrollment — no tenant dependency needed.
- `admission` uses `require_permission('admissions.*')` rather than `require_role` — the 2 "role" in the table are permission gates.

---

## 6. Cross-verification

### 6.1 OpenAPI ⇄ application — **in sync**
`/openapi.json` from the running API lists exactly **361 paths / 495 operations** — identical to the in-process enumeration. There are **no routes missing from OpenAPI** and **no OpenAPI-only routes** (schema is auto-generated from the app). No hand-maintained endpoint reference exists in `docs/`; OpenAPI is the single source of truth (no drift risk).

### 6.2 Frontend ⇄ backend — **0 calls to nonexistent routes**
Extracted **227 unique URL patterns** from `apps/web/src/api/**` (template literals + string literals, `${BASE}` resolved, params normalized):
- **226/227** match an actual backend route.
- The 1 "mismatch" is an extraction artifact — `/api/notifications${qs}` where `qs` is a runtime query-string variable for the real `GET /api/notifications`.
- Every route the frontend calls exists; every URL shape (including `/attendance/*` and `/auth/*`) is registered.

### 6.3 Backend ⇄ frontend — **82 routes with no consumer in either UI** (see Finding F2)

### 6.4 Documentation ⇄ implementation
- `docs/enterprise-demo.md`, `docs/migration.md`, `docs/zero-touch-deployment.md` reference only a handful of endpoints (`/auth/login`, `/health`, `/ready`, `/api/migration/...`, `/api/students/...`) — all verified present.
- No documented endpoint was found to be missing. No undocumented *environment* variables surfaced in this pass (covered by the prior docs-to-implementation audit).

---

## 7. Findings

| # | Sev | Finding | Evidence |
|---|---|---|---|
| **F1** | LOW (P2) | **Prefix convention break:** the attendance router is mounted at `/attendance/*` (no `/api`), the only domain outside the `/api/` convention (36 paths in OpenAPI confirm). Frontend and nginx both handle it, so nothing is broken — but it is an undocumented inconsistency external clients must know about. | OpenAPI `/attendance`, `/attendance/daily`, …; `apps/web/src/api/attendance/attendance-api.ts`; `infrastructure/nginx/nginx.conf:191` proxies it |
| **F2** | MEDIUM (P2) | **82 operations have no consumer in the web FE or mobile app** (verified by URL sweeps — zero references in `apps/web/src` and `apps/mobile/src`): `academic_ops` 46 (curricula, exam-schedules, grade-records, grading-structures, rooms, substitutions, time-slots, timetable), `documents` 12, `admission` merit-entries/seat-allocations 7, `billing/admin` 6, `report_cards` PDF 4, `notifications` send-push/device-tokens 4, `communications` inbox/schedules-pending 3. Either intended backend-only surface (platform billing console, future mobile/print flows) or dead API. Needs a product decision, not a delete. | Route sweeps §6.3; CSV `test_coverage` col for those domains |
| **F3** | MEDIUM (P2) | **`attendance_intelligence` API has no direct test coverage** — 27 ops, no test file references the domain directly (`tests/test_intelligence/` covers the engine core; `test_command_center` touches it indirectly). Same for the F2 dead domains (`documents`, `academic_ops` API, `billing`), which are also untested at the API layer. | `grep -rln "attendance_intelligence" tests/` → only command-center; CSV coverage col |
| **F4** | OBSERVATION | **Auth-only (no role) routes are deliberate** — 91 tenant-dependency-scoped + 13 user self-service; no unauthenticated data exposure found; no role-less route mutates cross-tenant state. | §3; CSV `authentication`+`role_permission` cols |
| **F5** | OBSERVATION | **Role-gated routes without tenant dependency are platform/catalog/user-scoped** — handler-level tenant scoping spot-verified for the mutable ones (`report-builder`, `communications`). | §3 tenant scoping; handler spot checks |
| **F6** | OBSERVATION | **Audit recording is not uniform** — 18 service modules record audit events (admission, attendance, auth, cases, communications, documents, fees, jobs, risk, school_finance, student, workflow, …). Domains without service-level audit: `academic`, `academic_ops`, `institution`, `billing`, `analytics`, `search`, `student_portal`, `leave`, `report_builder`, `reports`, `parent`, `notifications` (migration uses `migration_logs` + audit actions). GET-only domains are fine; mutation-heavy domains without audit (e.g. `institution` CRUD: 14 non-GET ops) are candidates for audit hooks. | `grep -rln audit app/domains/*/service.py` |
| **F7** | POSITIVE | No frontend call targets a nonexistent route; no OpenAPI/app drift; single error-handling contract (401/403/404/409/422/402) with no expected-condition 500s found. | §6.1, §6.2, §4 |
| **F8** | POSITIVE | Idempotency protections are DB-backed where they matter: campus-scoped payment idempotency keys (migration 047), `uq_outbox_events_event_id`, `notifications.event_key` dedup, `receipt_number` uniqueness, job status-machine. | CSV `idempotency` col; prior finance/outbox audits |

---

## 8. Test coverage summary

From the CSV (495 rows): **186 DIRECT** (dedicated test dir), **282 PARTIAL** (referenced by at least one test), **27 INDIRECT** (only via aggregate/command-center tests — this is the `attendance_intelligence` API plus dead-domain APIs).

Best-covered: `academic` (36), `fees` (24), `cases` (18), `workflow` (18), `auth` (14), `notifications` (13), `reports` (12), plus the security suites (`test_multi_tenant`, `test_tenant_isolation`, `test_permissions`, `test_rbac_router_enforcement`, `test_finance_security`, `test_outbox`, `test_async_hardening`) which exercise cross-cutting concerns on every domain.

Least-covered: `attendance_intelligence` API, `documents`, `academic_ops` API, `billing` admin, `institution` (direct API tests absent; covered indirectly through tenant/integration suites).

---

## 9. How to regenerate

```bash
# 1. API must be importable (venv): regenerates the CSV appendix
cd apps/api && uv run python _api_matrix.py > _api_routes_audit.tsv && uv run python _matrix_gen.py

# 2. Frontend URL extraction
cd apps/web && python _extract_urls.py > _fe_urls.txt

# 3. Cross-match + findings: see the analysis scripts used in this audit
#    (steps are documented inline in this file's method section)
```

Note: `_api_matrix.py`, `_matrix_gen.py`, `_extract_urls.py`, `_api_routes_audit.tsv`, `_fe_urls.txt`, `_openapi_audit.json` are **audit scratch artifacts** — regenerated per audit, not part of the deliverable.

---

## 10. Caveats

- Role/tenant columns reflect **declared dependencies**; handler-internal authorization is annotated where spot-checked, not exhaustively re-verified per route (the multi-tenant + RBAC + finance security suites cover the negative paths end-to-end).
- "Expected failure statuses" derive from the registered exception contract; a route that raises an unhandled framework exception still yields 500 by design (no 500-for-expected-condition was found in this pass).
- The CSV's `test_coverage` is heuristic (dedicated test dir vs textual references) — see §8 for the reliable part.
