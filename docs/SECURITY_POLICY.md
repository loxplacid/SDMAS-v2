# Security Policy & Implemented Controls

## Overview

This document describes both the security **policy** (requirements that must
be followed) and the security **controls actually implemented** in SDMAS v2 as
of the current codebase. Where a control is implemented, this is stated
explicitly. `SECURITY.md` at the repository root is the canonical
implementation-focused summary; this file is the policy document.

## Authentication

- **Policy**: strong authentication, secure session/password handling.
- **Implemented**:
  - JWT access tokens (short-lived, configurable via `ACCESS_TOKEN_EXPIRE_*`)
    plus refresh tokens; secrets via Pydantic Settings (env), never hardcoded.
  - Passwords hashed with a strong algorithm (bcrypt/argon-style) — see
    `app/domains/auth/service.py`.
  - Login rate limiting (`auth/router.py` limiter) and account audit logging.

## Authorization

- **Policy**: enforce role-based access control (RBAC); least privilege.
- **Implemented**:
  - Permission-based RBAC (`app/domains/auth/permissions.py`) with granular
    permissions (`ACADEMIC_*`, `FEES_*`, `STUDENT_*`, `BILLING_*`, …) and
    platform-level permissions (`PLATFORM_MANAGE`, `PLATFORM_ADMIN`, …) that
    tenant admins cannot hold.
  - `require_permission(...)` dependency; platform-scoped operations require
    explicit platform authorization.
  - See `AUTHORIZATION.md` for the full model.

## Data isolation (multi-tenancy)

- **Policy**: tenant data must never leak across tenants.
- **Implemented**:
  - Structural multi-tenancy: every tenant-owned query runs through
    `TenantScopedRepository` (`app/multi_tenant/repository.py`), which appends
    tenant/campus predicates at query construction time.
  - `require_tenant_context` + `assert_tenant_scope` / `effective_campus_id`
    guards on routers; tenant identity comes from the authenticated user's
    membership, never from client-supplied headers.
  - Platform-scoped queries require explicit authorization.
  - See `TENANCY.md` and `apps/api/tests/test_multi_tenant/` (security suite).

## Input validation & injection

- **Policy**: strict validation; parameterized queries; no dangerous eval.
- **Implemented**: Pydantic v2 schema validation on every request body/query;
  SQLAlchemy parameterized queries throughout (no string-built SQL in
  application code).

## Money & financial integrity

- **Policy**: monetary precision; immutable financial history.
- **Implemented**:
  - Integer paise for all monetary columns (`Integer`, never `Float`); DB
    `check` constraints (`amount > 0`, `refunded_amount ≤ amount`, …).
  - Idempotency keys (`payments`, `transaction_logs`) and webhook event
    dedup, all UNIQUE-constrained; HMAC-SHA256 webhook signature verification
    over the raw body with `compare_digest`.
  - Payments/refunds journaled to immutable `transaction_logs`; audit entries
    on financial actions.
  - See `KNOWN_LIMITATIONS.md` for remaining risks.

## Infrastructure

- **Policy**: least-privilege DB users, TLS everywhere, network segmentation.
- **Implemented**: Docker Compose with separate API/worker containers, Nginx
  reverse proxy (TLS terminated at the proxy), secrets via env/`infrastructure/
  secrets/`, Prometheus/Grafana/OTel monitoring in `infrastructure/monitoring/`.

## Incident response & compliance

- **Policy**: defined reporting channels, documented events, audit trails,
  retention; GDPR/HIPAA-appropriate controls where applicable.
- **Implemented**: audit trail system (`app/domains/audit/`) records security
  events (login, registration, financial actions, permission changes).

## Third-party security

- **Policy**: assess vendor posture; secure API integrations; HTTPS.
- **Implemented**: Razorpay integration with webhook signature verification
  (`app/domains/billing/razorpay.py`), provider keys from env, tenant
  attribution via server-side notes (never client headers).

## Developer education

- **Policy**: regular secure-coding training; keep docs current.
- **Implemented**: `docs/CODING_STANDARDS.md`, `CONTRIBUTING.md`, security and
  tenancy docs kept in sync with the codebase.
