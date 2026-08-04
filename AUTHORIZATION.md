# SDMAS v2 — Authorization

How permissions actually work in the canonical system
(`apps/api/app/domains/auth/permissions.py` + `dependencies.py`).

## Model

Permissions are **strings** in the convention `<resource>.<action>`
(e.g. `fees.record_payment`, `students.view`, `reports.export`). They are
defined as constants in `app/domains/auth/permissions.py` and registered in
`ALL_PERMISSIONS`.

Enforcement happens through three FastAPI dependencies
(`app/domains/auth/dependencies.py`):

| Dependency | Checks | Used for |
|---|---|---|
| `require_permission("fees.create")` | The user's roles grant the permission (DB role→permission mapping, registry fallback) | Most tenant endpoints |
| `require_role("admin", "staff")` | The user holds one of the named roles (primary `role` + assigned roles) | Role-level gates |
| `require_platform_permission("platform.manage")` | An explicit platform permission (default `platform.access`) | Cross-tenant / platform operations |

Permission lookups go through `PermissionService.any_role_has_permission`
(DB-backed, falling back to the static `ROLE_PERMISSIONS` registry).

## Roles

| Role | Scope | Permissions |
|---|---|---|
| `platform_admin` | Cross-tenant (explicit) | `platform.access` + `platform.manage` + every tenant permission |
| `admin` | Own campus | Every tenant permission — but **never** platform permissions |
| `principal` | Own campus | Students, fees view, reports, analytics, workflow, audit view, … |
| `accountant` | Own campus | Fees full lifecycle (`fees.record_payment`, `fees.refund`, exports), reports |
| `staff` | Own campus | Students, academic, attendance, notifications, leave |
| `teacher` | Own campus | Students view, attendance record/update, notifications, leave |
| `student` | Own campus | Attendance view, fees view, notifications, leave view |
| `parent` | Own campus | Students view, attendance view, fees view, notifications |

`get_permissions_for_role(role)` returns `[]` for unknown roles — **new roles
are locked down by default**.

## Platform access

`platform.access` and `platform.manage` are the **only** permissions that
authorise cross-tenant operation:

- A tenant `admin` has full control *inside its own campus* but never
  satisfies a platform check.
- `resolve_tenant_context` (multi_tenant) only marks a request as platform
  when the user holds an explicit platform permission.
- Platform-only surfaces (e.g. billing plan pricing/entitlements) are gated
  with `require_permission(PLATFORM_MANAGE)` — a tenant can never set its own
  prices.

## Enforcement points

- Routers declare permission dependencies per endpoint (e.g.
  `require_permission(FEES_REFUND)` on refunds).
- Tenant scoping (who *may* see a row) is enforced separately and
  structurally — see [`TENANCY.md`](TENANCY.md). Authorization answers "may
  this role do this action?"; tenancy answers "may this actor touch this
  row?".

## Tests

- `tests/test_permissions.py` — role↔permission matrix, including the
  guarantee that tenant `admin` has no platform permissions.
- `tests/test_multi_tenant/test_security_suite.py` — end-to-end default-deny
  and platform-access scenarios.
