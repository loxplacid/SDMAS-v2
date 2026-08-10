#!/bin/bash
# =============================================================
# SDMAS v2 — Seed Data Script
# Runs after migrations to populate reference data.
# =============================================================
set -euo pipefail

ENVIRONMENT="${1:-development}"
COMPOSE_PROJECT="sdmas-${ENVIRONMENT}"

# Map ENV names to compose-file suffixes (files are docker-compose.dev.yml /
# staging.yml / production.yml).
case "${ENVIRONMENT}" in
    development) COMPOSE_SUFFIX="dev" ;;
    staging|production) COMPOSE_SUFFIX="${ENVIRONMENT}" ;;
    *) echo "Error: Unknown environment '${ENVIRONMENT}'. Use development|staging|production."; exit 1 ;;
esac
COMPOSE_FILE="infrastructure/docker/docker-compose.${COMPOSE_SUFFIX}.yml"

echo "[$(date +%H:%M:%S)] Seeding data for ${ENVIRONMENT}..."

docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" run --rm api \
    python -m scripts.seed

docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" run --rm api \
    python -m scripts.seed_student_portal

echo "[$(date +%H:%M:%S)] Seed complete."
