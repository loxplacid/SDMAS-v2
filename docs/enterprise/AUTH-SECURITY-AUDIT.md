# Authentication Security Audit — SDMAS v2

**Status: VERIFIED (P0/P1 findings fixed and regression-tested)**
**Date:** 2026-08-12

Behavioral audit of the authentication stack — login, logout, password
hashing, token/session handling, refresh rotation, expiration, rate
limiting, CSRF posture, secure headers, session invalidation, tenant
selection and the default-deny auth gate.  Every failure path was
exercised through the live ASGI app and must be a deliberate 4xx
(401/422/429) — never a generic 500.

---

## 1. Surface inspected

| Area | Implementation |
|---|---|
| Login | `POST /auth/login` — `apps/api/app/domains/auth/router.py`, `service.login` |
| Registration | `POST /auth/register` (public, rate-limited) |
| Logout | `POST /auth/logout` — **NEW in this audit** |
| Password hashing | bcrypt (`hash_password` / `verify_password`, `security.py`) |
| Access token | HS256 JWT, 30 min, claims `sub/username/jti/exp/type/campus_id` |
| Refresh token | HS256 JWT, 7 days, stored **hashed** (SHA-256) in `refresh_tokens` |
| Refresh rotation | rotation + reuse detection + family revocation (`service.refresh_token`) |
| Password change | `PATCH /auth/me/password` (current password verified) |
| Rate limiting | Redis-backed in prod / in-memory in dev (`rate_limiter.py`); trusted-proxy client IP |
| Session invalidation | refresh-token revocation on logout / deactivation — **hardened in this audit** |
| Tenant selection | `POST /auth/schools/switch` validates membership server-side before issuing campus-scoped tokens |
| Auth middleware | `AuthGateMiddleware` — global default-deny; public allowlist is small and audited |
| CSRF / cookies | No auth cookies; bearer token in `Authorization` header / JSON body → CSRF not applicable |
| Secure headers | nginx `security-headers.conf` (HSTS, X-Frame-Options, etc.) |

---

## 2. Verified controls (behavioural tests)

| Control | Behaviour | Evidence |
|---|---|---|
| Generic login failure | wrong password and nonexistent user return the **same** `401 "Invalid username or password"` — no account enumeration | `test_nonexistent_user_401_same_message` |
| Disabled accounts | cannot login (401); existing access tokens rejected on every request | `test_disabled_user_cannot_login` |
| Malformed tokens | garbage, truncated, wrong-alg (HS512) and hand-forged `alg:none` tokens → **401, never 500** | `TestMalformedTokens` |
| Expired sessions | expired access and expired refresh JWTs → 401 | `TestExpiredTokens` |
| Refresh rotation | presenting a rotated-away token → 401 | `test_refresh_rotates_and_old_token_rejected` |
| Reuse detection | replay of a revoked token revokes the **entire token family** (all sessions die) | `test_refresh_reuse_revokes_entire_family` |
| Concurrent sessions | two logins produce independent, non-interfering refresh tokens | `test_concurrent_sessions_are_independent` |
| Credential separation | refresh token never authenticates APIs; access token never refreshes | `test_refresh_token_cannot_be_used_as_bearer`, `test_access_token_cannot_be_used_as_refresh` |
| Brute-force | 5 failed logins per IP/min → 6th attempt (even correct) → **429 + Retry-After**; refresh throttled at 30/min | `TestBruteForceProtection` |
| Privilege change mid-session | access tokens carry **no role claims** → role/permission changes apply on the next request | `test_access_token_carries_no_role_claim` |
| Deactivation mid-session | existing access token → 401 immediately; **refresh rotation also cut off** (see §3) | `test_deactivation_revokes_session_immediately`, `test_deactivated_user_cannot_refresh` |
| Logout | 204; **all** refresh tokens revoked; subsequent refresh → 401; idempotent; unauthenticated → 401 | `TestLogout` |

---

## 3. Findings

### Fixed (P1)

