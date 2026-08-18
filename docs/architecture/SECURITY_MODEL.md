# SECURITY MODEL — SDMAS v2

Date: 2026-08-17 · Consolidated from `SECURITY.md` (root), `AUTHORIZATION.md`,
`TENANCY.md`, and verified code in `apps/api/app/core/security/`,
`apps/api/app/domains/auth/`, `apps/api/app/domains/audit/`,
`apps/api/app/domains/billing/`, `apps/api/app/domains/documents/`.

The root-level `SECURITY.md` remains the canonical security document; this
file is the architecture-set view with the same evidence.

---

## 1. Authentication

| Concern | Implementation (evidence) |
|---|---|
| Login | `POST /auth/login` (rate-limited per IP); credentials verified against hashed passwords |
| Access token | JWT HS256, 30-minute default expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| Refresh token | 7-day expiry, **single-use with rotation**; replay of a consumed token revokes the whole family — revocation is committed before the 401 is returned (durable containment) |
| Password storage | `auth/security.py` — `hash_password` / `verify_password`; plaintext never stored |
| Registration | `POST /auth/register` (public allowlist); admin user management is tenant-scoped |
| Logout | `POST /auth/logout` (rate-limited) — revokes all refresh tokens, records a `LOGOUT` audit event |
| Session changes | Refresh rotation/reuse detection makes a stolen refresh token self-destruct the family |

## 2. Default-deny auth gate (`core/security/auth_gate.py`)

Every request must present a valid bearer token **unless** the path is on the
explicit public allowlist:

- `POST /auth/login`, `POST /auth/refresh`, `POST /auth/register`
- `GET /health`, `GET /ready`, `GET /metrics`
- `GET /docs`, `GET /redoc`, `GET /openapi.json` (dev/staging only —
  **disabled in production** via `ENVIRONMENT=production`)
- `GET /billing/plans` (public plan catalog)
- `POST /billing/webhook/{provider}` (authenticated by **provider
  signature**, not user session)

Everything else fails closed with **401**.

## 3. Authorization (RBAC)

- Permissions are strings `<resource>.<action>` (`students.view`,
  `fees.record_payment`, `reports.export`, …) defined in
  `auth/permissions.py` and registered in `ALL_PERMISSIONS`.
- Three enforcement dependencies (`auth/dependencies.py`):
  - `require_permission("x.y")` — DB role→permission mapping with registry
    fallback (most tenant endpoints),
  - `require_role("admin", "staff")` — named-role gates,
  - `require_platform_permission("platform.manage")` — explicit
    cross-tenant grant (default `platform.access`).
- Roles: `platform_admin` (cross-tenant), `admin` (full own-campus, never
  platform), `principal`, `accountant`, `staff`, `teacher`, `student`,
  `parent`. Unknown roles get `[]` permissions — **locked down by default**.
- Frontend hiding is never authorization: every privileged operation is
  enforced server-side (verified by `docs/enterprise/RBAC-AUTHORIZATION-AUDIT.md`
  and `test_rbac_router_enforcement.py`).

## 4. Tenant isolation (summary — full detail in TENANCY_MODEL.md)

Structural, at query-construction time:

1. `TenantContext` (campus-scoped / platform / unscoped) resolved per
   request from token + `user_school_memberships`.
2. `TenantScopedRepository` applies the tenant predicate to every query —
   another campus's row **does not exist** to a scoped caller (IDOR closed
   at the repository layer).
3. Router guards (`assert_tenant_scope`, `effective_campus_id`,
   `inject_campus`) pin lists, verify targets, tag new rows.
4. Unscoped non-platform callers denied by default; platform requires an
   explicit `platform.*` permission.

Proven by 28-test multi-tenant security suite + 64-test
`test_security_acquisition` suite + adversarial three-tenant suite.

## 5. Payment webhooks (`POST /billing/webhook/{provider}`)

- **Signature verification**: HMAC-SHA256 over the raw request body with the
  provider webhook secret, compared constant-time (`hmac.compare_digest`).
  Invalid signatures rejected before any processing.
