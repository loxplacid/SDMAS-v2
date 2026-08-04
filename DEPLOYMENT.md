# SDMAS v2 — Deployment Guide

## Architecture Overview

```
                     ┌─────────────┐
                     │   DNS / CDN  │
                     │ (Cloudflare) │
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │   Nginx     │  ← Reverse proxy, SSL termination, rate limiting
                     │  (1.27)     │
                     └──┬──────┬───┘
                        │      │
              ┌─────────▼┐  ┌──▼──────────┐
              │  API      │  │   Web       │  ← React SPA (PWA)
              │  (FastAPI)│  │  (Nginx)    │
              │  ×3 pods  │  │  ×2 pods    │
              └────┬──────┘  └─────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
  ┌─────▼───┐ ┌───▼────┐ ┌───▼──────────┐
  │PostgreSQL│ │ Redis  │ │   Worker     │
  │  16-alp. │ │  7-alp. │ │  ×2 pods     │
  └──────────┘ └────────┘ └──────────────┘
                            │
                     ┌──────▼──────┐
                     │  Background │  ← Job queue, billing, migration
                     │   Jobs DB   │
                     └─────────────┘

   Monitoring:
   ┌──────────┐    ┌──────────┐    ┌────────┐
   │OTel Coll.│───▶│Prometheus│───▶│Grafana │
   └──────────┘    └──────────┘    └────────┘
```

## Environments

| Environment | Compose File | Purpose |
|---|---|---|
| **Development** | `infrastructure/docker/docker-compose.dev.yml` | Local development with hot-reload |
| **Staging** | `infrastructure/docker/docker-compose.staging.yml` | Pre-production validation |
| **Production** | `infrastructure/docker/docker-compose.production.yml` | Live deployment |

## Quick Start (Local Development)

### Prerequisites

- Docker Desktop (or Docker CE + Docker Compose plugin)
- Git
- Node.js 20+ (for frontend dev outside Docker)

### Setup

```bash
# Clone repository
git clone <repo-url> && cd sdmas-v2

# Start development environment
make dev

# Run migrations
make migrate

# Seed reference data
make seed
```

The app will be available at:
- Frontend: `http://localhost:5173` (Vite dev server outside Docker)
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### Frontend Development Outside Docker

```bash
cd apps/web
npm install
npm run dev
```

The Vite dev server proxies API requests to `http://localhost:8000`.

## Production Deployment

### Server Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 50 GB SSD | 100 GB SSD |
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 |

### Step-by-Step Deployment

```bash
# 1. Clone and prepare
git clone <repo-url> /opt/sdmas
cd /opt/sdmas

# 2. Generate secrets
openssl rand -base64 32 > infrastructure/secrets/db_password.txt
openssl rand -base64 64 > infrastructure/secrets/jwt_secret.txt
echo "rzp_live_xxxxxxxxxxxx" > infrastructure/secrets/razorpay_key_id.txt
echo "xxxxxxxxxxxxxxxxxxxx" > infrastructure/secrets/razorpay_key_secret.txt
chmod 600 infrastructure/secrets/*.txt

# 3. Set environment variables
export ENVIRONMENT=production
export GRAFANA_PASSWORD=$(openssl rand -base64 16)

# 4. Build images
make build

# 5. Deploy
make deploy ENV=production

# 6. Verify
make health
make metrics
```

### Zero-Downtime Deployment

The deployment script (`infrastructure/scripts/deploy.sh`) handles:

1. **Rolling update** — Services are updated one at a time
2. **Health checks** — Each new container must pass `/health` before traffic is routed
3. **Pre-deploy migrations** — Alembic runs before new API containers start
4. **Rollback** — If health checks fail, the previous deployment is preserved

To force a rolling update without downtime:

```bash
docker compose -f infrastructure/docker/docker-compose.production.yml up --detach --no-deps --scale api=4 api
# Wait for new containers to be healthy
docker compose -f infrastructure/docker/docker-compose.production.yml up --detach --no-deps --scale api=3 api
```

### Rollback

```bash
make rollback ENV=production
```

Or manually:

```bash
docker compose -f infrastructure/docker/docker-compose.production.yml down api
docker compose -f infrastructure/docker/docker-compose.production.yml up --detach api
```

### Database Migrations

```bash
# Run pending migrations
make migrate

# Rollback last migration
make migrate-rollback

# Auto-generate a new migration
make migrate-autogenerate

# View history
make migrate-history
```

## Scaling

### Horizontal Scaling

| Service | Strategy | Max Instances |
|---|---|---|
| API | Stateless (scale via replicas) | 10+ |
| Worker | Idempotent jobs (scale via replicas) | 5+ |
| Web | Stateless (scale via replicas) | 5+ |
| PostgreSQL | Read replicas for reporting | 3 |
| Redis | Redis Cluster for HA | 3 nodes |

### Vertical Scaling

Adjust resource limits in the compose file:

```yaml
deploy:
  resources:
    limits:
      cpus: "4"
      memory: 4G
```

### Database Connection Pooling

The API uses SQLAlchemy connection pooling. Tune via environment:

```env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
```

For high concurrency, add PgBouncer between API and PostgreSQL.

## Backup & Disaster Recovery

### Automated Backups

Backups run via cron (set up on host machine):

```bash
# Edit crontab
crontab -e

# Add: daily at 2 AM, weekly to S3
0 2 * * * cd /opt/sdmas && ./infrastructure/scripts/backup-db.sh
0 3 * * 0 cd /opt/sdmas && S3_BUCKET=sdmas-backups ./infrastructure/scripts/backup-db.sh
```

