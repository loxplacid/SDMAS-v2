# RBAC & Authorization Audit — SDMAS v2

**Status: VERIFIED (P0/P1 findings fixed and regression-tested)**
**Date:** 2026-08-12 — first pass (router-level role enforcement) + second pass
(behavioral tests for exports, bulk operations, financial actions, tenant
management, stale sessions and token manipulation)

This audit enumerates the role/permission model, the protected surfaces on
both sides of the stack, and the result of adversarial privilege-escalation
testing. The mandate was explicit: *frontend hiding is not authorization —
backend must independently enforce every privileged operation.*

---

## 1. Roles & permission model

Roles are defined once in `apps/api/app/domains/auth/permissions.py`
(`ROLE_PERMISSIONS`) and mirrored for fast frontend checks in
`apps/web/src/types/permissions.ts`. Seven tenant roles plus one platform
role:

| Role | Scope | Backend authority (summary) |
|---|---|---|
| `platform_admin` | **cross-tenant** | Explicit `platform.access` + `platform.manage` + all tenant permissions. NOT a DB role row; only assignable by direct platform seeding. |
| `admin` | tenant | Every tenant permission (`TENANT_ALL_PERMISSIONS`). Never satisfies a platform check — `admin` ≠ platform admin. |
| `principal` | tenant | Students view/update, teachers view, attendance view, fees view, academic create/update/view, subjects view, admissions, reports, analytics, notifications, leave view/approve, audit view, workflow view/manage. |
| `accountant` | tenant | Students view, full fee lifecycle (create/update/payment/refund/export), reports, analytics view, notifications. |
| `staff` | tenant | Students view/create/update, academic view, subjects view, attendance view/record/update/export, notifications view/create, leave view/create/update. |
| `teacher` | tenant | Students view, attendance view/record/update, notifications, leave view/create. |
| `student` | tenant | Attendance view, fees view, notifications, leave view. |
| `parent` | tenant | Students view, attendance view, fees view, notifications. |

### Enforcement primitives (backend)

- `get_current_user` / `require_authenticated_user` — JWT access-token auth
  (`type == "access"` enforced; refresh tokens never double as bearer creds).
- `require_role(*roles)` — coarse role check against `role_codes` (primary
  role + M2M `assigned_roles`).
- `require_permission(*perms)` — granular DB-backed check with registry
  fallback.
- `require_platform_permission(...)` — the ONLY gate for cross-tenant access.
- `require_tenant_context` / `get_school_context` — fail-closed tenant
  resolution from DB memberships; unscoped non-platform users get 403.
- Global default-deny `AuthGateMiddleware` — every non-allowlisted path
  requires a valid access token, even if a router forgot a `Depends`.
- Tenant guards (`effective_campus_id`, `assert_tenant_scope`,
  `assert_tenant_scope_or_owner`, `inject_campus`) — close the IDOR class at
  the query/object layer.

---

## 2. Permission matrix (backend `ROLE_PERMISSIONS`, authoritative)

| Permission | admin | principal | accountant | staff | teacher | student | parent |
|---|---|---|---|---|---|---|---|
| students.view / create / update / delete / export | ✓ | ✓/–/✓/–/– | ✓/–/–/–/– | ✓/✓/✓/–/– | ✓/–/–/–/– | – | ✓ |
| teachers.view / create / update / delete | ✓ | ✓/–/–/– | – | – | – | – | – |
| attendance.view / record / update / export / approve | ✓ | ✓/–/–/–/– | ✓/–/–/–/– | ✓/✓/✓/✓/– | ✓/✓/✓/–/– | ✓/–/–/–/– | ✓/–/–/–/– |
| fees.view / create / update / delete / record_payment / refund / export | ✓ | ✓/–/–/–/–/–/– | ✓/✓/✓/–/✓/✓/✓ | – | – | ✓/–/–/–/–/–/– | ✓/–/–/–/–/–/– |
| academic.view / create / update / delete | ✓ | ✓/✓/✓/– | – | ✓/–/–/– | – | – | – |
| subjects.view / create / update / delete | ✓ | ✓/–/–/– | – | ✓/–/–/– | – | – | – |
| admissions.view / create / update / approve | ✓ | ✓/✓/✓/✓ | – | – | – | – | – |
| reports.view / create / export | ✓ | ✓/✓/✓ | ✓/✓/✓ | – | – | – | – |
| analytics.view / export | ✓ | ✓/✓ | ✓/– | – | – | – | – |
| notifications.view / create / delete | ✓ | ✓/–/– | ✓/–/– | ✓/✓/– | ✓/–/– | ✓/–/– | ✓/–/– |
| operations.view / execute / export | ✓ | – | – | – | – | – | – |
| users.view / create / update / delete / roles.manage | ✓ | – | – | – | – | – | – |
| audit.view / export | ✓ | ✓/– | – | – | – | – | – |
| leave.view / create / update / approve | ✓ | ✓/–/–/✓ | – | ✓/✓/✓/– | ✓/✓/–/– | ✓/–/–/– | – |
| institution.view / manage | ✓ | – | – | – | – | – | – |
| workflow.view / manage | ✓ | ✓/✓ | – | – | – | – | – |
| platform.access / manage | platform_admin only | – | – | – | – | – | – |

