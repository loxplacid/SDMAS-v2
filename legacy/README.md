# legacy/ — Deprecated SDMAS v1 (Archived)

> **Status: ARCHIVED.** The SDMAS v1 JavaScript implementation and the root
> Python v1 foundation have been moved to [`_archive/legacy-v1/`](../_archive/legacy-v1/).
> See [`_archive/legacy-v1/DEPRECATED.md`](../_archive/legacy-v1/DEPRECATED.md) for
> the deprecation manifest and the mapping to their canonical replacements.

## Why this directory exists

The `legacy/` directory was reserved for the JavaScript v1 reference once
Python behavioral parity was verified. That parity is now complete:

- The canonical backend is `apps/api` (Python FastAPI + SQLAlchemy + Alembic),
  with **1,100+ passing tests** covering every domain the JS v1 implemented
  (student, academic, attendance, fees) plus authentication, authorization,
  multi-tenancy, billing, jobs, events, and audit.
- The v1 JavaScript stack and root Python foundation had **zero runtime
  references** from `apps/`, `infrastructure/`, the Makefile, Dockerfiles, or
  deployment scripts, so they were archived wholesale.

The `legacy/` directory itself is kept empty as a marker of the completed
migration; the actual code lives under `_archive/legacy-v1/`.

## Migration history

See [`docs/migration.md`](../docs/migration.md) — the migration plan is now
marked **complete**.
