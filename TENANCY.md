# SDMAS v2 — Tenancy

The canonical multi-tenant framework lives in `apps/api/app/multi_tenant/`.
It makes cross-tenant data leakage **structurally difficult or impossible**
by scoping queries at construction time rather than relying on developers
remembering to check every fetched record.

## The chain

```
Authenticated User
  → Tenant Membership / Hierarchy Assignment
    (user_school_memberships / organization_assignments)
  → TenantContext            (multi_tenant/models.py)
  → Tenant-Scoped Query      (TenantScopedRepository — multi_tenant/repository.py)
  → Resource-Level Guards    (multi_tenant/guards.py)
```

## Enterprise hierarchy

The tenancy unit is the **campus** (`campus_id`). `Institution`,
`SchoolGroup` and `Region` are organizational aggregations, **not** tenant
units: they never carry tenant data and are never filtered by campus.

```
Institution (org)
  └── SchoolGroup
        └── Region
              └── Campus   ← the data-isolation unit
                    └── Department
```

`campus_id` remains the isolation boundary for every tenant-owned row.
Hierarchy administrators are authorized over the campuses **inside** their
subtree — the boundary is enforced in SQL as
`campus_id IN (SELECT id FROM campuses WHERE …)`, exactly like the classic
per-campus predicate (see `tenant_filter_for_scope` in
`multi_tenant/registry.py`).

## TenantContext

`TenantContext` (in `models.py`) is resolved per request by the tenant
middleware and carries:

- `campus_id` + `institution_id` — the concrete school scope.
- `school_group_id` / `region_id` — set only for group/region admin scopes.
- `user_id` — the acting user.
- `platform: bool` — explicit cross-tenant authorization (`platform.access`).
- `allow_cross_tenant` — hierarchy-admin or platform fallback flag.

The **scope level** (`TenantScopeLevel`) classifies the caller's granularity
within the hierarchy — the most specific non-empty scope wins:

| Scope level | Meaning |
|---|---|
| `CAMPUS` | The classic tenant: pinned to one campus. |
| `REGION` | Region admin: all campuses under one region. |
| `GROUP` | School-group admin: all campuses under one group. |
| `ORGANIZATION` | Org admin: all campuses under one institution. |
| `PLATFORM` | Explicit `platform.*` grant; may query across all boundaries. |
| `NONE` | No scope — **denied by default** for tenant-owned data. |

Three explicit states exist:

| State | Meaning |
|---|---|
| **Tenant/hierarchy-scoped** (`is_hierarchy_scoped=True`) | Pinned to a campus or a subtree; queries filtered by `campus_id` (directly or via subquery). |
| **Platform** | Explicit `platform.*` grant; may query across campuses. |
| **Unscoped** (neither) | **Denied by default** for tenant-owned data. |

`is_tenant_scoped` is intentionally campus-only for backward compatibility;
use `is_hierarchy_scoped` / `scope_level` for hierarchy admins.

Dependencies: `get_current_tenant` (lenient) and `require_tenant_context`
(raises `403` for unscoped non-platform callers). Platform operations use
`require_platform_permission()` from `auth/dependencies.py`.

## Hierarchy assignments (`organization_assignments`)

Subtree administration is authorized via `OrganizationAssignment` (not
`UserSchoolMembership`), which grants an admin a scope over one node of the
hierarchy:

- `org_admin` → `ORGANIZATION` scope over one `Institution`.
- `group_admin` → `GROUP` scope over one `SchoolGroup`.
- `region_admin` → `REGION` scope over one `Region`.
- `department` → a campus department (limited; campus-scoped).

`resolve_tenant_context` gives assignments precedence over memberships.
Assignments never imply platform access: an org admin is still pinned to
their own institution, and cross-institution access is forbidden.

## Model classification (`multi_tenant/registry.py`)

Every SQLAlchemy model is classified:

- **TENANT_DIRECT** — carries its own `campus_id` (most tenant-owned rows).
- **PARENT_TENANT_PATHS** — inherits tenancy from a parent row (e.g. child
  records resolve their campus through the parent) via
  `assert_tenant_scope_by_parent_id`.
- **PLATFORM** — global/system data (plans, fee types without campus, …);
  never filtered, and only reachable through scoped or platform callers.

`registry.tenant_filter_for(model, campus_id)` returns the predicate applied
to queries for the classic per-campus scope.
`registry.tenant_filter_for_scope(model, tenant)` returns the
subtree predicate for hierarchy admins (region/group/organization), applied
as a `campus_id IN (SELECT …)` subquery so the isolation boundary is
enforced in the SQL.

## TenantScopedRepository (`multi_tenant/repository.py`)

The canonical base for every tenant-owned repository. Key behavior:

- `scoped_query(model)` / `scoped_count(model)` build `SELECT`s with the
  tenant predicate **already applied**, and raise `AuthorizationError` for
  unscoped non-platform callers (default-deny). Hierarchy admins get the
  subtree predicate for their scope level.
- `get_by_id(model, id)` — a row owned by another campus *does not exist* to
  a scoped caller.
- `exists`, `first`, `_list_by_tenant` — all tenant-filtered.
- `_has_platform_access()` — `tenant=None` (legacy internal callers) or
  explicit platform → unfiltered; everything else denied.

## Guards (`multi_tenant/guards.py`)

- `effective_campus_id(tenant, client_campus_id)` — pins lists to the
  caller's campus; a client-supplied `campus_id` is ignored for scoped users
  and only honoured for platform callers.
- `assert_tenant_scope(entity, tenant, resource)` — 403 when the entity's
  campus differs from the tenant's (or is untagged).
- `inject_campus(entity, tenant)` — tags new rows with the caller's campus on
  creation (client-supplied values are overwritten).
- `assert_tenant_scope_or_owner` — lets a record's owner through only for
  legacy untagged rows.
- `assert_tenant_scope_by_parent_id` — for children inheriting tenancy.
- Hierarchy guards: `assert_campus_in_scope`, `assert_school_group_in_scope`,
  `assert_region_in_scope`, `assert_institution_in_scope` — verify a target
  entity lies inside the caller's subtree, and 403 otherwise
  (cross-tenant access is denied even for subtree admins).

## Platform-scoped queries

Explicit platform access is the only opt-in to cross-tenant data. Nothing in
the framework silently grants platform scope: it requires a `platform.*`
permission on the user and, for endpoint-level cross-tenant operation,
`require_platform_permission()`.

## Legacy data

Pre-tenancy rows may carry `campus_id = NULL`. Scoped callers cannot see
them through tenant-filtered queries, and guards treat untagged rows as
invisible to scoped tenants (with the narrow `assert_tenant_scope_or_owner`
exception for a user's own records).

## Verification

`tests/test_multi_tenant/test_security_suite.py` (28 tests) proves, end to
end, that Tenant A cannot read/update/delete/search/export/batch/reach
Tenant B's data through any surface — including 360 views, analytics, jobs,
notifications, documents, and parent/student-portal junctions — and that
platform operations require explicit authorization. (A further 64 tests in
`tests/test_security_acquisition/` cover authentication, authorization,
IDOR, rate limiting, and database invariants.)

`tests/test_enterprise_hierarchy.py` (28 tests) covers the enterprise
hierarchy: subtree isolation for org/group/region admins at the repository,
guard, and HTTP-API levels (list/create scoping, cross-subtree denial,
cross-institution denial), plus tenant-scoped assignment precedence and
migration-schema parity.
