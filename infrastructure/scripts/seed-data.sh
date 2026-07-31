#!/bin/bash
# =============================================================
# SDMAS v2 — Seed Data Script
# Runs after migrations to populate reference data.
# =============================================================
set -euo pipefail

ENVIRONMENT="${1:-development}"
COMPOSE_FILE="infrastructure/docker/docker-compose.${ENVIRONMENT}.yml"
COMPOSE_PROJECT="sdmas-${ENVIRONMENT}"

echo "[$(date +%H:%M:%S)] Seeding data for ${ENVIRONMENT}..."

docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" run --rm api \
    python -m scripts.seed

docker compose -f "${COMPOSE_FILE}" -p "${COMPOSE_PROJECT}" run --rm api \
    python -m scripts.seed_student_portal

echo "[$(date +%H:%M:%S)] Seed complete."
