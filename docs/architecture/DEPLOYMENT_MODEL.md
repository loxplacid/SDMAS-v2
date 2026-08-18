# DEPLOYMENT MODEL — SDMAS v2

Date: 2026-08-17 · Source: `infrastructure/docker/`, `infrastructure/scripts/`,
`Makefile`, `enterprise`, `.github/workflows/`, `apps/api/Dockerfile*`,
`apps/web/Dockerfile`, `DEPLOYMENT.md`, `docs/zero-touch-deployment.md`
(verified).

---

## 1. Zero-touch deployment (dev/demo)

Canonical first-run command:

```bash
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas up --build -d
# or simply: ./enterprise up
```

Starts, in dependency order:

```
postgres (healthy)
   ↓
redis (healthy)
   ↓
migration-init (one-shot: alembic upgrade head, exits 0)
   ↓
api ──┐
worker ┘  (both gate on migration-init: service_completed_successfully)
   ↓
web (SPA, nginx) ──┐
nginx (reverse proxy) ┘
```

### Service table (`docker-compose.yml`)

| Service | Image/build | Healthcheck | Restart | Notes |
|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `pg_isready -U sdmas` (5s/5s/5) | unless-stopped | volume `postgres_data`; dev creds `sdmas/sdmas_dev` (dev-only) |
| `redis` | `redis:7-alpine` | `redis-cli ping` (5s/5s/5) | unless-stopped | port 6379 |
| `migration-init` | `apps/api/Dockerfile` | none (one-shot) | **no** (restart: no) | command `alembic upgrade head`; fails deployment on failure; exit 0 = success |
| `api` | `apps/api/Dockerfile` | uvicorn `/health` (via image HEALTHCHECK) | unless-stopped | port 8000; depends migration-init completed + postgres/redis healthy; volume `storage_data:/app/storage` |
| `worker` | `apps/api/Dockerfile.worker` | **HEALTHCHECK NONE** (background process, no HTTP) | unless-stopped | `python -m app.domains.jobs.worker`; same depends_on; scheduler enabled |
| `web` | `apps/web/Dockerfile` | `wget http://127.0.0.1:8080/health-check` (non-root nginx on 8080) | unless-stopped | multi-stage build; serves SPA |
| `nginx` | `nginx:1.27-alpine` | (via web health path) | unless-stopped | port 80; mounts `dev.conf` |

Volumes: `postgres_data`, `storage_data` (shared API↔worker file storage).

### Dependency conditions

- `api` and `worker` depend on `migration-init: service_completed_successfully`
  — application services **never start before the schema is at head**.
- Migration is concurrency-safe: exactly one one-shot container runs it
  (not per-replica), and repeated runs are idempotent (`alembic upgrade
  head` is a no-op at head).

### Zero-touch environment

- Safe dev defaults in compose: `ENVIRONMENT=development`,
  `JWT_SECRET=dev-secret-do-not-use-in-production`, dev DB password,
  `CORS_ORIGINS` for localhost ports. No manual `.env` editing required.
- **Production stays different**: `docker-compose.production.yml` uses
  Docker secrets / injected env / external secret manager; the app hard-fails
  at boot if production still has placeholder secrets.

## 2. Environments & compose variants

| File | Use | Notes |
|---|---|---|
| `docker-compose.yml` | zero-touch dev/demo | canonical first-run |
| `docker-compose.dev.yml` | development | standalone dev stack (its own project `sdmas-dev`; own volumes/ports) |
| `docker-compose.staging.yml` | staging | closer to prod shape |
| `docker-compose.production.yml` | production | secrets, SSL, monitoring, resource bounds, no hardcoded defaults |

Makefile maps `ENV` → compose suffix (`development→dev`), project name
`sdmas-<env>`.

## 3. Container images

### `apps/api/Dockerfile` (API + migration-init)

