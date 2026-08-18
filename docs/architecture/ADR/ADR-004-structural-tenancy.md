# ADR-004 — Structural Multi-Tenancy at Query Construction

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Tenant
isolation is enforced by the framework at query-construction time, not by
developer discipline.**

## Context

- Multi-tenant school platform; cross-tenant leakage is a critical risk.
- Relying on every developer remembering to add `campus_id` filters is
  unsafe.

## Decision

1. `TenantContext` (campus-scoped / platform / unscoped) resolved per
   request from token + `user_school_memberships`.
2. `TenantScopedRepository` builds every query with the tenant predicate
   already applied; a row of another campus **does not exist** to a scoped
   caller (IDOR closed at the repository layer).
3. Router guards (`assert_tenant_scope`, `effective_campus_id`,
   `inject_campus`, `assert_tenant_scope_by_parent_id`) pin lists, verify
   targets, tag new rows.
4. Unscoped non-platform callers are denied by default; platform access
   requires an explicit `platform.*` permission.
5. Child tables inherit tenancy through parents (no duplicated
   `campus_id`), queried only via parent-scoped paths.

### Enterprise hierarchy extension (2026-08-18)

The tenancy unit remains the **campus**. `Institution` → `SchoolGroup` →
`Region` → `Campus` are organizational nodes; only `Campus` carries tenant
data. Subtree administrators (`org_admin`, `group_admin`, `region_admin`)
are authorized over the campuses **inside** their node via
`organization_assignments` (which take precedence over memberships):

- `TenantScopeLevel` classifies the caller: `CAMPUS` / `REGION` / `GROUP` /
  `ORGANIZATION` / `PLATFORM` / `NONE`.
- `tenant_filter_for_scope` scopes queries as
  `campus_id IN (SELECT id FROM campuses WHERE …)` — the isolation boundary
  is enforced in the SQL, exactly like the per-campus predicate.
- Hierarchy guards (`assert_campus_in_scope`,
  `assert_school_group_in_scope`, `assert_region_in_scope`,
  `assert_institution_in_scope`) 403 on any target outside the subtree.
- Assignments never imply platform access: an org admin stays inside their
  own institution.

## Consequences

- Cross-tenant access is structurally difficult or impossible; verified by
  28-test security suite + 64-test acquisition suite + adversarial
  three-tenant suite + 28-test enterprise-hierarchy suite (all pass).
- Hierarchy administrators get cross-campus subtree access without any
  erosion of the per-campus boundary (enforced as SQL subqueries).
- Platform operations are explicit, narrow, and permission-gated.

## Evidence

- `apps/api/app/multi_tenant/` (models, registry, repository, guards,
  middleware, dependencies), `apps/api/app/domains/institution/` (enterprise
  hierarchy CRUD), `tests/test_multi_tenant/`,
  `tests/test_enterprise_hierarchy.py`,
  `docs/enterprise/MULTI-TENANT-SECURITY-AUDIT.md`,
  `docs/architecture/TENANCY_MODEL.md`.
