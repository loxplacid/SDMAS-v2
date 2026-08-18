# SDMAS v2 — Architecture Documentation Set

The authoritative architecture documentation for SDMAS v2. Every document in
this set is **based on repository evidence** (code, config, tests, CI,
deployment files) and labelled CURRENT / IN PROGRESS / PLANNED where a
capability is not yet fully shipped. Nothing aspirational is presented as
implemented.

## Documents

| Doc | Content |
|---|---|
| [CURRENT_STATE.md](CURRENT_STATE.md) | Verified baseline: migration graph (single head `059`), schema/model consistency, Docker migration-init, additive-migration policy |
| [DATA_MODEL.md](DATA_MODEL.md) | 136-table schema inventory, ORM↔DB↔migration consistency baseline, representation patterns, adding-a-change policy |
| [DOMAIN_MAP.md](DOMAIN_MAP.md) | 35 backend domains + cross-cutting layers, wiring status per domain |
| [DOMAIN_CONTRACTS.md](DOMAIN_CONTRACTS.md) | Domain dependency direction rules, per-domain public contracts, cycle allowlist, router-logic findings, enforced by `tests/test_domain_boundaries.py` |
| [API_CONTRACTS.md](API_CONTRACTS.md) | Canonical API contract: routing (vite+nginx), auth/session, error envelope, pagination, request/correlation IDs, tenant context, versioning policy — guarded by `api-contract.test.ts` |
| [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md) | Current runtime + request lifecycle + data/security posture; IN PROGRESS cores (temporal, intelligence, simulation, optimization); PLANNED (graph, full bitemporal) |
| [EVENT_MODEL.md](EVENT_MODEL.md) | Domain events, event catalog, transactional outbox, durable jobs, worker, scheduler, workflow, end-to-end trace |
| [SECURITY_MODEL.md](SECURITY_MODEL.md) | Auth (JWT rotation/reuse detection), default-deny gate, RBAC, webhook security, uploads, audit, secrets, transport, evidence |
| [TENANCY_MODEL.md](TENANCY_MODEL.md) | TenantContext, model classification, TenantScopedRepository, guards, platform access, legacy data, demo tenants, verification |
| [INTEGRATION_MAP.md](INTEGRATION_MAP.md) | PostgreSQL, Redis, Razorpay, SendGrid, S3/local storage, Vault, nginx, SQLite-WASM search, observability |
| [DEPLOYMENT_MODEL.md](DEPLOYMENT_MODEL.md) | Zero-touch compose stack, service table, dependency graph, images, enterprise script, Makefile, CI/CD, ops |
| [ADR/](ADR/) | Architecture decision records (9 ACCEPTED), each mapped to repository evidence |

## Relationship to root docs

The root-level files remain canonical and are cross-linked:

- `ARCHITECTURE.md` — canonical CURRENT system description
- `SECURITY.md` / `AUTHORIZATION.md` / `TENANCY.md` — security,
  authorization, and tenancy detail
- `DEPLOYMENT.md` / `docs/zero-touch-deployment.md` — operations
- `KNOWN_LIMITATIONS.md` — honest current gaps
- `docs/enterprise/` — acquisition/verification reports (audits, evidence)

## Status labels

- **CURRENT** — implemented, wired, verified.
- **IN PROGRESS** — core implemented, not fully wired (no router/consumer).
- **PLANNED** — design spec only; no runnable behaviour.

## Updating this set

When code changes, update the matching document in the same change:
domains → `DOMAIN_MAP.md`; wiring/scaffold status → `TARGET_ARCHITECTURE.md`;
schema → `DATA_MODEL.md` + `CURRENT_STATE.md`; API contracts → `API_CONTRACTS.md`; events/jobs → `EVENT_MODEL.md`;
security → `SECURITY_MODEL.md`; tenancy → `TENANCY_MODEL.md`; integrations →
`INTEGRATION_MAP.md`; deployment → `DEPLOYMENT_MODEL.md`; a new significant
decision → a new `ADR/` record and the index.
