# INTEGRATION MAP — SDMAS v2 External Services

Date: 2026-08-17 · Source: `apps/api/app/config.py`, `app/domains/billing/`,
`app/domains/notifications/`, `app/core/`, `infrastructure/` (verified).

Every integration below is optional at runtime where noted; the zero-touch
development stack runs with **no external credentials** (PostgreSQL + Redis
only).

---

## 1. PostgreSQL 16 — primary datastore

- **Driver**: `postgresql+asyncpg` in production / compose; `sqlite+aiosqlite`
  for unit tests only (migrations are PostgreSQL-only — documented
  limitation, CI validates migrations against PostgreSQL 16).
- **Config**: `DATABASE_URL`, `DB_POOL_SIZE` (10), `DB_POOL_MAX_OVERFLOW`
  (20).
- **Migration**: Alembic, single head `060_add_migration_factory_tables`,
  applied by the one-shot `migration-init` compose service before API/worker
  start.
- **Security**: tenant scoping at query layer (TENANCY_MODEL.md); finance
  invariants at app + DB level (idempotency keys, unique constraints).

## 2. Redis 7 — rate limiting + cache

- **Config**: `REDIS_URL` (optional — absent in pure unit tests).
- **Uses**:
  - `app/core/security/rate_limiter.py` — per-IP login rate limiting and
    protected-endpoint limits; `RATE_LIMIT_FAIL_CLOSED` toggles
    Redis-outage policy (default fail-open + log).
  - `app/domains/jobs/scheduler.py` — daily / five-minute bucket keys for
    idempotent periodic enqueue across worker restarts/replicas.
  - Cache for plan/result caching where configured (simulation/optimization
    design docs).
- **Not used** for durable queues — the outbox/jobs tables are the durable
  mechanism.

## 3. Razorpay — payments (optional, India)

- **Files**: `app/domains/billing/razorpay.py` (`RazorpayProvider`),
  `app/domains/billing/payments.py` (`register_provider`).
- **Config**: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
  `RAZORPAY_WEBHOOK_SECRET` (must differ from key secret; falls back to key
  secret when unset).
- **Activation**: provider registered at startup only when both key id and
  secret are set.
- **Security**: HMAC-SHA256 webhook verification over raw body, constant-time
  compare; `webhook_events` idempotency ledger `(provider_name,
  sha256(raw_body))` UNIQUE; timestamp freshness (300 s); tenant resolved
  from server-set notes; amount fail-closed. (SECURITY_MODEL §5.)

## 4. SendGrid — transactional email (optional)

- **Files**: `app/domains/notifications/email_service.py` (HTML render +
  send), `app/domains/notifications/channels.py` (`EmailChannel`).
- **Config**: `SENDGRID_API_KEY`, `EMAIL_FROM_ADDRESS` (default
  `noreply@sdmas.app`), `EMAIL_FROM_NAME`.
- **Fallback**: if no API key is configured, email delivery degrades to a
  logged no-op — the in-app notification path is unaffected.

## 5. Document / file storage — local or S3-compatible

- **Config**: `STORAGE_BACKEND` (`local` default | `s3`), `STORAGE_ROOT`
  (default `storage/documents`), plus S3: `S3_ENDPOINT`,
  `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`,
  `S3_REGION`, `S3_USE_SSL`.
- **Security**: uploads validated for size/extension/content-MIME; UUID
  storage keys; signed document URLs via `DOCUMENT_STORAGE_SECRET`.
- **Deployment**: `/app/storage` shared volume between API and worker
  (`storage_data`) so the worker reads migration uploads and document blobs
  written by the API.

## 6. Vault — secrets backend (optional)

- **File**: `app/core/secrets.py`.
- Production secrets may come from env, `infrastructure/secrets/` (chmod
  600), platform injection, or a Vault backend; pydantic-settings remains
  the primary mechanism.

## 7. nginx — reverse proxy / SPA server

- **Dev** (`infrastructure/nginx/dev.conf`): serves the built SPA; proxies
  `/api/`, `/auth/`, `/docs`, `/openapi.json`, `/health`, `/ready`;
  content-negotiates shared SPA/API prefixes (`/students`, `/attendance`,
  `/migration`, `/admin`) by `Accept` header; no SSL (zero-touch demo).
- **Prod** (`infrastructure/nginx/nginx.conf`, `default.conf`): TLS
  termination, security headers, rate limits (deployed via the web image
  and/or the nginx service).
- **Contract**: the Vite dev proxy (`apps/web/vite.config.ts`) is the
  canonical API-prefix contract; every prefix there must be routed in
  nginx dev.conf (documented in the config header).

## 8. SQLite WASM — frontend universal search (browser-local)

- `@sqlite.org/sqlite-wasm` in `apps/web` powers the universal search modal:
  an FTS5 index built locally in the browser from API data, synced in the
  background (`use-universal-search`, `app/domains/search`). No backend
  search infrastructure required for this surface.

## 9. Monitoring / observability (optional profiles)

- `infrastructure/monitoring/`: Prometheus + Grafana (provisioned datasource/
  alerts) and OpenTelemetry Collector (`otel-collector.yml`).
- API exposes `/health`, `/ready`, `/metrics`; `app/core/observability/`
  instruments FastAPI + SQLAlchemy, JSON logging, request/correlation IDs.
- **Not part of the zero-touch demo stack** (kept behind a separate
  profile/compose file so first-run stays light).

## 10. External integration security rules (AGENTS.md §13)

- Webhooks authenticated by signature, never by user session.
- Payment tenant association from provider payload, never client headers.
- Rate limiting keyed on the real client IP (trusted-proxy allowlist).
- No production secrets in code or `.env`; CI guards `.env` tracking and
  hardcoded credential patterns.