### Restore

```bash
# From latest backup
./infrastructure/scripts/restore-db.sh latest

# From specific file
./infrastructure/scripts/restore-db.sh /path/to/backup.sql.gz
```

### Disaster Recovery Plan

| Scenario | Recovery Time | Action |
|---|---|---|
| API crash | < 30s | Docker restart policy auto-recovers |
| Node failure | < 5 min | Orchestrator reschedules containers |
| Database corruption | < 1 hour | Restore from latest backup |
| Full region failure | < 4 hours | Deploy to secondary region, restore S3 backup |
| Data breach | < 15 min | Rotate all secrets, revoke JWT tokens, audit logs |

## Monitoring & Alerting

### Stack

- **OpenTelemetry Collector** — Receives traces, metrics, logs from API
- **Prometheus** — Time-series metrics storage (30-day retention)
- **Grafana** — Dashboards and alerting
- **Sentry** (optional) — Error tracking

### Dashboards

Grafana is provisioned with datasources. Create dashboards for:

1. **API Performance** — Request rate, latency (p50/p95/p99), error rate by endpoint
2. **Business Metrics** — Active schools, student count, daily attendance, fee collection
3. **Background Jobs** — Queue depth, processing time, failure rate, dead-letter count
4. **System Health** — CPU/memory/disk per service, DB connections, cache hit ratio
5. **Billing** — Active subscriptions, revenue MRR, payment success rate

### Alert Rules

Prometheus alert rules are defined in `infrastructure/monitoring/prometheus/alerts.yml`:

| Alert | Condition | Severity |
|---|---|---|
| APIInstanceDown | `up{job="api"} == 0` for 1m | Critical |
| HighAPIErrorRate | 5xx rate > 5% for 5m | Warning |
| SlowAPIResponse | P95 > 2s for 5m | Warning |
| PostgresDown | `pg_up == 0` for 30s | Critical |
| HighDBConnections | `numbackends > 50` for 5m | Warning |
| DiskSpaceLow | Available < 10% | Critical |

## Security

### Network Security

- API ports bound to `127.0.0.1` only (not exposed externally)
- All external traffic goes through Nginx (port 443)
- Rate limiting at Nginx level (30 req/s API, 5 req/m login)
- Security headers set at Nginx level

### Secrets Management

Secrets are never stored in the repository. Production uses:

1. **Docker Secrets** — Files mounted at `/run/secrets/` (default in compose)
2. **Environment variables** — Injected by the deployment platform
3. **HashiCorp Vault** — Supported via `app/core/secrets.py` (VaultBackend)
4. **Env file** — Only for development (not tracked in git)

### JWT Security

- Access tokens: 30 min expiry (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh tokens: 7 days with rotation and reuse detection
- Algorithm: HS256 (secret from `JWT_SECRET`)

### Regular Audits

- Dependency scanning: `pip audit` (Python), `npm audit` (Node)
- Secret scanning: `trufflehog` or `git-secrets` in CI
- Access log review: Monitor Nginx JSON logs for anomalies

## CI/CD Pipeline

### GitHub Actions Workflow (Suggested)

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run API tests
        run: make test-api
      - name: Run Web tests
        run: make test-web
      - name: Lint
        run: make lint

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build images
        run: make build
      - name: Push to registry
        run: |
          docker tag sdmas-api:latest registry.example.com/sdmas-api:${{ github.sha }}
          docker push registry.example.com/sdmas-api:${{ github.sha }}
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          script: |
            cd /opt/sdmas
            docker compose pull
            make deploy
```

## Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| API returns 503 | Database unreachable | Check `docker compose ps postgres` — verify health |
| Frontend shows blank page | Build failed `/` API unreachable | Check `docker compose logs web` `/` nginx logs |
| Migration fails | Conflicting schema | `alembic downgrade -1` then fix migration |
| Worker not processing jobs | DB connection or auth | Check `docker compose logs worker` |
| High memory usage | Connection leak | Tune `DB_POOL_SIZE`, restart service |
| SSL certificate expired | Certbot renewal failed | Run `certbot renew`, reload nginx |

### Logs

```bash
# All services
docker compose logs --tail=100 --follow

# Single service
make logs SERVICE=api

# Nginx access log (JSON format)
docker compose exec nginx tail -f /var/log/nginx/access.log | jq .

# API structured logs
make logs SERVICE=api | grep '"event"'
```

### Health Check Endpoints

```bash
# Liveness (is the process alive?)
curl http://localhost:8000/health

# Readiness (can it serve traffic?)
curl http://localhost:8000/ready

# Metrics (Prometheus format)
curl http://localhost:8000/metrics
```

## Maintenance

### Regular Tasks

| Frequency | Task | Command |
|---|---|---|
| Daily | Backup database | `make backup` |
| Weekly | Review error logs | `make logs SERVICE=api \| grep ERROR` |
| Weekly | Check disk usage | `df -h /var/lib/docker` |
| Monthly | Rotate JWT secret | Generate new secret, restart API |
| Monthly | Update dependencies | `cd apps/api && pip install --upgrade -r requirements.txt` |
| Quarterly | SSL certificate renewal | `certbot renew` (automatic if configured) |
| As needed | Prune old Docker images | `docker image prune --force --filter "until=30d"` |

### Updating

```bash
git pull origin main
make build
make migrate ENV=production
make deploy ENV=production
```
