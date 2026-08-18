# ADR-008 — PostgreSQL for Production; SQLite Only for Unit Tests

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **PostgreSQL 16
is the production datastore; SQLite is used only for fast unit tests, never
for migrations or production.**

## Context

- Migration chain uses PostgreSQL-specific constructs (batch DDL, views,
  transactional DDL). The chain **does not run on SQLite** — `alembic
  upgrade head` fails in `050_add_missing_tenant_fks` because SQLite
  revalidates the `legacy_null_campus_records` view on table rename.
- Unit tests want fast in-memory databases without Docker.

## Decision

1. Production, staging, compose, and CI migration validation use
   **PostgreSQL 16** (asyncpg).
2. Unit/security/async test suites use SQLite in-memory with
   `Base.metadata.create_all` (never Alembic) — documented, intentional.
3. Integration tests (Testcontainers) run against real PostgreSQL and are
   gated behind `@pytest.mark.integration`.

## Consequences

- The migration baseline is verified on the real database (single head,
  66 revisions, idempotent upgrade — see CURRENT_STATE.md).
- SQLite unit-test databases use `Base.metadata.create_all` (never Alembic).
  Since the 050 view-revalidation repair (2026-08-17), the full Alembic chain
  also applies from an empty SQLite database, but that path is not part of the
  test-suite contract.
- SQLite-only behaviours (FK pragma, view revalidation) are test-suite
  concerns, not production ones.
- CI runs migrations against a PostgreSQL 16 service container.

## Evidence

- `docs/architecture/CURRENT_STATE.md` §5 (documented limitation),
  `.github/workflows/ci.yml` (migrations job),
  `apps/api/tests/conftest.py`, `app/config.py`
  (`database_url` default `sqlite+aiosqlite` for local dev).
