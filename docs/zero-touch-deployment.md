# Zero-Touch Deployment

A single command boots the entire SDMAS platform — no environment variables
to edit, no secrets to generate, no manual migration steps.

## Prerequisites

- **Docker** 24+ with Compose plugin (v2.23+)
- **Git**
- **4 GB RAM** available for Docker (8 GB recommended)

## One-Command Startup

```bash
# Clone the repository
git clone <repo-url> sdmas-v2
cd sdmas-v2

# Start the full stack — this is the only command you need
./enterprise up
```

On first run Docker builds every image and runs the database migration
automatically.  Subsequent starts reuse cached images.

### Equivalent docker compose command

If `./enterprise` is not available, run:

```bash
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas up --build --detach
```

## Expected Services

| Service | Purpose | Depends On |
|---|---|---|
| `postgres` | PostgreSQL 16 database | — |
| `redis` | Redis 7 cache / queue | — |
| `migration-init` | One-shot Alembic migration | postgres healthy |
| `api` | FastAPI (Uvicorn) | migration-init completed |
| `worker` | Background job processor | migration-init completed |
| `web` | Nginx serving the SPA | api |
| `nginx` | Reverse proxy (api + spa) | api, web |

The dependency graph:

```
postgres ──→ migration-init ──→ api
     │                        └→ worker
     └────────────────────────┘→ worker
redis ──────────────────────────→ api
                                └→ worker
```

## URLs

| Service | URL |
|---|---|
| Frontend (SPA) | http://localhost:80 |
| API (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Health | http://localhost:8000/health |
| API Readiness | http://localhost:8000/ready |
| Nginx health check | http://localhost:80/health-check |
| PostgreSQL | localhost:5432 (sdmas / sdmas_db) |
| Redis | localhost:6379 |

## Health Verification

```bash
# Quick summary
./enterprise health

# Full verification script
./infrastructure/scripts/verify-health.sh
```

The verification script checks:

- PostgreSQL accepts connections
- Redis responds to `PING`
- API health endpoint returns `healthy`
- API readiness endpoint returns `ready`
- API database component shows `healthy`
- Worker process is running
- Frontend returns HTTP 200
- Nginx health-check returns `ok`
- Swagger UI is accessible

## Shutdown

```bash
# Stop all services (data persists in volumes)
./enterprise down

# Stop and remove all data (irreversible)
./enterprise reset
```

## Reset

```bash
# Remove all data volumes, rebuild images, and restart
./enterprise reset
```

This destroys the PostgreSQL and Redis data volumes.  The migration runs
automatically on the next `./enterprise up`.

## Manual Migration

```bash
# Run pending migrations without restarting the stack
./enterprise migrate
```

## Running Tests

```bash
# Run both API and frontend test suites
./enterprise test
```

## Enterprise Script Reference

```bash
./enterprise [command]

Commands:
  up        Start the full stack (build, migrate, run)
  down      Stop all services
  health    Check all services are healthy
  logs      Tail logs from all services
  test      Run the API and frontend test suites
  reset     Stop, remove volumes, rebuild
  migrate   Run Alembic migrations manually
  help      Show this help message
```

## Production Deployment Differences

The zero-touch experience uses **hardcoded development defaults** for
secrets and passwords.  This is intentional and safe — the API refuses to
start with development defaults when `ENVIRONMENT=production`.

For production, use the dedicated compose file:

```bash
docker compose -f infrastructure/docker/docker-compose.production.yml up -d
```

Key differences:

| Aspect | Development (zero-touch) | Production |
|---|---|---|
| Secrets | Hardcoded dev defaults | Docker secrets + env file |
| Database password | `sdmas_dev` | Random, in `secrets/db_password.txt` |
| JWT secret | `dev-secret-do-not-use-in-production` | Random, in `secrets/jwt_secret.txt` |
| SSL | None | Let's Encrypt via nginx |
| Monitoring | Not included | Prometheus + Grafana + OTel |
| API replicas | 1 | 3 |
| Worker replicas | 1 | 2 |
| Rate limiting | None | nginx rate limiting |
| Migration | Automatic one-shot | Via deploy script |

## Troubleshooting

### "docker compose" command not found

Ensure Docker Desktop or Docker CE is installed and the Compose plugin is
available.  Verify with:

```bash
docker compose version
```

Old Docker installations may need `docker-compose` (with hyphen) instead;
the compose file is compatible with both.

### Migration fails

```bash
# Check the migration-init logs
./enterprise logs migration-init

# If the database connection failed, verify PostgreSQL is healthy:
docker compose -f infrastructure/docker/docker-compose.yml ps postgres

# Run migration manually after fixing the issue:
./enterprise migrate
```

### API not healthy

```bash
# Check API logs
./enterprise logs api

# Verify the database has the schema:
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
    psql -U sdmas -c "\dt" | head -20
```

### Worker not processing jobs

```bash
./enterprise logs worker
```

The worker uses `restart: unless-stopped` — if it exits abnormally Docker
restarts it.  Check the logs for Python tracebacks.

### Port conflicts

If ports 80, 5432, or 6379 are already in use, stop the conflicting
services or change the port mappings in
`infrastructure/docker/docker-compose.yml`.

## Architecture / Dependency Diagram

```
┌──────────┐    ┌──────────┐
│ postgres │    │  redis   │
│  :5432   │    │  :6379   │
└────┬─────┘    └────┬─────┘
     │ health        │ health
     ▼               ▼
┌──────────────────────────┐
│     migration-init       │  ← one-shot `alembic upgrade head`
│  (exits after success)   │
└──────────┬───────────────┘
           │ service_completed_successfully
           ▼
┌──────────┴──────────┐    ┌───────────────┐
│        api          │    │    worker     │
│  FastAPI (Uvicorn)  │    │  background   │
│  :8000              │    │  job processor│
└──────────┬──────────┘    └───────────────┘
           │                             │
           ▼                             │
┌──────────────────┐                    │
│       web        │                    │
│  Nginx (SPA)     │                    │
│  :80 internal    │                    │
└──────────┬───────┘                    │
           │                            │
           ▼                            │
┌──────────────────┐                    │
│  nginx proxy     │◄───────────────────┘
│  :80 (external)  │
│  /api/ → api:8000│
│  /     → web:80  │
└──────────────────┘
```