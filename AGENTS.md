# SDMAS v2 — Agent Engineering Rules

This file is the binding instruction set for any AI agent operating on this
repository. Treat every rule below as non-negotiable unless a higher-priority
rule (correctness, security, tenant isolation) forces a documented exception.

## 1. Repository-first

Before changing any code:
- Read the relevant source files, tests, and configuration.
- Trace the existing architecture and data flow.
- Search for existing functionality before creating new.
- Reuse existing abstractions (repositories, services, guards, models).
- Never create a parallel implementation of something that already exists.

## 2. Do not destroy

- Never delete working functionality.
- Never replace the existing architecture merely because another architecture
  is fashionable.
- Never weaken RBAC, tenant isolation, audit, or financial security.
- Never bypass tenant-scoped repositories to make a feature easier.
- Maintain backward compatibility unless there is a concrete, documented
  reason not to.

## 3. Verify, then trust

- Do not assume a feature exists because a comment, test, or AI output claims
  it does. Verify the actual implementation.
- Do not fabricate files, modules, APIs, database tables, configuration,
  tests, or functionality.
- Do not claim a test passed unless it actually passed.
- Do not claim something is fixed, implemented, or production-ready until you
  have verified it.

## 4. Engineering priorities

In order:
1. Correctness
2. Reliability
3. Security
4. Maintainability
5. Backward compatibility
6. Testability
7. Performance
8. UX / polish

## 5. Change discipline

For every task: PLAN → INSPECT → IMPLEMENT → TEST → REVIEW.

- State what you found and what you intend to change before coding.
- Implement the smallest complete solution that satisfies the requirement.
- Keep changes focused on the task — do not make unrelated improvements.
- After changing, run the relevant tests, static checks, and lints.
- Inspect failures rather than blindly modifying code until tests pass.

## 6. Tenant isolation (see TENANCY.md)

- Every query must be scoped to the caller's campus_id.
- Use tenant-scoped repositories; never bypass tenant guards.
- Never trust a frontend tenant ID as a security boundary — the backend is
  authoritative.
- Cross-tenant access is forbidden even for admin users.

## 7. Authorization (see AUTHORIZATION.md)

- Check authorization server-side for every operation.
- Never rely solely on UI hiding for security.
- Respect the existing RBAC role model.

## 8. Audit (see SECURITY.md)

- Every mutating operation on a production-important entity must produce an
  immutable audit event.
- Use the existing `AuditService` — do not create a second audit system.

## 9. Data and migrations

- Use Alembic for schema changes. Ensure migrations are reversible where
  the existing migration architecture supports it.
- Validate that Alembic heads remain a single head (no divergence).
- Use PostgreSQL for production behavior; SQLite may remain for unit tests
  where the repository already intentionally uses it.

## 10. Async operations

- Use the existing durable jobs/outbox infrastructure instead of inventing
  another queue.
- Never block the HTTP request for a long-running background operation.

## 11. Testing

- All new functionality must have automated tests.
- Prefer deterministic behavior over random behavior in tests.
- Test: loading, empty, error, permission-denied, and success states.
- Test: lifecycle transitions, invalid transitions, and authorization.
- Add tests for important behavior even if the task does not explicitly
  request them.

## 12. Documentation

- Update documentation whenever behavior or operational procedures change.
- Keep KNOWN_LIMITATIONS.md honest and current.
- Make every externally visible operation observable and auditable.

## 13. Safety-critical domains

- Treat financial operations, tenant boundaries, and authentication as
  high-risk areas. Extra verification is required before modifying them.
- Never use fake success states, mock financial data as real, or hardcode
  production secrets.
- Demo credentials must be explicitly marked as development/demo-only.

## 14. Repository structure

Canonical docs:
- ARCHITECTURE.md — system design
- SECURITY.md — auth, tenant isolation, audit, secrets
- AUTHORIZATION.md — roles, permissions
- TENANCY.md — multi-tenant context
- DEPLOYMENT.md — operational procedures
- KNOWN_LIMITATIONS.md — current gaps and risks

Canonical code paths:
- `apps/api/` — backend (Python FastAPI, SQLAlchemy 2 async, Alembic)
- `apps/web/` — frontend (React + Vite + TypeScript, PWA)
- `apps/mobile/` — mobile (Expo / React Native)
- `infrastructure/` — Docker Compose, Nginx, monitoring
- `docs/` — all documentation
- `.github/` — CI/CD workflows