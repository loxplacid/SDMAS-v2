#!/bin/bash
# =============================================================
# SDMAS v2 — Database Initialization Script
# Runs inside PostgreSQL container on first startup.
# =============================================================
set -e

# Create additional databases if needed
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-EOSQL
    -- Create extensions
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

    -- Create application roles (if not using default user)
    -- CREATE ROLE sdmas_app WITH LOGIN PASSWORD '${APP_DB_PASSWORD}';
    -- GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO sdmas_app;

    -- Create schemas
    CREATE SCHEMA IF NOT EXISTS app;

    -- Set search path
    ALTER DATABASE ${POSTGRES_DB} SET search_path TO app, public;
EOSQL

echo "Database initialization complete."