- `python:3.11-slim`; pip installs `--prefix=/opt/sdmas` (not `--user` —
  the historical `/root/.local` failure: `/root` is 0700 on Debian slim so
  the runtime user couldn't traverse it; `/opt/sdmas` is world-readable);
  `ENV PATH=/opt/sdmas/bin:$PATH`, `PYTHONPATH` set explicitly; runs as
  `USER sdmas` (non-root); `PYTHONDONTWRITEBYTECODE=1`.
- CMD uvicorn (API); migration-init overrides command with
  `alembic upgrade head`.

### `apps/api/Dockerfile.worker` (worker)

- Same base + prefix install with `--require-hashes` (requirements.txt
  generated from `uv.lock`, pinned + hashed).
- **Truthful health**: the worker is a background process that listens on no
  port — `HEALTHCHECK NONE` + `restart: unless-stopped` instead of a fake
  HTTP probe against port 8000 (documented in the Dockerfile).
- `USER sdmas`; pre-created `/app/storage` owned by sdmas (shared volume).

### `apps/web/Dockerfile` (frontend)

- Multi-stage: `node:20-alpine` build (`npm ci` + `npm run build`) →
  `nginx:1.27-alpine` runtime; `apk upgrade` for base-layer CVEs; non-root
  `sdmas` user; unprivileged port 8080; healthcheck probes `127.0.0.1`
  (Alpine resolves `localhost` to `::1` but nginx listens on IPv4 only).

## 4. Operations

### `enterprise` script (bash, cross-platform via Git Bash on Windows)

| Command | Action |
|---|---|
| `./enterprise up` | build + start the full stack |
| `./enterprise down` | stop all services |
| `./enterprise health` | check all services healthy |
| `./enterprise logs` | tail logs |
| `./enterprise test` | API + web test suites |
| `./enterprise audit` | generate security due-diligence evidence package |
| `./enterprise reset` | down + remove volumes + rebuild |
| `./enterprise migrate` | run `alembic upgrade head` manually |
| `./enterprise demo-seed` / `demo-reset` | seed / wipe + reseed the three-tenant demo (guarded against production) |

### `infrastructure/scripts/`

`deploy.sh`, `rollback.sh`, `backup-db.sh`, `restore-db.sh`, `init-db.sh`,
`seed-data.sh`, `verify-health.sh`.

### Makefile targets

`dev`, `build*`, `deploy`, `rollback`, `migrate*`, `seed`, `backup`,
`restore`, `test*`, `lint`, `format`, `security-audit` (+ `-offline`),
`metrics`, `health`, `clean`, `ps`, `logs`, `shell`.

## 5. CI/CD (`.github/workflows/ci.yml`, `sbom_validation.yml`)

| Job | What it gates |
|---|---|
| `api` | ruff lint + format (changed files), mypy (changed files), full unit+security+async suite (SQLite in-memory, `-m "not integration"`) |
| `api-integration` | Docker/Testcontainers integration tests (`-m integration`) |
| `migrations` | exactly **one** Alembic head + `alembic upgrade head` against a PostgreSQL 16 service container |
| `docker-build` | builds all three images (buildx) + smoke tests (API import, web nginx config syntax) |
| `web` | `npm ci` from lockfile, `tsc --noEmit`, vitest, production build, `npm audit --audit-level=high` |
| `mobile` | `npm ci`, `tsc --noEmit`, jest (fails on zero tests) |
| `security` | Gitleaks container scan, tracked-`.env` guard, hardcoded-credential pattern scan |
| `evidence` | Bandit (HIGH gate), pip-audit (waived-list gate), SBOM generation + schema validation + determinism, evidence package checksums |

`sbom_validation.yml` additionally gates byte-reproducible SBOMs
(CycloneDX 1.5 / SPDX 2.3; see `scripts/python_sbom.sh`,
`scripts/node_sbom.sh`, `scripts/_sbom_common.sh`, `sbom/`).

## 6. Backup / restore / recovery

- `backup-db.sh` / `restore-db.sh` wrap `pg_dump`/`pg_restore` for
  PostgreSQL.
- `deploy.sh` / `rollback.sh` support staged rollouts and rollback to a
  previous version.
- Migration downgrade path exists for recent revisions (verified 051→049);
  full-chain downgrade is best-effort and intended for local development
  (CURRENT_STATE.md §5).

## 7. Verification commands an acquirer can run

```bash
# zero-touch boot
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas up --build -d
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas ps
curl -s http://localhost:8000/health && curl -s http://localhost:8000/ready
# migrations
cd apps/api && uv run alembic heads          # expect 1 head
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas \
  uv run alembic current                    # expect head
# tests / security
make test                                   # API suite (no Docker)
make security-audit                         # evidence package
```

See `DEPLOYMENT.md` and `docs/zero-touch-deployment.md` for the full
operational guide.