1. **No server-side logout — sessions survived "sign out".**
   `api.logout()` only cleared browser tokens; no endpoint revoked the
   server-side session, so a stolen refresh token remained valid for up
   to 7 days after the user signed out.  The `LOGOUT` audit constant
   existed but was never emitted.
   **Fix:** `POST /auth/logout` (authenticated, rate-limited 20/min)
   revokes **every** outstanding refresh token via
   `UserService.logout` and records a `LOGOUT` audit event; the web
   client now fires it best-effort (raw fetch — never through the
   refresh/onLogout machinery) before clearing local tokens.

2. **Deactivated users could keep rotating refresh tokens.**
   `UserService.refresh_token` loaded the user but never checked
   `is_active`, so an admin "deactivation" only blocked *login*: the
   user's existing refresh tokens still minted fresh access tokens
   (which then 401 at `get_current_user`, so no data access — but the
   session was never actually terminated, and rotation continued).
   **Fix (two layers):** `refresh_token` now rejects inactive users
   with 401, and `admin_update_user` revokes all refresh tokens the
   moment `is_active` transitions True → False.

### Documented limitations (not defects)

| Severity | Limitation | Rationale |
|---|---|---|
| P2 | **No forgot-password / admin password-reset flow** | Documented gap (`docs/PRODUCT_CAPABILITY_AUDIT.md`); requires email-delivery decisions. Password *change* (authenticated) exists and is covered. |
| P3 | No account **lockout**; brute-force is throttled per IP instead (5/min login) | Distributed-safe alternative; IP throttle is effective behind the trusted-proxy boundary. A lockout is a per-account policy decision, not implemented. |
| P3 | Access tokens are stateless JWTs: after logout they remain valid until their **30-minute expiry** | Standard JWT semantics; logout kills refresh (no new tokens) and the client discards the token. An access-token denylist (Redis) would be a follow-up if revocation-before-expiry is required. |
| P3 | If the access token is **already expired** at sign-out, the best-effort logout fetch 401s and the server does not revoke refresh tokens | Client discards them anyway; short access-token lifetime bounds exposure. |
| — | TOCTOU: a refresh racing a logout can mint one final token | Standard for refresh-token systems; the reuse-detection family revocation bounds it. |

---

## 4. Changes

| File | Change |
|---|---|
| `apps/api/app/domains/auth/router.py` | New `POST /auth/logout` (204, `get_current_user`, rate-limited, audits LOGOUT) |
| `apps/api/app/domains/auth/service.py` | New `UserService.logout` (revoke all refresh tokens + LOGOUT audit); `refresh_token` rejects inactive users; deactivation revokes refresh tokens |
| `apps/web/src/api/client/http-client.ts` | `api.logout()` fires best-effort `POST /auth/logout` before clearing local tokens |
| `apps/api/tests/test_auth/test_security_audit.py` | **New — 27 behavioural regression tests** |
| `apps/web/src/__tests__/auth-client.test.ts` | Updated logout test to pin the server-side-revocation call |

## 5. Tests executed

- `tests/test_auth/test_security_audit.py` — **27 passed**: invalid /
  nonexistent / disabled credentials; malformed, truncated, wrong-alg,
  `alg:none`, expired tokens (all 401, none 500); refresh rotation,
  reuse → family revocation, concurrent-session independence,
  refresh-as-bearer; logout revocation + idempotency + auth requirement +
  stateless-access-token semantics; no-role-claim in JWT; deactivation
  cutting both access and refresh; brute-force 429 with `Retry-After`;
  refresh throttling.
- Combined backend regression (`test_auth`, `test_rbac_router_enforcement`,
  `test_multi_tenant`, `test_tenant_isolation`, `test_permissions`,
  `test_communications_context`) — **260 passed, 0 failed**.
- Frontend: `auth-client.test.ts` + `login-flow.test.ts` — **21 passed**;
  `tsc --noEmit` clean.
- Ruff (`E9,F821,F822,F811,I001`) on all changed files: **clean**.

## 6. Verify

```bash
cd apps/api
uv run pytest tests/test_auth/test_security_audit.py -q
cd ../web
npx vitest run src/__tests__/auth-client.test.ts src/__tests__/login-flow.test.ts
```
