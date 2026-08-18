# TENANCY MODEL — SDMAS v2 Multi-Tenancy

Date: 2026-08-17 · Source: `apps/api/app/multi_tenant/` (verified). The
root-level `TENANCY.md` remains canonical; this is the architecture-set view.

SDMAS is **structurally multi-tenant**: isolation is enforced at query
construction time by the framework, not by developer discipline. Tenant A
can never read Tenant B's rows even by guessing an ID.

---

## 1. Enterprise hierarchy

The tenancy unit is the **campus** (`campus_id`). `Institution`,
`SchoolGroup` and `Region` are organizational aggregations, **not** tenant
units — they never carry tenant data and are never filtered by campus.

```
Institution (org)
  └── SchoolGroup
        └── Region
              └── Campus   ← the data-isolation unit
                    └── Department
```

`campus_id` remains the isolation boundary for every tenant-owned row.
Hierarchy administrators are authorized over the campuses **inside** their
subtree; the boundary is enforced in SQL as
`campus_id IN (SELECT id FROM campuses WHERE …)` (see
`tenant_filter_for_scope` in `multi_tenant/registry.py`).

## 2. The chain

```
Authenticated User
  → Tenant Membership / Hierarchy Assignment
    (user_school_memberships / organization_assignments)
  → TenantContext            (multi_tenant/models.py)
  → Tenant-Scoped Query      (TenantScopedRepository — multi_tenant/repository.py)
  → Resource-Level Guards    (multi_tenant/guards.py)
```

## 3. TenantContext (`multi_tenant/models.py`)

Resolved per request by the tenant middleware from the token +
memberships/assignments. Carries:

- `campus_id` + `institution_id` — the concrete school scope,
- `school_group_id` / `region_id` — set only for group/region admin scopes,
- `user_id` — the acting user,
- `platform: bool` — explicit cross-tenant authorization (`platform.access`),
- `allow_cross_tenant` — hierarchy-admin or platform fallback flag.

The **scope level** (`TenantScopeLevel`) classifies the caller's granularity
within the hierarchy — the most specific non-empty scope wins:

| Scope level | Meaning |
|---|---|
| `CAMPUS` | The classic tenant: pinned to one campus |
| `REGION` | Region admin: all campuses under one region |
| `GROUP` | School-group admin: all campuses under one group |
| `ORGANIZATION` | Org admin: all campuses under one institution |
| `PLATFORM` | Explicit `platform.*` grant; across all boundaries |
| `NONE` | No scope — **denied by default** for tenant-owned data |

Three explicit states:

| State | Meaning |
|---|---|
| **Tenant/hierarchy-scoped** (`is_hierarchy_scoped=True`) | Pinned to a campus or subtree; filtered by `campus_id` (directly or via subquery) |
| **Platform** | Explicit `platform.*` grant; may query across campuses |
| **Unscoped** (neither) | **Denied by default** for tenant-owned data |

`is_tenant_scoped` is intentionally campus-only for backward compatibility;
use `is_hierarchy_scoped` / `scope_level` for hierarchy admins.

Dependencies: `get_current_tenant` (lenient) and `require_tenant_context`
(raises 403 for unscoped non-platform callers). Platform operations use
`require_platform_permission()` from `auth/dependencies.py`.

## 4. Hierarchy assignments (`organization_assignments`)

Subtree administration is authorized via `OrganizationAssignment` (not
`UserSchoolMembership`), which grants an admin a scope over one node:

- `org_admin` → `ORGANIZATION` scope over one `Institution`.
- `group_admin` → `GROUP` scope over one `SchoolGroup`.
- `region_admin` → `REGION` scope over one `Region`.
- `department` → a campus department (limited; campus-scoped).

`resolve_tenant_context` gives assignments precedence over memberships.
Assignments never imply platform access.

## 5. Model classification (`multi_tenant/registry.py`)

Every SQLAlchemy model is classified:

- **TENANT_DIRECT** — carries its own `campus_id` (most tenant-owned rows:
  students, classes, fee_dues, payments, transaction_logs,
  attendance_records, documents, cases, migration_projects, notifications,
  communication_messages, …).
- **PARENT_TENANT_PATHS** — inherits tenancy from a parent row (children
  such as case_events, document_versions, message_recipients,
  admission_documents) via `assert_tenant_scope_by_parent_id`.
- **PLATFORM** — global/system data (plans, roles, permissions,
  institutions) never filtered; reachable only through scoped or platform
  callers.

`registry.tenant_filter_for(model, campus_id)` returns the predicate applied
to queries for the classic per-campus scope.
`registry.tenant_filter_for_scope(model, tenant)` returns the subtree
predicate for hierarchy admins, applied as a `campus_id IN (SELECT …)`
subquery so the isolation boundary is enforced in the SQL.

