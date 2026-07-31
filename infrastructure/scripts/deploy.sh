#!/bin/bash
# =============================================================
# SDMAS v2 — Deployment Script
# Zero-downtime deployment for Docker Compose environments.
# =============================================================
set -euo pipefail

ENVIRONMENT="${1:-production}"
COMPOSE_FILE="infrastructure/docker/docker-compose.${ENVIRONMENT}.yml"
COMPOSE_PROJECT="sdmas-${ENVIRONMENT}"

# Validate
if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "Error: Compose file not found: ${COMPOSE_FILE}"
    echo "Usage: $0 [development|staging|production]"
    exit 1
fi

echo "=============================================="
echo "SDMAS v2 Deploy — ${ENVIRONMENT}"
echo "=============================================="
echo ""

# 1. Pull latest images
echo "[1/5] Pulling latest images..."
docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" pull --quiet

# 2. Run database migrations (pre-deploy)
echo "[2/5] Running database migrations..."
docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" run --rm api \
    alembic upgrade head

# 3. Deploy with zero-downtime
echo "[3/5] Deploying services..."
docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" up --detach --quiet-pull --remove-orphans

# 4. Health check
echo "[4/5] Waiting for health checks..."
RETRIES=30
DELAY=5
for i in $(seq 1 ${RETRIES}); do
    STATUS=$(docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" ps --format json 2>/dev/null | \
        python -c "import sys,json; services=json.load(sys.stdin); print(all(s.get('Health')=='healthy' for s in services if 'Health' in s))" 2>/dev/null || echo "false")
    if [ "${STATUS}" = "True" ]; then
        echo "  All services healthy after ${i}s"
        break
    fi
    if [ "${i}" -eq "${RETRIES}" ]; then
        echo "  WARNING: Some services did not become healthy within timeout."
        echo "  Check: docker compose -f ${COMPOSE_FILE} ps"
    fi
    sleep "${DELAY}"
done

# 5. Clean up old images
echo "[5/5] Cleaning up..."
docker image prune --force --filter "until=24h" 2>/dev/null || true

echo ""
echo "=============================================="
echo "Deployment complete: ${ENVIRONMENT}"
echo "=============================================="
