# ADR-002 — Dedicated Background Worker Process

Status: ACCEPTED · Date: 2026-08-16 (verified) · Decision: **Background work
runs in a dedicated worker process; the API never consumes the queues in
production.**

## Context

- Jobs (`jobs` table) and events (transactional outbox) need a consumer.
- If every API replica started an in-process worker, replicas would compete
  for the same queues (`acquire_next` claims are row-level, so no
  double-execution — but unbounded competing pollers are wasteful and
  confusing).

## Decision

1. Production runs a dedicated worker (`apps/api/Dockerfile.worker`,
   `python -m app.domains.jobs.worker`) as the **sole** consumer of the
   jobs table and event outbox.
2. The API starts in-process workers **only** when
   `WORKER_IN_PROCESS=true` (single-process dev/tests).
3. The worker is a background process with **no HTTP port**; health is
   `HEALTHCHECK NONE` + `restart: unless-stopped` — a truthful mechanism,
   never a fake probe of the API port.

## Consequences

- Scaling API replicas never launches competing workers.
- The worker is observable via the jobs API (status/progress/result/audit).
- Container restart policy is the process-level health mechanism.

## Evidence

- `apps/api/Dockerfile.worker`, `apps/api/app/domains/jobs/worker.py`,
  `apps/api/app/main.py` (`_start_in_process_workers` gated on
  `settings.worker_in_process`), `app/config.py`
  (`worker_in_process` default False), `infrastructure/docker/docker-compose.yml`.
