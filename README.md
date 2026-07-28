# SDMAS v2 — School Data Management & Analytics System

This repository contains two implementations:

## 1. JavaScript DI Container (Legacy Behavioral Reference)

The existing JavaScript implementation (v1) in the repository root is a comprehensive **Enterprise Dependency Injection Container** with:

- Full dependency resolution with automatic injection
- Singleton support for stateful services
- Modular architecture following SOLID principles
- 10 implemented components (Configuration Manager, Logger, Database Connector, Repository Pattern, Service Layer, Session Manager, Security Manager, Theme Manager, AI Manager, Event Bus)
- CLI tools for student and academic operations
- Database migration system
- ~488 tests across ~6200 lines

**Status:** Active behavioral reference. This code will be archived into `legacy/` only after Python behavioral parity is verified.

```bash
npm install
npm test
```

## 2. Python FastAPI Backend (v2 — In Development)

A new Python backend being developed alongside the existing implementation in `apps/api/`.

**Current Phase:** Phase 1 — Foundation (scaffolding, configuration, database infrastructure)

### Prerequisites

- Python >= 3.11
- pip

### Setup

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -e ".[dev]"
```

### Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

### Run the API

```bash
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`.

- `GET /health` — Health check
- `GET /ready` — Readiness check (requires database)
- `http://localhost:8000/docs` — OpenAPI documentation

### Run Tests

```bash
cd apps/api
pytest
```

### Linting & Type Checking

```bash
ruff check .
ruff format --check .
mypy app/
```

### Docker Compose

Starts PostgreSQL, Redis, and the API:

```bash
docker-compose -f infrastructure/docker/docker-compose.yml up --build
```

### Alembic Migrations

```bash
cd apps/api
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Important Notes

- Domain migration has **NOT** started yet.
- No Student, Academic, Attendance, or Fees tables exist yet.
- Authentication is **NOT** implemented yet.
- The JavaScript implementation remains the authoritative behavioral reference.

## Project Structure

```
sdmas-v2/
├── apps/api/                  # Python FastAPI backend
│   ├── app/                   # Application package
│   │   ├── core/              # Exceptions, pagination
│   │   ├── infrastructure/    # Database setup
│   │   ├── config.py          # Pydantic Settings
│   │   ├── dependencies.py    # DI dependencies
│   │   └── main.py            # FastAPI application
│   ├── tests/                 # pytest test suite
│   ├── alembic/               # Database migrations
│   ├── pyproject.toml         # Project metadata
│   └── Dockerfile             # API container
├── infrastructure/docker/     # Docker Compose
├── docs/                      # Architecture & migration docs
├── legacy/                    # Future home of JS reference
├── backend/                   # Previous Python foundation (preserved)
├── tests/                     # JS test files
└── ...                        # JS implementation files
```

## License

MIT