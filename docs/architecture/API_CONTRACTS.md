# API Contracts — SDMAS v2

Status: **CURRENT** · Last verified: 2026-08-17 · Owner: platform team

This document is the canonical API contract policy for SDMAS v2. It describes
the *actual* contract between the FastAPI backend, the React frontend API
clients (`apps/web/src/api/`), and the routing layers (Vite dev proxy, nginx),
as verified against the repository. Anything that disagrees with this document
is a defect (see the guard test below).

---

## 1. Routing contract (how the frontend reaches the API)

The frontend calls the backend with **two path families**:

| Family | Example | Backend routers |
|---|---|---|
| `/api/...` (modern, majority) | `/api/students`, `/api/fees/payments`, `/api/cases` | `analytics`, `academic`, `admission`, `academic_ops`, `attendance_intelligence`, `audit`, `cases`, `command_center`, `communications`, `data_quality`, `documents`, `fees`, `institution`, `leave`, `notifications`, `parent`, `report_builder`, `report_cards`, `reports`, `risk`, `school_finance`, `search`, `student_portal`, `timeline`, `workflow` |
| Bare legacy prefixes | `/auth/login`, `/students/{id}`, `/attendance/daily`, `/migration/projects`, `/admin/users`, `/classes/{id}/360`, `/teachers/{id}/360` | `auth`, `student`, `attendance`, `migration`, `admin_router`, `class_360`, `teacher_360`, `student_360`, `billing`, `jobs` |

**Every bare prefix must be routed to the API by ALL of:**

1. `apps/web/vite.config.ts` — the dev proxy (`server.proxy`)
2. `infrastructure/nginx/dev.conf` — the zero-touch dev stack
3. `infrastructure/nginx/nginx.conf` — the production stack

The nginx configs use **content negotiation** for prefixes that are *both* SPA
routes and API prefixes (`/students`, `/teachers`, `/attendance`, `/migration`,
`/admin`): a browser navigation sends `Accept: text/html` and gets the app
shell; `fetch()` sends `*/*` or `application/json` and is proxied to the API.
`/classes` is API-only (the SPA class routes live under `/academic/classes`).

### Guard test

`apps/web/src/__tests__/api-contract.test.ts` statically scans every API client
file for path prefixes and asserts each bare prefix is covered by the Vite
proxy **and** both nginx configs. A new bare API call with no proxy entry
**fails CI** instead of silently returning `index.html` at runtime.

> **Verified defect fixed 2026-08-17:** Class 360 (`/classes/{id}/360`),
> Teacher 360 (`/teachers/{id}/360`) and the admin user-management pages
> (`/admin/users`) returned the SPA shell instead of JSON because `/classes`,
> `/teachers` (and `/admin` in the Vite proxy) were missing from the routing
> configs. Fixed in `vite.config.ts`, `dev.conf`, `nginx.conf`; the guard test
> now prevents recurrence.

---

## 2. Authentication & session contract

| Aspect | Contract |
|---|---|
| Login | `POST /auth/login` `{login, password}` → `{access_token, refresh_token, expires_in}` (public, no auth) |
| Access token | `Authorization: Bearer <access_token>` on every authenticated request |
| Refresh | `POST /auth/refresh` with body `{refresh_token}` → new token pair. Body-based (never in the URL) |
| Logout | `POST /auth/logout` with bearer token → revokes all refresh tokens (204) |
| Me | `GET /auth/me` → `UserResponse` incl. `roles` and `campus_id` (tenant context for the UI) |
| Registration | `POST /auth/register` (public) |
| 401 | `{"detail": "..."}` with `WWW-Authenticate: Bearer` header |
| 403 | `{"detail": "..."}` — authenticated but not authorized |

Token/refresh flow is implemented in `apps/web/src/api/client/http-client.ts`
(single in-flight refresh promise; 401 → refresh → retry once).

---

## 3. Error envelope

All errors are JSON with a **`detail` field**. Two shapes, both handled by the
frontend `parseApiError` in `http-client.ts`:

| Shape | Produced by | Frontend handling |
|---|---|---|
| `{"detail": "human message"}` | Domain exception handlers (`app/core/error_handlers.py`) | `ApiError.detail` |
| `{"detail": [{loc, msg, type, input?, ctx?}]}` | FastAPI/Pydantic 422 validation | `ApiError.validation_errors`, `detail` = first `msg` |

Domain exceptions → status mapping (`app/core/exceptions.py` +
`app/core/error_handlers.py`):

