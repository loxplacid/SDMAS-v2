#!/bin/bash
# =============================================================
# SDMAS v2 — Database Backup Script
# Creates timestamped PostgreSQL backups with rotation.
# =============================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-sdmas}"
DB_USER="${DB_USER:-sdmas}"
DB_PASSWORD="${DB_PASSWORD:-}"
S3_BUCKET="${S3_BUCKET:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="sdmas_${DB_NAME}_${TIMESTAMP}.sql.gz"
LATEST_LINK="${BACKUP_DIR}/latest.sql.gz"

mkdir -p "${BACKUP_DIR}"

export PGPASSWORD="${DB_PASSWORD}"

echo "[$(date +%H:%M:%S)] Starting backup: ${DB_NAME}@${DB_HOST}:${DB_PORT}"

pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    --verbose \
    2>&1 \
    | gzip > "${BACKUP_DIR}/${FILENAME}"

BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "[$(date +%H:%M:%S)] Backup complete: ${BACKUP_DIR}/${FILENAME} (${BACKUP_SIZE})"

# Update latest symlink
ln -sf "${BACKUP_DIR}/${FILENAME}" "${LATEST_LINK}"

# Rotate old backups
find "${BACKUP_DIR}" -name "sdmas_${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# Optional: upload to S3-compatible storage
if [ -n "${S3_BUCKET}" ]; then
    echo "[$(date +%H:%M:%S)] Uploading to S3: s3://${S3_BUCKET}/postgres/${FILENAME}"
    aws s3 cp "${BACKUP_DIR}/${FILENAME}" "s3://${S3_BUCKET}/postgres/${FILENAME}" --only-show-errors
    echo "[$(date +%H:%M:%S)] Upload complete"
fi

echo "[$(date +%H:%M:%S)] Backup finished successfully"
