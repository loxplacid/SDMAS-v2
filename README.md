# SDMAS v2 — School Data Management & Analytics System

A production school-administration platform: student management, academics,
attendance, fees/billing, admissions, reports/analytics, communications, and
parent/student portals — with **structural multi-tenant isolation** at the
data layer.

## Repository layout

```
sdmas-v2/
├── apps/
│   ├── api/                 # Backend — Python 3.11+ FastAPI, SQLAlchemy 2 (async), Alembic
│   ├── web/                 # Frontend — React + Vite + TypeScript (PWA, dark mode)
│   └── mobile/              # Mobile — Expo / React Native
├── infrastructure/          # Docker Compose, Nginx, monitoring (Prometheus/Grafana/OTel), ops scripts
├── docs/                    # Coding standards, contribution & historical migration docs
├── legacy/                  # Marker for the archived SDMAS v1 (see _archive/legacy-v1)
├── _archive/                # Read-only archives: v1 stack (legacy-v1), early backend (backend)
├── Makefile                 # Canonical dev/build/deploy/test entry points
└── *.md                     # Canonical docs: ARCHITECTURE, SECURITY, AUTHORIZATION, TENANCY,
                             # DEPLOYMENT, KNOWN_LIMITATIONS
```

> The SDMAS v1 JavaScript implementation and the root Python v1 foundation
> were archived to [`_archive/legacy-v1/`](_archive/legacy-v1/DEPRECATED.md).
> The canonical system is `apps/` — nothing else is imported or deployed.

## Quick start

### Backend (apps/api)

```bash
cd apps/api
python -m venv .venv
# activate the venv (platform-specific), then:
pip install -e ".[dev]"
cp ../.env.example .env        # or set env vars
uvicorn app.main:app --reload  # http://localhost:8000/docs
```

### Whole stack with Docker

```bash
make dev        # Postgres + Redis + API + background worker via docker compose
make migrate    # alembic upgrade head
make seed       # reference/seed data
```

### Frontend (apps/web)

```bash
cd apps/web
npm install
npm run dev     # http://localhost:5173 (proxies /api → :8000)
```

## Testing

```bash
make test       # Unit/security/async suite (1,499 tests; no Docker needed)
make test-all   # Full suite including Docker-dependent integration tests
make test-web   # Frontend suite (vitest, 513 tests)
```

> The `test` target excludes Docker-dependent integration tests — the same
> default the CI pipeline uses.  Run `make test-all` or `make test-integration`
> on a machine with Docker to exercise the full suite.

## Core docs

| Doc | Covers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Canonical system design — API layering, domains, worker, web, mobile |
| [`SECURITY.md`](SECURITY.md) | Authentication, tenant isolation, webhooks, audit, secrets |
| [`AUTHORIZATION.md`](AUTHORIZATION.md) | Roles & permission model, platform access |
| [`TENANCY.md`](TENANCY.md) | Multi-tenant context, scoped repositories, guards |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Environments, deployment, scaling, backup, monitoring |
| [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) | Honest list of current gaps & risks |
| [`docs/security-assurance-report.md`](docs/security-assurance-report.md) | Machine-generated security evidence (scanners, tests, SBOM, verification status) |
| [`docs/security-policy.md`](docs/security-policy.md) | Security gate policy + accepted-risk register |

## Security evidence package

```bash
make security-audit          # scanners + tests + SBOM + assurance report
./enterprise audit           # same
make security-audit-offline  # skip network-dependent scanners
```

Generates `artifacts/` (scanner JSON, JUnit test evidence, CycloneDX 1.5 +
SPDX 2.3 SBOM copies, SHA-256 checksums, artifact manifest) and the
machine-generated [`docs/security-assurance-report.md`](docs/security-assurance-report.md).
Every number comes from a tool that actually ran.

## License

MIT
