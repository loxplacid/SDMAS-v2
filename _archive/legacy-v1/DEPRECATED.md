# _archive/legacy-v1 — Deprecated SDMAS v1 Stack (Archived 2026-08)

> **Status: DEPRECATED — read-only archive. Do not build on this code.**

This directory contains the complete pre-`apps/` implementation of SDMAS,
archived verbatim during the architecture-consolidation pass. It is kept for
historical reference and behavioral comparison only. Nothing here is imported
by, deployed with, or referenced by the canonical system.

## Why it was archived

The repository grew two overlapping implementations side by side:

1. **JavaScript v1** — an "Enterprise DI Container" demo (configuration
   manager, DI container, database connector, repository/service layers,
   session/security/theme/AI managers, event bus, CLI tools, and its own
   migration system with ~488 Jest tests).
2. **Python v1 foundation** — root-level modules (`mysql_provider.py`,
   `pool_manager.py`, `repository_base.py`, `crud.py`, `migration_runner.py`,
   loggers, `bootstrap/`) and `_archive/backend` (an early FastAPI skeleton).

The canonical production system (`apps/api` + `apps/web` + `apps/mobile`)
fully supersedes both. Reference analysis confirmed **zero imports or runtime
references** from `apps/`, `infrastructure/`, `Makefile`, Dockerfiles, or
deployment scripts — so this stack was relocated here without migrating any
live callers.

## What's inside

| Path | Content |
|---|---|
| `*.js`, `di-*.js`, `jest.config.js`, `package*.json` | JavaScript v1 DI-container demo + CLI tools |
| `implementations/`, `interfaces/` | v1 JS component implementations & contracts |
| `migrations/` | v1 JS database migrations (superseded by Alembic) |
| `examples/` | v1 JS runnable examples |
| `tests/` | v1 JS (Jest) + v1 Python unit tests |
| `*.py` (root of this dir) | v1 Python providers, loggers, repository base, CRUD helper |
| `bootstrap/` | v1 Python application bootstrap (superseded by `apps/api` lifespan) |
| `ROADMAP.md` | v1 "Enterprise DI Container" roadmap |

## Canonical replacements

| Deprecated here | Canonical replacement |
|---|---|
| `ConfigurationLoader.js` / `EnvironmentConfigurationProvider.js` / `config_watcher.js` / `secrets_provider.js` | `apps/api/app/config.py` (pydantic-settings) |
| `di-container.js` / `di-setup.js` / `interfaces/` | FastAPI dependency injection (`Depends`) |
| `implementations/database.js` / root `*_provider.py` / `pool_manager.py` / `connection_manager.py` | `apps/api/app/infrastructure/database.py` (async SQLAlchemy) |
| `implementations/repository.js` / `repository_base.py` / `crud.py` | `apps/api/app/multi_tenant/repository.py` (TenantScopedRepository) + per-domain repositories |
| `implementations/service.js` | Per-domain services under `apps/api/app/domains/*/service.py` |
| `implementations/security-manager.js` / `session-manager.js` | `apps/api/app/domains/auth` (JWT, roles, permissions) |
| `implementations/event-bus.js` | `apps/api/app/domains/events` + `apps/api/app/domains/notifications/dispatcher.py` |
| `implementations/logger.js` / `audit_logger.py` / `logger_setup.py` / `logging_config.py` / `performance_logger.py` | `apps/api/app/core/observability` (JSON logging, OTel) + `apps/api/app/domains/audit` |
| `implementations/migration-runner.js` / `migrations/` / `migration_runner.py` | `apps/api/alembic/` (41 migrations) |
| `bootstrap/` | `apps/api/app/main.py` lifespan + `apps/api/app/domains/jobs/worker.py` |
| `business_exception.py` / `user_dto.py` | `apps/api/app/core/exceptions.py` + pydantic schemas |
| `student-cli.js` / `academic-cli.js` | REST API + `apps/web` |
