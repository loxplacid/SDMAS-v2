# SDMAS v2 — Tenancy

The canonical multi-tenant framework lives in `apps/api/app/multi_tenant/`.
It makes cross-tenant data leakage **structurally difficult or impossible**
by scoping queries at construction time rather than relying on developers
remembering to check every fetched record.

## The chain

```
Authenticated User
  → Tenant Membership        (user_school_memberships)
  → TenantContext            (multi_tenant/models.py)
  → Tenant-Scoped Query      (TenantScopedRepository — multi_tenant/repository.py)
  → Resource-Level Guards    (multi_tenant/guards.py)
```

## TenantContext

`TenantContext` (in `models.py`) is resolved per request by the tenant
middleware and carries:

- `campus_id` + `institution_id` — the concrete school scope.
- `user_id` — the acting user.
- `platform: bool` — explicit cross-tenant authorization (`platform.access`).
- `allow_cross_tenant` — platform fallback flag.

Three explicit states exist:

| State | Meaning |
|---|---|
| **Tenant-scoped** (`is_tenant_scoped=True`) | Pinned to one campus; queries are filtered by `campus_id`. |
| **Platform** | Explicit `platform.*` grant; may query across campuses. |
| **Unscoped** (neither) | **Denied by default** for tenant-owned data. |

Dependencies: `get_current_tenant` (lenient) and `require_tenant_context`
(raises `403` for unscoped non-platform callers). Platform operations use
`require_platform_permission()` from `auth/dependencies.py`.

## Model classification (`multi_tenant/registry.py`)

Every SQLAlchemy model is classified:

- **TENANT_DIRECT** — carries its own `campus_id` (most tenant-owned rows).
- **PARENT_TENANT_PATHS** — inherits tenancy from a parent row (e.g. child
  records resolve their campus through the parent) via
  `assert_tenant_scope_by_parent_id`.
- **PLATFORM** — global/system data (plans, fee types without campus, …);
  never filtered, and only reachable through scoped or platform callers.

`registry.tenant_filter_for(model, campus_id)` returns the predicate applied
to queries.

## TenantScopedRepository (`multi_tenant/repository.py`)

The canonical base for every tenant-owned repository. Key behavior:

- `scoped_query(model)` / `scoped_count(model)` build `SELECT`s with the
  tenant predicate **already applied**, and raise `AuthorizationError` for
  unscoped non-platform callers (default-deny).
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

`tests/test_multi_tenant/test_security_suite.py` (60 tests) proves, end to
end, that Tenant A cannot read/update/delete/search/export/batch/reach
Tenant B's data through any surface — including 360 views, analytics, jobs,
notifications, documents, and parent/student-portal junctions — and that
platform operations require explicit authorization.
