#!/bin/bash
# =============================================================
# SDMAS v2 — Rollback Script
# Reverts to a previous Docker Compose release.
# =============================================================
set -euo pipefail

ENVIRONMENT="${1:-production}"
PREVIOUS_TAG="${2:-}"

COMPOSE_FILE="infrastructure/docker/docker-compose.${ENVIRONMENT}.yml"
COMPOSE_PROJECT="sdmas-${ENVIRONMENT}"

if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "Error: Compose file not found: ${COMPOSE_FILE}"
    echo "Usage: $0 [development|staging|production] [tag]"
    exit 1
fi

echo "=============================================="
echo "SDMAS v2 Rollback — ${ENVIRONMENT}"
echo "=============================================="

# Determine previous version
if [ -z "${PREVIOUS_TAG}" ]; then
    PREVIOUS_TAG=$(docker images --format "{{.Tag}}" sdmas-api | sort -V | tail -2 | head -1)
    if [ -z "${PREVIOUS_TAG}" ]; then
        echo "Error: Could not determine previous version."
        echo "Specify a tag: $0 ${ENVIRONMENT} <tag>"
        exit 1
    fi
fi

echo "Rolling back to: ${PREVIOUS_TAG}"

# Tag previous version as current
docker tag "sdmas-api:${PREVIOUS_TAG}" "sdmas-api:latest"
docker tag "sdmas-web:${PREVIOUS_TAG}" "sdmas-web:latest"
docker tag "sdmas-worker:${PREVIOUS_TAG}" "sdmas-worker:latest"

# Re-deploy
docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" up --detach

echo "Rollback complete. Verify with health checks."
