# =============================================================
# SDMAS v2 — Makefile
# =============================================================

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

ENV ?= development
COMPOSE_FILE := infrastructure/docker/docker-compose.$(ENV).yml
COMPOSE_PROJECT := sdmas-$(ENV)

# ── Development ───────────────────────────────────────────

.PHONY: dev
dev:  ## Start development environment
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) up --build --detach
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) logs --follow

.PHONY: dev-logs
dev-logs:  ## Follow development logs
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) logs --follow

.PHONY: dev-stop
dev-stop:  ## Stop development environment
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) down

# ── Build ─────────────────────────────────────────────────

.PHONY: build
build:  ## Build all Docker images
	docker build -t sdmas-api:latest -f apps/api/Dockerfile apps/api
	docker build -t sdmas-worker:latest -f apps/api/Dockerfile.worker apps/api
	docker build -t sdmas-web:latest -f apps/web/Dockerfile apps/web

.PHONY: build-api
build-api:  ## Build API image
	docker build -t sdmas-api:latest -f apps/api/Dockerfile apps/api

.PHONY: build-web
build-web:  ## Build frontend image
	docker build -t sdmas-web:latest -f apps/web/Dockerfile apps/web

.PHONY: build-worker
build-worker:  ## Build worker image
	docker build -t sdmas-worker:latest -f apps/api/Dockerfile.worker apps/api

# ── Deploy ────────────────────────────────────────────────

.PHONY: deploy
deploy:  ## Deploy to environment (ENV=production)
	@bash infrastructure/scripts/deploy.sh $(ENV)

.PHONY: rollback
rollback:  ## Rollback to previous version (ENV=production)
	@bash infrastructure/scripts/rollback.sh $(ENV)

# ── Database ─────────────────────────────────────────────

.PHONY: migrate
migrate:  ## Run database migrations
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) run --rm api alembic upgrade head

.PHONY: migrate-rollback
migrate-rollback:  ## Rollback last migration
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) run --rm api alembic downgrade -1

.PHONY: migrate-history
migrate-history:  ## Show migration history
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) run --rm api alembic history

.PHONY: migrate-autogenerate
migrate-autogenerate:  ## Auto-generate new migration
	@read -p "Migration message: " msg; \
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) run --rm api \
		alembic revision --autogenerate -m "$$msg"

.PHONY: seed
seed:  ## Seed reference data
	@bash infrastructure/scripts/seed-data.sh $(ENV)

# ── Backup ────────────────────────────────────────────────

.PHONY: backup
backup:  ## Backup database
	@bash infrastructure/scripts/backup-db.sh

.PHONY: restore
restore:  ## Restore database (FILE=<path>)
	@bash infrastructure/scripts/restore-db.sh $(FILE)

# ── Testing ──────────────────────────────────────────────

.PHONY: test
test:  ## Run all tests
	cd apps/api && python -m pytest tests/ -v --tb=short

.PHONY: test-api
test-api:  ## Run API tests
	cd apps/api && python -m pytest tests/ -v --tb=short -m "not integration"

.PHONY: test-integration
test-integration:  ## Run integration tests (requires Docker)
	cd apps/api && python -m pytest tests/ -v --tb=short -m integration

.PHONY: test-web
test-web:  ## Run frontend tests
	cd apps/web && npm test

# ── Lint ──────────────────────────────────────────────────

.PHONY: lint
lint:  ## Run linters
	cd apps/api && ruff check .
	cd apps/api && ruff format --check .

.PHONY: format
format:  ## Format code
	cd apps/api && ruff format .
	cd apps/api && ruff check --fix .

# ── Monitoring ────────────────────────────────────────────

.PHONY: metrics
metrics:  ## Show API metrics (requires jq)
	@curl -s http://localhost:8000/metrics | jq .

.PHONY: health
health:  ## Check API health
	@curl -s http://localhost:8000/health | jq .

# ── Utility ──────────────────────────────────────────────

.PHONY: clean
clean:  ## Clean up Docker resources
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) down --volumes --remove-orphans
	docker image prune --force

.PHONY: ps
ps:  ## Show running services
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) ps

.PHONY: logs
logs:  ## Follow logs (SERVICE=<name>)
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) logs --follow $(SERVICE)

.PHONY: shell
shell:  ## Open shell in running container (SERVICE=api)
	docker compose -f $(COMPOSE_FILE) -p $(COMPOSE_PROJECT) exec $(SERVICE) /bin/sh

.PHONY: help
help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