| Exception | HTTP |
|---|---|
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `ValidationError` | 422 |
| `AuthenticationError` | 401 (+ `WWW-Authenticate`) |
| `AuthorizationError` | 403 |
| `PaymentRequiredError` | 402 |
| `FileValidationError` | 400 |

Frontend `ApiError` type (`apps/web/src/api/generated/types.ts`):
`{status, detail?, validation_errors?}`.

---

## 4. Pagination

Canonical page shape (both sides, verified identical):

```ts
interface Page<T> { items: T[]; total: number; page: number; size: number; pages: number }
```

- Backend: `app/core/pagination.py` — `Page.create()`; `pages = ceil(total/size)`.
- Query params: `page` (1-based, default 1) and `size` (default 20).
- Frontend: `Page<T>` in `generated/types.ts` + `report-builder-api.ts` — identical shape.

List endpoints SHOULD return `Page<T>`; endpoints returning raw arrays are
documented exceptions (e.g. `GET /api/fees/payments/by-date-range`).

---

## 5. Request & correlation IDs

- Every response carries `X-Request-ID` and `X-Correlation-ID`
  (`app/core/observability/middleware.py`).
- Incoming `X-Request-ID` / `X-Correlation-ID` are honored; otherwise a fresh
  ID is generated.
- The correlation ID propagates into domain events and audit records
  (`audit_logs.request_id` / `correlation_id`), so a single user action is
  traceable end-to-end (HTTP → service → outbox → worker → audit).
- Clients are not required to send these headers, but SHOULD when retrying
  (idempotent retries reuse the same correlation ID).

---

## 6. Tenant context

- Tenant identity is carried in the JWT `campus_id` claim, decoded by
  `TenantContextMiddleware` (`app/multi_tenant/middleware.py`) into
  `request.state.tenant`.
- Handlers use the `get_current_tenant` dependency
  (`app/multi_tenant/dependencies.py`) and tenant-scoped repositories
  (`TenantScopedRepository`) — tenant scoping is enforced server-side, never
  trusted from the client (no client-supplied `tenant_id` query/body params).
- The UI derives its tenant from `GET /auth/me` → `campus_id`.
- There is **no API versioning** (`/v1`, etc.) today. See §8.

---

## 7. Response conventions

- Success JSON is plain payloads (no envelope); `204` for no-content DELETE/PATCH where used.
- CSV exports return `text/csv` blobs (`api.get<Blob>` or `fetchAuthed`).
- Date/timestamp fields are ISO-8601 strings.
- Money is integer **minor units** (paise/cents) — see `ADR-005`.

---

## 8. API versioning policy

**Current state: no versioning.** All routes are unversioned under `/api/...`
or bare prefixes. Decision: versioning will be introduced only when a breaking
contract change is required; the first such change must:

1. Introduce `/api/v1/...` while keeping the old routes (deprecation window).
2. Be documented in `docs/architecture/API_CONTRACTS.md` and `DEPLOYMENT.md`.
3. Update the routing contract (vite proxy + nginx) and the guard test.

---

## 9. Changing the contract (policy)

1. **New endpoint:** add the path to the frontend API client, ensure the Vite
   proxy + nginx cover any bare prefix (the guard test enforces this), and add
   contract coverage.
2. **Breaking change:** follow §8. Do not silently change response shapes that
   the generated types or existing pages consume.
3. **Error handling:** prefer the domain exceptions in §3 over raw
   `HTTPException` in routers.
4. **Pagination:** new list endpoints return `Page<T>` per §4.

---

## 10. Verification commands

```bash
# Guard test (routing contract, frontend side)
cd apps/web && npx vitest run src/__tests__/api-contract.test.ts

# HTTP client contract tests (auth refresh, error parsing)
cd apps/web && npx vitest run src/__tests__/http-client.test.ts

# Backend: confirm error handlers map exceptions to deliberate statuses
cd apps/api && uv run pytest tests/ -k "error or handler or 404 or 422" -q
```

---

## 11. Related documents

- `docs/architecture/DOMAIN_CONTRACTS.md` — domain boundaries and dependency direction
- `docs/architecture/SECURITY_MODEL.md` — auth/RBAC/audit mechanics
- `docs/architecture/TENANCY_MODEL.md` — tenant scoping
- `docs/architecture/EVENT_MODEL.md` — events/outbox/jobs correlation
- `docs/architecture/DEPLOYMENT_MODEL.md` — compose/nginx/zero-touch stack
