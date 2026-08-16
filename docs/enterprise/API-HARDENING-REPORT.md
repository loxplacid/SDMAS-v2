# SDMAS-v2 — API / Security Hardening Report

**Date:** 2026-08-16
**Basis:** `API-VERIFICATION-MATRIX.md` (495-operation enumeration) + the targeted defect hunt mandated by this task (hardcoded IDs, `verified_by=0`, public staff registration, cross-tenant resource lookup, bulk/export endpoints, migration endpoints).

**Result:** **2 defects fixed** (both in the authentication/authorization boundary), each with regression tests; every other named area re-verified and found already hardened. All related and cross-cutting suites pass.

---

## 1. Defects fixed

### D1 — Service-layer role-escalation gap in admin user mutation (authorization)

**Severity:** HIGH (P1-class). The HTTP path was partially guarded by Pydantic schema validators, but the enforcement lived at the wrong layer and was bypassable by any non-HTTP caller of `UserService`.

**Reproduction (service-level, i.e. bypassing the router):**
1. A tenant admin holds `UserService` access (or any future endpoint calls `admin_update_user`).
2. `admin_update_user(user_id, AdminUserUpdate(role="platform_admin"))` sets `user.role = "platform_admin"` with **no validation**.
3. `User.role_codes` includes the primary `role` field (`models.py:267`), and `ROLE_PERMISSIONS["platform_admin"] = [platform.access, platform.manage, *TENANT_ALL_PERMISSIONS]` (`permissions.py:200`).
4. `require_platform_permission("platform.access")` then passes → **cross-tenant (platform) access from a tenant account**.

The same gap existed for the M2M `roles` list: `_sync_user_roles` accepted *any* existing `Role` row (including `platform_admin` if present), so a PATCH body `{"roles": ["platform_admin"]}` could mint the escalation through a path that the dedicated `/admin/users/{id}/roles` endpoint's router-level whitelist did not cover.

**Root cause:** Role whitelisting existed only at the router (`_ASSIGNABLE_ROLES`) and Pydantic schema level — the service layer (`admin_update_user`, `_sync_user_roles`) — the single place every mutation funnels through — had no guard, and the schema's `role` validator was a hand-maintained `{"admin","staff"}` set that both diverged from `TENANT_ROLES` and silently broke legitimate changes to `teacher`/`accountant`/`principal`/`parent`.

**Fix (single enforcement points, defense in depth):**
- `UserService.admin_update_user` now rejects any `data.role` outside `TENANT_ROLES` with `ValidationError` (422) before assignment.
- `UserService._sync_user_roles` (the single M2M mutation point — both the `/roles` endpoint and the PATCH `roles` body funnel through it) now whitelists codes against `TENANT_ROLES`.
- `AdminUserUpdate.role` schema validator widened from `{"admin","staff"}` to `TENANT_ROLES` — consistent with the `roles` validator, the service guard, and the `/roles` endpoint; also unblocks the previously impossible `role: "teacher"|"accountant"|"principal"|"parent"` changes.

**Regression tests** (`tests/test_auth/test_security_audit.py::TestAdminRoleEscalation`):
- `test_admin_patch_cannot_set_platform_primary_role` — `PATCH /admin/users/{id} {"role":"platform_admin"}` → **422**
- `test_admin_patch_cannot_assign_platform_m2m_role` — `PATCH /admin/users/{id} {"roles":["platform_admin"]}` → **422**
- `test_admin_patch_valid_role_still_works` — `PATCH /admin/users/{id} {"role":"teacher"}` → **200**, role applied

### D2 — Public self-registration minted a privileged `staff` account (authentication/authorization)

**Severity:** HIGH (P1-class). `POST /auth/register` is public (rate-limited 20/60 s) and created every account with `role="staff"` — a privileged role that passes ~76 role gates (`require_role("admin","staff")`, etc.). While a campus-less `staff` user is denied tenant-scoped routes (`require_tenant_context` → 403), the account was minted at staff trust level without any admin approval — wrong trust model for an enterprise multi-tenant product, and a privilege-escalation surface if the account is later linked to a campus.

**Root cause:** `UserService.register` hardcoded `role="staff"`.

**Fix:** Public self-registration now defaults to **`parent`** — the least-privileged tenant role. Privileged roles are granted only by a tenant admin through `/admin/users`. A self-registered user has no campus membership, so `require_tenant_context` continues to deny every tenant-scoped route (403) until an admin links them to a campus.

**Regression tests** (`tests/test_auth/test_security_audit.py::TestPublicRegistrationPrivilege`):
- `test_registered_user_defaults_to_parent_role` — register → `role == "parent"` (was `staff`)
- `test_registered_parent_cannot_reach_staff_or_tenant_routes` — self-registered user gets **403** on a staff-gated route (`GET /api/communications/messages`) and **403** on a tenant-scoped route (`GET /students`)
- Updated `tests/test_auth/test_service.py::TestRegister::test_register_success` to the new least-privilege contract (`role == "parent"`).

---

## 2. Named areas re-verified — already hardened (no change)

