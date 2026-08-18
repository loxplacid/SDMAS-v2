# ADR-001 — Single Alembic Head with Additive Migrations

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Never edit
historical migrations; append additive revisions linearly.**

## Context

- 67 migration files in `apps/api/alembic/versions/`; historical branches
  were converged by merge-only revisions (`merge_multi_tenant_heads`,
  `042_merge_migration_heads`); graph is linear from the head.
- Canonical head: `060_add_migration_factory_tables` (exactly one head;
  `alembic heads` returns one line; CI enforces this).
- All 66 `down_revision` references resolve to real files; no missing
  revisions, no duplicate revision IDs.

## Decision

1. All schema changes are **additive** revisions appended after
   `060_add_migration_factory_tables`.
2. Historical revisions are never modified in place (production data
   compatibility).
3. CI gates: exactly one head + `alembic upgrade head` against PostgreSQL 16.

## Consequences

- Migration history is deterministic and replayable from an empty database
  (verified: full chain applies; re-run is a no-op).
- A historical defect that must be fixed is fixed with a **corrective
  migration**, not by rewriting history (e.g. 044–051 closed earlier drift;
  see `docs/enterprise/DATABASE-TRUTH-AUDIT.md`).
- Downgrade is best-effort (verified for recent revisions only).

## Evidence

- `apps/api/alembic/versions/`, `docs/architecture/CURRENT_STATE.md`,
  `.github/workflows/ci.yml` (migrations job).