---

## 3. Protected surface inventory

### Backend (45 routers, ~180 routes)

- **Permission-gated (granular):** `academic_ops`, `attendance_intelligence`,
  `admission` (approve), `class_360`, `student_360`, `billing` (plans),
  `teacher_360`, and — after this audit — `academic`, `attendance`, `student`.
- **Role-gated (coarse but tenant-scoped):** `audit` (admin), `workflow`
  (admin CRUD), `jobs` (admin `/all` + `/stats`), `migration` (admin +
  `get_school_context`), `documents` (staff/teacher/accountant/principal),
  `communications` (admin/staff/teacher/principal), `cases`
  (admin/principal/staff; leadership for mutations), `risk`, `data_quality`,
  `timeline`, `command_center`, `reports` (rollover), `billing/admin`.
- **Tenant-scoped self-service (`get_current_user` + tenant):**
  `notifications`, `leave`, `jobs`, `search`, `institution` reads,
  `report_builder`, `parent`, `student_portal`.
- **Global default-deny gate** covers every private path; public allowlist is
  small and audited: `/health`, `/ready`, `/metrics`, `/docs`, `/redoc`,
  `/openapi.json`, `/auth/register`, `/auth/login`, `/auth/refresh`,
  `/billing/plans*`, `/billing/webhook/*` (signature-verified).

### Frontend (`App.tsx` + `RoleGuard`/`hasRouteAccess`)

- Workspace routes for teacher/student/parent/principal/accountant/staff and
  admin-only routes (migration, audit logs, approvals) are RoleGuard-wrapped.
- A set of shared domain pages (`/students`, `/academic*`, `/attendance*`,
  `/fees*`, `/reports*`, `/analytics*`, `/users`, `/operations*`,
  `/communications*`, `/admissions*`, `/leave*`) rely on `ProtectedRoute`
  only — no `RoleGuard`. This is **not** a security boundary (backend
  enforces), but a UX gap: denied roles see error states instead of a
  redirect. Documented as a P2 follow-up, not fixed here.

---

## 4. Privilege-escalation attempts

| Attack vector | Result before fix | Result after fix |
|---|---|---|
| Student/Parent `POST /api/classes`, `/sections`, `/enrollments`, `/subjects`, `/teachers`, `/academic-years`, `PATCH/DELETE /api/classes/{id}` etc. | **200/204 (escalation)** | **403** |
| Student/Parent `POST /attendance`, `/attendance/daily`, `PATCH /attendance/{id}` | **201/200 (escalation)** | **403** |
| Student `GET /students`, `GET /students/{id}` (PII: name/email/DOB/guardian) | **200 (full roster)** | **403** |
| Tenant admin `POST /admin/users/{id}/roles` with `["platform_admin"]` | 404 (blocked only because no `platform_admin` Role row existed — **latent**) | **422 (explicit validation)** |
| Tenant admin `POST /admin/users/{id}/roles` with unknown code | 404 | **422** |
| Tenant admin `PATCH /admin/users/{id}` `role: "platform_admin"` | blocked (schema allows admin/staff only) | blocked + now uses shared `TENANT_ROLES` set |
| `alg: none` / wrong-alg JWT | blocked (`algorithms=[settings.jwt_algorithm]`) | blocked |
| Refresh token used as bearer | blocked (`type == "access"` check) | blocked |
| Cross-tenant object-ID substitution (all domains) | **previously fixed** (prior audit; still verified green) | **403/404** |
| Public self-registration → `staff` with no campus | 403 on tenant endpoints (fail-closed) | 403 (no change) |

| Staff `GET /api/reports/export/students` + `/export/payments`, `/api/fees/*` reads | **200 (PII + full payment ledger)** | **403** |
| Staff `POST /api/reports/batch/enroll` + `/batch/fee-dues` | **200 (bulk escalation)** | **403** |
| Staff `POST /api/cases/bulk/assign` (and all `/bulk/*`) | **422 for everyone — routes shadowed by `/{case_id}/*`, bulk ops unreachable** | **403 (staff) / 200 (admin executes)** |
| Tenant admin `POST /api/institution/institutions` / foreign-`institution_id` campus | already blocked | blocked (now test-pinned) |
| `alg:none` forged JWT / refresh-token-as-bearer / deactivated user's token | blocked | blocked (now test-pinned) |

