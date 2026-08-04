# SDMAS v2 — Migration Record

## Status: COMPLETE

The migration from the JavaScript SDMAS v1 implementation to the Python FastAPI
SDMAS v2 backend is **complete**. The v1 stack has been archived and no longer
runs as part of the production system.

## What happened

- **v1 JavaScript DI-container stack** (root-level `ConfigurationLoader.js`,
  `di-container.js`, `implementations/`, `interfaces/`, `migrations/`,
  `student-cli.js`, `academic-cli.js`, `bootstrap/`, `examples/`, etc.) was
  archived in full to `_archive/legacy-v1/` with a `DEPRECATED.md` manifest.
- **v1 Python foundation modules** (root-level `mysql_provider.py`,
  `pool_manager.py`, `repository_base.py`, `migration_runner.py`,
  `audit_logger.py`, `crud.py`, `user_dto.py`, etc.) were archived with the same
  stack.
- **Domain migration**: all domains live in `apps/api/app/domains/` — student,
  academic, academic_ops, attendance, attendance_intelligence, admission,
  analytics, audit, billing, class_360, command_center, documents, events,
  fees, institution, jobs, leave, notifications, parent, reports, report_builder,
  report_cards, school_finance, student_360, student_portal, teacher_360,
  timeline, workflow, and more.
- **Authentication & authorization**: JWT access/refresh tokens, RBAC
  permissions, platform-role separation, and structural multi-tenancy are
  implemented (see `AUTHORIZATION.md` and `TENANCY.md`).
- **Frontend**: React + Vite + TypeScript web app (`apps/web/`, PWA with dark
  mode) and Expo/React Native mobile app (`apps/mobile/`).
- **Migrations**: Alembic under `apps/api/alembic/versions/` (37+ versions,
  including tenant-boundary and finance-ledger hardening).

## Migration phases (historical record)

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Architecture Reconciliation | Complete |
| 1 | Repository Scaffolding + Backend Foundation | Complete |
| 2 | Domain Migration (Student, Academic, Attendance, Fees, …) | Complete |
| 3 | Authentication & Authorization | Complete |
| 4 | AI & Analytics | Complete |
| 5 | Frontend (web + mobile) | Complete |
| 6 | JS Archival + Cleanup | Complete |

## Rules carried forward

1. Do **not** modify anything under `_archive/` — it is a read-only record.
2. New features go into `apps/` only.
3. The canonical architecture is described in the repository root
   `ARCHITECTURE.md`; this file is the historical migration record.

## Current structure

```
sdmas-v2/
├── apps/
│   ├── api/                 # Backend — Python 3.11+ FastAPI, SQLAlchemy 2 (async), Alembic
│   ├── web/                 # Frontend — React + Vite + TypeScript (PWA, dark mode)
│   └── mobile/              # Mobile — Expo / React Native
├── infrastructure/          # Docker Compose, Nginx, monitoring, ops scripts
├── docs/                    # Standards, contribution, historical migration records
├── legacy/                  # Marker pointing to the archived v1 stack
└── _archive/
    ├── legacy-v1/           # Archived SDMAS v1 (JS + Python), read-only
    └── backend/             # Earlier Python foundation skeleton, preserved
```