## 6. TenantScopedRepository (`multi_tenant/repository.py`)

Canonical base for every tenant-owned repository:

- `scoped_query(model)` / `scoped_count(model)` build SELECTs with the
  tenant predicate **already applied**; raise `AuthorizationError` for
  unscoped non-platform callers (default-deny). Hierarchy admins get the
  subtree predicate for their scope level.
- `get_by_id(model, id)` — a row owned by another campus **does not exist**
  to a scoped caller.
- `exists`, `first`, `_list_by_tenant` — all tenant-filtered.
- `_has_platform_access()` — `tenant=None` (legacy internal callers) or
  explicit platform → unfiltered; everything else denied.

## 7. Guards (`multi_tenant/guards.py`)

- `effective_campus_id(tenant, client_campus_id)` — pins lists to the
  caller's campus; a client-supplied `campus_id` is ignored for scoped
  users, honoured only for platform callers.
- `assert_tenant_scope(entity, tenant, resource)` — 403 when the entity's
  campus differs from the tenant's (or is untagged).
- `inject_campus(entity, tenant)` — tags new rows with the caller's campus
  on creation (client-supplied values overwritten).
- `assert_tenant_scope_or_owner` — legacy untagged-row exception for the
  record's own user.
- `assert_tenant_scope_by_parent_id` — children inheriting tenancy.
- Hierarchy guards: `assert_campus_in_scope`, `assert_school_group_in_scope`,
  `assert_region_in_scope`, `assert_institution_in_scope` — verify a target
  entity lies inside the caller's subtree, 403 otherwise.

## 8. Platform-scoped queries

Explicit platform access is the **only** opt-in to cross-tenant data.
Nothing silently grants it: requires a `platform.*` permission on the user
and, at endpoint level, `require_platform_permission()`.

## 9. Legacy data

Pre-tenancy rows may carry `campus_id = NULL`. Scoped callers cannot see
them through tenant-filtered queries; guards treat untagged rows as
invisible to scoped tenants (narrow `assert_tenant_scope_or_owner`
exception for a user's own records). Migration `c21889d4e562` flags legacy
null-campus records.

## 10. Tenant propagation across child tables (DATA_MODEL §1, verified)

20 child tables lack direct `campus_id` but are reached **only** through
parent-scoped queries (e.g. `CaseEvent.case_id`,
`DocumentVersion.document_id`,
`MessageRecipient.message_id IN (SELECT id FROM messages WHERE campus_id=…)`).
The adversarial multi-tenant suite verified no isolation gap exists via these
paths (see `docs/enterprise/TENANT-RBAC-VERIFICATION.md`).

## 11. Demo tenants (Step 5, `scripts/seed_enterprise_demo.py`)

- Three isolated demo tenants: **Apex Global School**, **St. Jude Public
  Academy**, **Metropolitan Institute of Tech** — distinct datasets, own
  admins (apex.admin / stjude.admin / mit.admin), demo-only credentials,
  deterministic + idempotent seeding (`./enterprise demo-seed` /
  `demo-reset`).
- Isolation is proven at the **API level** by `test_enterprise_demo.py`
  (14 tests) — login as A → Tenant B student/fee/audit/migration denied.
- See `docs/enterprise-demo.md`.

## 12. Verification evidence

- `tests/test_multi_tenant/test_security_suite.py` — 28 tests proving
  cross-tenant read/update/delete/search/export/batch denial and platform
  gating.
- `tests/test_multi_tenant/test_adversarial_three_tenant.py` — three-tenant
  IDOR across every major domain (students, academics, attendance, fees,
  invoices, payments, ledger, reports, documents, audit, notifications,
  migration jobs, background jobs).
- `tests/test_security_acquisition/` — 64 tests incl. tenant isolation +
  IDOR for jobs, notifications, audit, documents, guardian junctions.
- `tests/test_enterprise_hierarchy.py` — 28 tests covering subtree
  isolation for org/group/region admins at the repository, guard, and
  HTTP-API levels (list/create scoping, cross-subtree denial,
  cross-institution denial), plus assignment precedence and migration
  schema parity.
- `docs/enterprise/MULTI-TENANT-SECURITY-AUDIT.md` and
  `docs/enterprise/TENANT-RBAC-VERIFICATION.md`.

## 13. Design rules (AGENTS.md §6)

- Every query must be scoped to the caller's campus_id.
- Use tenant-scoped repositories; never bypass tenant guards.
- Never trust a frontend tenant ID as a security boundary — backend is
  authoritative.
- Cross-tenant access is forbidden even for admin users (admin is
  own-campus; only explicit platform permissions cross boundaries).
