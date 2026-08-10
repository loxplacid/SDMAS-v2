#!/bin/bash
# =============================================================
# SDMAS v2 — Health Verification Script
# =============================================================
# Verifies every service in the zero-touch deployment is
# operational and the system as a whole is functional.
# Exits 0 if healthy, 1 otherwise.
#
# Usage:
#   ./infrastructure/scripts/verify-health.sh
# =============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
TIMEOUT=10

check() {
    local label="$1"
    local cmd="$2"
    local expected="$3"
    local result

    if result=$(eval "$cmd" 2>/dev/null); then
        if [[ "$result" == *"$expected"* ]]; then
            echo -e "  ${GREEN}✓${NC} $label"
            PASS=$((PASS + 1))
        else
            echo -e "  ${RED}✗${NC} $label — unexpected response: $result"
            FAIL=$((FAIL + 1))
        fi
    else
        echo -e "  ${RED}✗${NC} $label — command failed"
        FAIL=$((FAIL + 1))
    fi
}

echo "=============================================="
echo "  SDMAS — Health Verification"
echo "=============================================="
echo ""

# ── PostgreSQL ────────────────────────────────────────────
echo "→ PostgreSQL"
check "pg_isready" \
    "docker compose -f infrastructure/docker/docker-compose.yml -p sdmas exec -T postgres pg_isready -U sdmas" \
    "accepting connections"

# ── Redis ─────────────────────────────────────────────────
echo "→ Redis"
check "redis ping" \
    "docker compose -f infrastructure/docker/docker-compose.yml -p sdmas exec -T redis redis-cli ping" \
    "PONG"

# ── API health ────────────────────────────────────────────
echo "→ API /health"
check "health endpoint" \
    "curl -sf --max-time $TIMEOUT http://localhost:8000/health" \
    "healthy"

# ── API readiness ─────────────────────────────────────────
echo "→ API /ready"
check "readiness endpoint" \
    "curl -sf --max-time $TIMEOUT http://localhost:8000/ready" \
    "ready"

# ── API database connectivity ─────────────────────────────
echo "→ API database check"
check "database component healthy" \
    "curl -sf --max-time $TIMEOUT http://localhost:8000/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"components\",{}).get(\"database\",{}).get(\"status\",\"\"))'" \
    "healthy"

# ── Worker alive ──────────────────────────────────────────
echo "→ Worker"
check "worker process running" \
    "docker compose -f infrastructure/docker/docker-compose.yml -p sdmas exec -T worker pgrep -f 'app.domains.jobs.worker'" \
    ""

# ── Frontend ──────────────────────────────────────────────
echo "→ Frontend (Nginx proxy)"
check "frontend HTTP 200" \
    "curl -s -o /dev/null -w '%{http_code}' --max-time $TIMEOUT http://localhost:80/" \
    "200"

# ── Nginx health check ────────────────────────────────────
echo "→ Nginx health-check"
check "health-check endpoint" \
    "curl -sf --max-time $TIMEOUT http://localhost:80/health-check" \
    "ok"

# ── API docs ──────────────────────────────────────────────
echo "→ API docs (Swagger)"
check "Swagger UI accessible" \
    "curl -sf --max-time $TIMEOUT http://localhost:8000/docs" \
    "swagger"

# ── Summary ───────────────────────────────────────────────
echo ""
echo "=============================================="
if [ $FAIL -eq 0 ]; then
    echo -e "  ${GREEN}All $PASS checks passed${NC}"
    echo "=============================================="
    exit 0
else
    echo -e "  ${RED}$FAIL/$((PASS + FAIL)) checks failed${NC}"
    echo "=============================================="
    exit 1
fi