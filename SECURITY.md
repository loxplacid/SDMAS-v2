# SDMAS v2 — Security

This document describes the security controls **as implemented** in the
canonical system (`apps/`). It is not a wishlist.

## Authentication

- **JWT bearer tokens** issued by `app/domains/auth` on `POST /auth/login`.
  - Access token: HS256, **30-minute** default expiry
    (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  - Refresh token: 7-day expiry with rotation/reuse detection. A refresh
    token is single-use: rotation revokes the consumed token, and **replay
    of a consumed token revokes the whole family** (the revocation is
    committed before the 401 is returned, so the containment is durable).
- **Password hashing** via `app/domains/auth/security.py`
  (`hash_password` / `verify_password`) — plaintext is never stored.
- **Default-deny auth gate** (`app/core/security/auth_gate.py`): every
  request must present a valid bearer token unless the path is on an explicit
  public allowlist. The allowlist is minimal and intentional:
  - `POST /auth/login`, `POST /auth/refresh`, `POST /auth/register`
  - `GET /health`, `GET /ready`, `GET /metrics`
  - `GET /docs`, `GET /redoc`, `GET /openapi.json` (dev/staging only)
  - `GET /billing/plans` — public plan catalog
  - `POST /billing/webhook/{provider}` — authenticated by **provider
    signature**, not by user session.
- **Login rate limiting** (per-IP) on the login endpoint.

## Authorization

- **RBAC**: users carry roles; roles map to `<resource>.<action>`
  permissions (`app/domains/auth/permissions.py`). Enforcement via
  `require_permission(...)`, `require_role(...)`, and
  `require_platform_permission(...)` dependencies.
- **Platform permissions** (`platform.access`, `platform.manage`) are the
  *only* way to operate across tenant boundaries. A tenant `admin` never
  satisfies a platform check. See [`AUTHORIZATION.md`](AUTHORIZATION.md).

## Tenant isolation

Isolation is **structural**, not by developer discipline:

1. `TenantContext` (campus-scoped / platform / unscoped) is resolved per
   request from token + `user_school_memberships`.
2. `TenantScopedRepository` applies the tenant predicate at **query
   construction time** — a scoped caller cannot read another campus's rows
   even by guessing an ID (IDOR closed in the repository layer).
3. Router guards (`assert_tenant_scope`, `effective_campus_id`,
   `inject_campus`) pin lists, verify get/update/delete targets, and tag new
   rows with the caller's campus.
4. Unscoped non-platform callers are **denied by default**; platform-scoped
   access requires an explicit `platform.*` permission.

See [`TENANCY.md`](TENANCY.md) for the full mechanism. A dedicated
multi-tenant security test suite (28 tests in
`tests/test_multi_tenant/test_security_suite.py`) continuously proves Tenant
A cannot read/update/delete/search/export/reach Tenant B's data.

**Admin user management** (`/admin/users`) is tenant-scoped: a tenant admin
can only list/get/update/assign-roles for users of their own campus, and
new users are pinned to the acting admin's campus.

An **acquisition-grade security & invariants suite** (64 tests in
`apps/api/tests/test_security_acquisition/`) proves the boundaries end-to-end
for every requested category — authentication (expired/invalid/revoked
tokens, refresh rotation/reuse, invalid refresh), authorization (missing
permission, incorrect role, horizontal/vertical privilege escalation, role
from wrong tenant), platform access (default-deny unscoped, explicit
platform grant), tenant isolation + IDOR (jobs, notifications, audit,
documents, shares, guardian junctions), documents (oversized uploads,
disallowed MIME/extension, path traversal), rate limiting (per-IP login
429s, per-process assumption), database invariants (unique races, transaction
rollback, FK integrity with `PRAGMA foreign_keys=ON`), and audit invariants
(explicit actors, tenant context, FAILURE/SUCCESS outcomes).

## Payment webhooks (`POST /billing/webhook/{provider}`)

- **Signature verification**: HMAC-SHA256 over the **raw request body** with
  the provider webhook secret, compared with `hmac.compare_digest`
  (constant-time). Invalid signatures are rejected before any processing.
- **Replay protection**: timestamp-freshness enforced when the provider signs
  one (events older than 300 s are dropped); every verified event is also
  recorded in the `webhook_events` idempotency ledger keyed by
  `(provider_name, sha256(raw_body))` with a UNIQUE constraint — duplicates
  and replayed deliveries are skipped, so a retry can never double-process a
  payment.
- **Tenant association** is resolved **from the provider payload** (notes set
  server-side at payment-link creation), never from client headers.
- **Monetary integrity**: a `payment.captured` event only settles an invoice
  when the captured amount covers that invoice; a missing/unparseable amount
  **fails closed**. Client-supplied payment status is never authoritative.
- **Safe retry**: event + side effects commit atomically; an exception
  bubbles as a 5xx so the provider retries; a re-delivery is deduped.

## Uploads

- File uploads are validated for **size**, **extension allowlist**, and
  **content-based MIME type** (`python-magic`). Rejected uploads return a
  clean `400` (a `FileValidationError` handler); executables, scripts,
  oversized files, and traversal-style filenames never reach storage.
  Storage keys are server-generated UUIDs — user filenames are never used
  in paths.

## Audit trail

- Append-only `audit_logs` written by middleware and by domain services
  (payments, refunds, reconciliations, logins, webhook deliveries).
- Actors are explicit: `user`, `system`, `worker`, `webhook`, `platform` —
  never an unattributed `0`.
- Audit writes are best-effort (non-fatal on failure) so they never break the
  primary operation.

## Secrets

- Runtime configuration via environment variables / `.env`
  (pydantic-settings). Template: `.env.example`.
- Production secrets are expected in `infrastructure/secrets/` (files
  `chmod 600`) or injected by the platform; `app/core/secrets.py` provides a
  Vault backend.
- **Known gap (resolved)**: the root `.env` file was previously tracked in
  git; it is now untracked (`git rm --cached`) and `.gitignore`d (see
  [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) and `docs/SECRETS.md`).
  Rotation of any secrets that ever lived in it is recommended.

## Transport & hardening

- CORS restricted to configured origins (`CORS_ORIGINS`).
- Security headers middleware (HSTS, X-Content-Type-Options, etc.).
- Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are **disabled in
  production** (`ENVIRONMENT=production`).
- Nginx handles TLS termination and rate limiting in the deployment topology.

## Reporting

Report vulnerabilities privately to the maintainers (see
[`docs/security-policy-and-controls.md`](docs/security-policy-and-controls.md)
and the accepted-risk register in
[`docs/security-policy.md`](docs/security-policy.md)).
