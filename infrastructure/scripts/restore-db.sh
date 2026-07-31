#!/bin/bash
# =============================================================
# SDMAS v2 — Database Restore Script
# Usage: ./restore-db.sh <backup-file>
# =============================================================
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup-file>"
    echo "  backup-file: Path to .sql.gz file or 'latest' for most recent"
    exit 1
fi

BACKUP_FILE="$1"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-sdmas}"
DB_USER="${DB_USER:-sdmas}"
DB_PASSWORD="${DB_PASSWORD:-}"

if [ "${BACKUP_FILE}" = "latest" ]; then
    BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
    BACKUP_FILE="${BACKUP_DIR}/latest.sql.gz"
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

export PGPASSWORD="${DB_PASSWORD}"

echo "[$(date +%H:%M:%S)] WARNING: This will overwrite the current database."
echo "[$(date +%H:%M:%S)] Target: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "[$(date +%H:%M:%S)] Source: ${BACKUP_FILE}"
read -rp "Are you sure? (type 'yes' to continue): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Restore cancelled."
    exit 1
fi

echo "[$(date +%H:%M:%S)] Dropping and recreating database..."

# Terminate existing connections
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres <<-SQL
    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = '${DB_NAME}'
      AND pid <> pg_backend_pid();
SQL

dropdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${DB_NAME}"
createdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${DB_NAME}"

echo "[$(date +%H:%M:%S)] Restoring from backup..."
gunzip -c "${BACKUP_FILE}" | psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}"

echo "[$(date +%H:%M:%S)] Restore complete!"
echo "[$(date +%H:%M:%S)] Run migrations if needed: alembic upgrade head"