No P0 issues remain. All P1 issues fixed.

---

## 5. Findings

### Fixed (P1)

1. **`academic/router.py` — write endpoints enforced tenant context only.**
   Any authenticated campus member (student/parent included) could create,
   modify, and delete academic structure (years, classes, sections,
   enrollments, terms, subjects, teachers, teacher assignments).
   **Fix:** `require_permission(ACADEMIC_CREATE/UPDATE/DELETE)`,
   `SUBJECTS_CREATE/UPDATE`, `TEACHERS_CREATE/UPDATE` on every write
   endpoint. Reads remain tenant-scoped by design (teacher UI depends on
   them; teacher role has no `academic.view`).

2. **`attendance/router.py` — record/update enforced tenant context only.**
   Any campus member could fabricate or amend attendance (impacts
   attendance analytics, fees, and discipline outcomes).
   **Fix:** `ATTENDANCE_RECORD` on creates, `ATTENDANCE_UPDATE` on patch;
   `ATTENDANCE_VIEW` on all reads (every role holds it — verified).

3. **`student/router.py` — `GET /students` and `GET /students/{id}` had no
   permission check.** A `student`-role user could enumerate the entire
   campus roster with PII.
   **Fix:** `STUDENTS_VIEW` on both. Parent/teacher hold it (portal +
   roster workflows intact); student does not.

4. **`admin_router.py` — `POST /admin/users/{id}/roles` accepted arbitrary
   role codes.** It was only *accidentally* safe because no `platform_admin`
   Role row exists; any future seed or migration creating one would turn it
   into instant tenant→platform escalation, and unknown codes produced
   confusing 404s instead of validation.
   **Fix:** validate against `TENANT_ROLES` (platform roles excluded) → 422.
   Consolidated the previously-duplicated role set into a single
   `TENANT_ROLES` constant in `permissions.py`, now referenced by both
   `schemas.py` and `admin_router.py` (drift-proof).

5. **`reports/router.py` — over-permission cluster.** Exports
   (`/export/students`, `/export/payments`), financial reports
   (`/fees/collection`, `/fees/outstanding`), detailed receipts, and batch
   operations (`/batch/enroll`, `/batch/fee-dues`) were gated only by role
   `admin`/`staff` — so `staff`, who holds **no** `fees.view`, `students.export`,
   `fees.export` or `academic.create` in the matrix, could export the full
   student roster and the payment ledger and read financial reports.
   **Fix:** matrix-accurate `require_permission` gates (`STUDENTS_EXPORT`,
   `ATTENDANCE_EXPORT`, `FEES_EXPORT`, `FEES_VIEW`, `ACADEMIC_CREATE`,
   `FEES_CREATE`). Staff retain attendance export/report reads — those are
   granted in the matrix.

6. **`fees/router.py` — read endpoints enforced tenant context only.** Staff
   (zero fee permissions) could read fee structures, dues, payments, and
   per-student summaries.
   **Fix:** `FEES_VIEW` on every read endpoint; writes were already gated
   (`FEES_CREATE`/`FEES_UPDATE`, payment/refund perms).

7. **`cases/router.py` — `/bulk/*` routes shadowed by `/{case_id}/*`.** The
   four bulk endpoints were registered *after* the `/{case_id}/...` family,
   so `POST /api/cases/bulk/assign|priority|status|due-date` always matched
   `/{case_id}/assign` with `case_id="bulk"` → 422. Bulk case operations
   were **unreachable for every role** (found by the behavioral test, not
   static review).
   **Fix:** int path converters on the case-id routes (`/{case_id:int}`) so
   the `/bulk/*` routes win. Staff → 403 (leadership gate); admin executes.

### Verified present / not a finding

- `switch_school` validates membership server-side before issuing a new
  campus-scoped token.
- `PATCH /me` cannot change roles; `AdminUserUpdate.role` restricts the
  primary role to `admin`/`staff`.
- Report builder data is campus-filtered in every builder
  (`campus_id` threaded from the caller).
- `require_role("admin")` on audit/workflow/jobs is scoped by an additional
  `require_tenant_context`.
- Billing plans/entitlements require `platform.manage`; payment webhook is
  signature-verified + content-derived idempotency keyed.

### Remaining observations (P2/P3 — not fixed)

