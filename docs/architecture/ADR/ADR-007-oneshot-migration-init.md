# ADR-007 — One-Shot Migration-Init Service

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Schema
migrations run in a dedicated one-shot container before application
services start; the API never runs migrations itself.**

## Context

- Multiple API replicas must not race to run migrations at startup.
- A clean first-run experience (zero-touch) requires automatic migration.

## Decision

1. `migration-init` compose service runs `alembic upgrade head` as a
   one-shot job (`restart: no`), waiting for PostgreSQL health first.
2. `api` and `worker` depend on
   `migration-init: service_completed_successfully` — they never start
   before the schema is at head; a migration failure fails the deployment.
3. Migration is idempotent (`alembic upgrade head` at head is a no-op);
   the one-shot container is concurrency-safe by construction.

## Consequences

- No per-replica migration races; deterministic startup ordering.
- Failed migrations are visible (container exit non-zero, logs).
- Repeated `up` after `down` is safe (verified).

## Evidence

- `infrastructure/docker/docker-compose.yml`, `apps/api/Dockerfile`
  (non-root `--prefix=/opt/sdmas` install resolving the historical
  `/root/.local` permission failure), `docs/architecture/CURRENT_STATE.md` §4,
  `docs/zero-touch-deployment.md`.
