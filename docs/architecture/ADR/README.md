# Architecture Decision Records — SDMAS v2

This directory records significant architectural decisions **as evidenced in
the repository**. Every ADR states the decision, the concrete code/config
that implements it, and the consequences. ADRs are never aspirational: if
the implementation does not match, the ADR is updated.

## Conventions

- **Status**: `ACCEPTED` (implemented and verified), `PROPOSED` (design
  spec only), `SUPERSEDED`.
- New ADRs: `ADR-###-short-name.md`, appended chronologically.
- Update an ADR when the implementation changes its outcome.

## Index

| # | Title | Status |
|---|---|---|
| 001 | Single Alembic head with additive migrations | ACCEPTED |
| 002 | Dedicated background worker process | ACCEPTED |
| 003 | Transactional outbox for durable events | ACCEPTED |
| 004 | Structural multi-tenancy at query construction | ACCEPTED |
| 005 | Money as integer minor units | ACCEPTED |
| 006 | Deterministic engines over ML/AI | ACCEPTED |
| 007 | One-shot migration-init service | ACCEPTED |
| 008 | PostgreSQL for production; SQLite only for unit tests | ACCEPTED |
| 009 | No LLM/AI runtime dependency in the migration engine | ACCEPTED |

## Status summary

All 9 records are ACCEPTED — each corresponds to verified repository state
(see the referenced files/commits in each record). Proposed designs
(simulation/optimization/graph/temporal) are tracked in
`TARGET_ARCHITECTURE.md` and their design docs, not as ACCEPTED ADRs.