| # | Severity | Observation |
|---|---|---|
| 1 | P2 | Frontend `hasRouteAccess`/nav grants principal the `/attendance*` pages, but the matrix is attendance-**view-only** for principal — a principal opening a record/update control now gets 403. Backend is correct; restrict the principal's attendance UI or document. |
| 2 | P2 | `GET /api/teachers` (with email) is tenant-only, not `TEACHERS_VIEW`-gated. Gating it would break the teacher dashboard (it lists teachers via `teacherApi.list`) because the `teacher` role lacks `TEACHERS_VIEW`. Decision: keep open within campus; revisit if the matrix is intended to be stricter. |
| 3 | P2 | A set of shared frontend routes (`/students`, `/academic`, `/attendance`, `/fees`, `/reports`, `/analytics`, `/users`, `/operations`, `/communications`, `/admissions`, `/leave`) lack `RoleGuard`. Backend now rejects each denied operation (403), but users see error states rather than redirects. |
| 4 | P3 | `analytics` router is role-gated to `admin`/`staff` while `principal` is granted `analytics.view` in the matrix (granted-but-unreachable) and `staff` can reach analytics it is not granted. Endpoints are tenant-scoped, so this is a matrix/role-gate mismatch, not a data leak. |
| 5 | P3 | `audit` endpoints require role `admin` while the matrix grants `principal` `audit.view`. Restrictive direction; principal audit UI (if any) would 403. |
| 6 | P3 | `/auth/register` is public and creates `staff`-role accounts (no campus → fail-closed 403 on tenant endpoints). Consider an env toggle (`ALLOW_PUBLIC_REGISTRATION`) for production hardening. |

---

## 6. Changes

| File | Change |
|---|---|
| `apps/api/app/domains/academic/router.py` | Permission checks on all write endpoints |
| `apps/api/app/domains/attendance/router.py` | `ATTENDANCE_RECORD`/`UPDATE` on writes, `ATTENDANCE_VIEW` on reads |
| `apps/api/app/domains/student/router.py` | `STUDENTS_VIEW` on list + get |
| `apps/api/app/domains/auth/admin_router.py` | Role-code validation via `TENANT_ROLES` |
| `apps/api/app/domains/auth/permissions.py` | New `TENANT_ROLES` single source of truth |
| `apps/api/app/domains/auth/schemas.py` | `AdminUserUpdate.valid_roles` uses `TENANT_ROLES` |
| `apps/api/app/domains/reports/router.py` | Matrix-accurate permission gates on exports / financial reports / batch endpoints |
| `apps/api/app/domains/fees/router.py` | `FEES_VIEW` on all read endpoints |
| `apps/api/app/domains/cases/router.py` | `{case_id:int}` path converters — unshadows the `/bulk/*` routes |
| `apps/api/tests/test_rbac_router_enforcement.py` | **New** — 41 regression tests (was 25; second pass added exports, bulk ops, finance reads, tenant mgmt, session/token manipulation) |

## 7. Tests executed

- `tests/test_rbac_router_enforcement.py` — **41 passed, 0 failed**:
  - academic/attendance/student mutations — student & parent denied (403),
    principal view-only on attendance, staff/teacher/admin/principal
    legitimate paths intact;
  - `platform_admin`/unknown role codes → 422; valid tenant role
    assignment still works;
  - exports (students/payments) denied for staff, granted for
    admin/accountant; staff attendance export intact;
  - financial report reads denied for staff/teacher, granted for
    accountant/student (fees.view);
  - bulk ops (reports batch, cases bulk-assign) denied for staff, executed
    by admin;
  - tenant management: institution creation + foreign-campus creation
    blocked for tenant admin, own-campus creation allowed;
  - token manipulation: `alg:none` forged JWT rejected (401) on open and
    protected routes, refresh token rejected as bearer (401), deactivated
    user's token rejected (401).
- Combined regression — group 1 (`test_rbac_router_enforcement`,
  `test_academic`, `test_attendance`, `test_student`, `test_permissions`,
  `test_auth`, `test_multi_tenant`, `test_tenant_isolation`):
  **524 passed, 0 failed**.
- Combined regression — group 2 (`test_communications_context`,
  `test_migration_workspace`, `test_cases`, `test_workflow`, `test_fees`,
  `test_finance_security`): **315 passed, 0 failed**.
- **Total: 839 passed, 0 failed.**
- Ruff (`E9,F821,F822,F811,I001`) on all changed files: **clean**.

## 8. Verify

```bash
cd apps/api
uv run pytest tests/test_rbac_router_enforcement.py -q
uv run ruff check app/domains/academic/router.py app/domains/attendance/router.py \
  app/domains/student/router.py app/domains/auth/admin_router.py \
  app/domains/auth/schemas.py app/domains/auth/permissions.py \
  tests/test_rbac_router_enforcement.py --select E9,F821,F822,F811,I001
```