- **Replay protection**: timestamp freshness (events older than 300 s
  dropped); every verified event recorded in the `webhook_events`
  idempotency ledger keyed by `(provider_name, sha256(raw_body))` with a
  UNIQUE constraint — duplicates/replays skipped; a retry can never
  double-process a payment.
- **Tenant association** resolved from the provider payload (server-set
  notes), never client headers.
- **Monetary integrity**: `payment.captured` settles an invoice only when
  the captured amount covers it; missing/unparseable amount **fails
  closed**; client-supplied status is never authoritative.
- **Safe retry**: event + side effects commit atomically; a failure returns
  5xx so the provider retries; re-delivery deduped.

## 6. Uploads (documents / migration files)

- Validated for **size** (`MAX_FILE_SIZE_MB`), **extension allowlist**, and
  **content-based MIME** (`python-magic`).
- Rejected uploads return a clean **400** (`FileValidationError` handler) —
  executables, scripts, oversized files, traversal-style filenames never
  reach storage.
- Storage keys are server-generated UUIDs; user filenames never used in
  paths.

## 7. Audit trail (`audit/`)

- Append-only `audit_logs` written by middleware (mutating requests) and by
  domain services (payments, refunds, reconciliations, logins, logout,
  webhook deliveries, jobs).
- Actors are explicit: `user`, `system`, `worker`, `webhook`, `platform` —
  never an unattributed `0` (prior `verified_by=0` defect fixed and
  regression-tested).
- Audit writes are best-effort/non-fatal so they never break the primary
  operation.
- Export endpoint (`/audit/export`) is separate from the `{entry_id}`
  catch-all to avoid route shadowing.

## 8. Secrets & configuration

- Pydantic-settings via env + `.env`; template `.env.example`.
- **Production boot refuses placeholder secrets** — `JWT_SECRET` /
  `DOCUMENT_STORAGE_SECRET` still at defaults ⇒ startup fails fast.
- Backends: env or **Vault** (`app/core/secrets.py`); production expects
  `infrastructure/secrets/` (files `chmod 600`) or platform injection.
- `.env` files are git-ignored and guarded in CI (tracked-`.env` check).

## 9. Transport & hardening

- CORS restricted to `CORS_ORIGINS`.
- Security headers middleware (HSTS, X-Content-Type-Options, etc.).
- Interactive docs disabled in production.
- Nginx: TLS termination, security headers, rate limits (production config);
  dev config content-negotiates SPA/API prefixes.
- Trusted-proxy allowlist (`TRUSTED_PROXIES`) so only real proxies can set
  `X-Forwarded-*` (prevents IP spoofing against rate limits and audit);
  `RATE_LIMIT_FAIL_CLOSED` option for Redis-outage policy.

## 10. Verification evidence

- `docs/enterprise/MULTI-TENANT-SECURITY-AUDIT.md` — cross-tenant IDOR,
  horizontal/vertical escalation, negative tests pass.
- `docs/enterprise/RBAC-AUTHORIZATION-AUDIT.md` — permission matrix,
  escalation attempts.
- `docs/enterprise/AUTH-SECURITY-AUDIT.md` — token/session lifecycle,
  brute-force, deliberate 4xx.
- `docs/enterprise/SUPPLY-CHAIN-SECURITY-AUDIT.md` — bandit/pip-audit/npm
  audit/gitleaks/SBOM results.
- `docs/enterprise/API-PRODUCTION-READINESS-AUDIT.md` —
  unauthenticated/malicious-request tests.
- Security-policy and accepted-risk registers: `docs/security-policy.md`,
  `docs/security-policy-and-controls.md`.

## 11. Known limitations (from KNOWN_LIMITATIONS.md / audits)

- Historical `.env` was once tracked; untracked now, rotation of any
  previously-exposed secrets recommended.
- `alembic check` representation noise (no functional impact; see
  CURRENT_STATE.md §3).
- No CSRF needed for bearer-token SPA usage; cookies are not used for
  session auth.
