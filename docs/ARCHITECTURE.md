# SDMAS v2 — Architecture

## Overview

SDMAS (School Data Management & Analytics System) v2 is a flagship-level rewrite of the existing SDMAS v1 JavaScript implementation. The new backend is built with Python + FastAPI, following clean architecture principles.

## Phase 1 Scope (Current)

The goal of Phase 1 is to establish a production-ready Python backend foundation.

**Completed:**
- Repository scaffolding (`apps/api/`)
- Project configuration (`pyproject.toml`, `requirements.txt`)
- Configuration management (Pydantic Settings, `.env` support)
- Async SQLAlchemy infrastructure (engine, session factory, session dependency)
- FastAPI application with `/health` and `/ready` endpoints
- Core foundation (exception hierarchy, pagination primitives)
- Alembic configuration (async, settings-based)
- Test infrastructure (pytest, async fixtures, httpx)
- Docker Compose development environment (PostgreSQL, Redis, API)
- Documentation (README, architecture, migration plan)

**Not yet implemented (later phases):**
- Domain models (Student, Academic, Attendance, Fees)
- Domain migrations
- Authentication / authorization
- API routers for domain entities
- AI / Analytics services
- Frontend

## Project Structure

```
sdmas-v2/
├── apps/api/            # Python FastAPI backend
├── infrastructure/      # Docker, CI/CD configs
├── docs/                # Architecture & migration docs
├── legacy/              # Future home of JS reference
├── backend/             # Existing Python foundation (preserved)
├── tests/               # Existing JS tests (preserved)
├── ...JS files...       # Legacy JS implementation
```

## JavaScript Legacy

The existing JavaScript implementation in the repository root is the **legacy behavioral reference**. It contains ~488 tests across ~6200 lines. It remains in place and will be archived into `legacy/` only after Python behavioral parity is verified.

## Technology Stack

| Component       | Technology                        |
|----------------|-----------------------------------|
| Framework       | FastAPI                           |
| ASGI Server     | Uvicorn                           |
| ORM             | SQLAlchemy 2.x (async)            |
| Database        | PostgreSQL (asyncpg)              |
| Migrations      | Alembic                           |
| Validation      | Pydantic v2                       |
| Config          | Pydantic Settings                 |
| Testing         | pytest, pytest-asyncio, httpx     |
| Linting         | Ruff                              |
| Type Checking   | mypy                              |
| Container       | Docker + Docker Compose           |

## Configuration

Configuration is managed via Pydantic Settings, reading from environment variables and `.env` files. See `.env.example` for available settings.