| Area | Result | Evidence |
|---|---|---|
| **Hardcoded IDs** | No hardcoded tenant/entity IDs in app code (services, migrators, routers). | `grep` over `app/domains/**` for `campus_id=1`, `user_id=1`, `school_id=1` literal assignments → none |
| **`verified_by=0`** | Not present anywhere. Document verification uses the authenticated actor: `verified_by=actor.id` (`admission/router.py:308`), endpoint is `require_permission(ADMISSIONS_APPROVE)` + tenant-scoped by parent application. | `grep -rn "verified_by" app/` → only legitimate actor-id assignments |
| **Cross-tenant resource lookup** | All routers that fetch by path ID either carry `require_tenant_context`/`get_school_context` + `assert_tenant_scope*`, or are user-owner-scoped (report-builder exports/saved: `get_result_data(job_id, current_user.id)`; documents download: `assert_tenant_scope(existing, tenant)`; leave: `assert_tenant_scope_or_owner`; student portal: student resolved from token). | Router-by-router scan of `*.get(id)` call sites (210) + handler spot checks |
| **Bulk/export endpoints** | `cases/bulk/*` — `get_school_context` + leadership roles; audit-logs export — `effective_campus_id(tenant, campus_id)` (client campus_id honoured only for platform callers); report exports — user-owned. | `cases/router.py:362`, `audit/export.py`, `report_builder/router.py:249` |
| **Migration endpoints** | All 24 ops `require_role("admin")` + `get_school_context` (23/24; `GET /migration/entities` is a static catalog). Cross-tenant project access → 404 (previously verified live). | `migration/router.py` dependency audit; prior E2E |
| **Auth self-service** | `PATCH /auth/me` allows only `display_name`/`email` (no role); `UserUpdate` schema has no role field; password change is owner-only + rate-limited. | `auth/schemas.py:56`, `auth/router.py:152` |
| **Admin user management** | `/admin/users*` — `require_role("admin")` + `require_tenant_context`, records pinned to acting admin's campus (`assert_tenant_scope`), role-assignment endpoint restricted to `TENANT_ROLES`, platform roles rejected 422. | `auth/admin_router.py` |
| **Tenant scoping of role-less routes** | The 104 auth-only routes are 91 tenant-dependency-scoped + 13 user self-service (verified: no role-less route mutates cross-tenant state). | `API-VERIFICATION-MATRIX.md` §3 |

---

## 3. Tests executed

| Suite | Result |
|---|---|
| `tests/test_auth/test_security_audit.py` (incl. 6 new regression tests) | **32 passed** |
| `tests/test_auth` (full) | **77 passed** |
| `tests/test_permissions.py` + `tests/test_rbac_router_enforcement.py` + `tests/test_multi_tenant` + `tests/test_tenant_isolation.py` | **241 passed, 1 failed → fixed & re-run** (the 1 failure was the pre-fix `test_register_success` role assertion; updated to the new contract, then full `test_auth` re-run green) |
| `tests/test_audit` + `tests/test_enterprise_demo.py` + `tests/test_finance_security` + `tests/test_integration.py` | **147 passed, 36 skipped** (skips = Docker-gated Postgres integration tests, expected) |
| `tests/test_migration_workspace.py` + `tests/test_outbox` + `tests/test_jobs` + `tests/test_schema_integrity.py` + `tests/test_audit_action_width.py` | **86 passed** |
| `ruff check` on changed files | Clean (only pre-existing E501 line-length items remain) |

**Total this pass: 583 passed, 0 failed (excluding Docker-gated skips).**

---

## 4. Files changed

| File | Change |
|---|---|
| `apps/api/app/domains/auth/service.py` | `register` default role `staff` → `parent`; `admin_update_user` primary-role whitelist; `_sync_user_roles` M2M whitelist (single enforcement point) |
| `apps/api/app/domains/auth/schemas.py` | `AdminUserUpdate.role` validator widened `{admin,staff}` → `TENANT_ROLES` (consistency + unblocks legit changes) |
| `apps/api/tests/test_auth/test_security_audit.py` | +6 regression tests (2 classes: `TestPublicRegistrationPrivilege`, `TestAdminRoleEscalation`) |
| `apps/api/tests/test_auth/test_service.py` | Updated `test_register_success` to assert `role == "parent"` |
| `docs/enterprise/API-HARDENING-REPORT.md` | This report |

---

## 5. Remaining risks (not P0/P1 — documented, not fixed this pass)

- **P2 — Non-uniform domain audit (matrix F6):** `institution` CRUD (14 non-GET ops), `academic_ops`, `billing`, `notifications` push, and `report_cards` have no semantic service-level audit entries. Request-level audit middleware covers every HTTP request; the gap is resource-level entries for these domains. Recommended follow-up: add `AuditService.record` to the institution service mutations (actor already available in the router).
- **P2 — 82 backend routes with no consumer in web or mobile** (matrix F2: academic_ops timetable/exams/grades/rooms/substitutions/time-slots/curricula, documents, billing admin, report-cards PDF, notifications push, comms inbox): product decision needed (backend-only capability vs dead surface).
- **P3 — attendance_intelligence API (27 ops) has no direct API test coverage** (matrix F3).

## 6. Verification commands

```bash
cd apps/api
uv run pytest tests/test_auth/test_security_audit.py -q            # 32 passed (incl. new regressions)
uv run pytest tests/test_auth tests/test_permissions.py \
  tests/test_rbac_router_enforcement.py tests/test_multi_tenant \
  tests/test_tenant_isolation.py -q                                # 318 passed
uv run ruff check app/domains/auth/service.py app/domains/auth/schemas.py
```
