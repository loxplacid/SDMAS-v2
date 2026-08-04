# SDMAS v2 — Architecture

> The canonical, maintained architecture document lives at the repository root:
> **[`ARCHITECTURE.md`](../ARCHITECTURE.md)**. This file is a short index.

## Status

SDMAS v2 is a production school-administration platform. The v1 JavaScript
stack has been archived to `_archive/legacy-v1/` (read-only) — it is **not**
part of the running system. All of the features previously listed as
"not yet implemented" (domains, migrations, authentication, routers, AI,
frontend) are **implemented**.

## Repositories

- `apps/api/` — Backend: Python 3.11+ FastAPI, SQLAlchemy 2 (async), Pydantic v2,
  Alembic. Domains under `app/domains/`, structural multi-tenancy under
  `app/multi_tenant/`, infrastructure under `app/infrastructure/`.
- `apps/web/` — Frontend: React + Vite + TypeScript, PWA, dark mode.
- `apps/mobile/` — Mobile: Expo / React Native.
- `infrastructure/` — Docker Compose (dev/staging/prod), Nginx, monitoring
  (Prometheus/Grafana/OTel), ops scripts (backup, restore, deploy, seed).
- `docs/` — Standards, contribution guide, historical migration record.

## Technology Stack

| Component    | Technology                        |
|--------------|-----------------------------------|
| Framework    | FastAPI                           |
| ASGI Server  | Uvicorn                           |
| ORM          | SQLAlchemy 2.x (async)            |
| Database     | PostgreSQL (asyncpg)              |
| Migrations   | Alembic (async, settings-based)   |
| Validation   | Pydantic v2                       |
| Config       | Pydantic Settings (env + `.env`)  |
| Testing      | pytest, pytest-asyncio, httpx     |
| Frontend     | React + Vite + TypeScript, Expo   |
| Container    | Docker + Docker Compose           |
| Payments     | Razorpay (HMAC-verified webhooks) |

## Configuration

Configuration is managed via Pydantic Settings reading environment variables
and `.env` files (`apps/api/app/config.py`). See `apps/api/.env.example` for
available settings.

## Security & tenancy

See `SECURITY.md`, `AUTHORIZATION.md`, and `TENANCY.md` at the repository root.
