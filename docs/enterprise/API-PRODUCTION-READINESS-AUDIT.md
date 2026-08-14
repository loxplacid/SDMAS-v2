# FastAPI Production-Readiness Audit — SDMAS-v2

**Date:** 2026-08-12
**Scope:** Complete API surface, endpoint hardening, tenant isolation, idempotency, audit.
**Method:** Static route enumeration + OpenAPI comparison + frontend usage comparison + live behavioral attack matrix against a running stack.

---

## 1. Executive summary

| Area | Result |
|---|---|
| Route enumeration | ~full OpenAPI surface reviewed (protected/public classification) |
| Frontend ↔ backend route comparison | **CLEAN** — every frontend API call resolves to a real backend route (two "missing" items were React Router paths, not API calls) |
| Behavioral attack matrix (live) | **22/22 PASS** |
| Cross-tenant idempotency (financial) | **P1 found → FIXED and verified live** |
| Migration chain | Single head `047_scope_idem_keys`; fresh SQLite + fresh PostgreSQL chains verified |
| Regression | 181 finance tests, 302 tenancy/permissions tests, 23 school-finance tests — all pass |

---

## 2. What was inspected

1. **Route enumeration** — full OpenAPI path/method list exported from the live app; endpoints classified as public (login/register/webhook) vs protected (dependency-composed auth).
2. **Frontend usage comparison** — static scan of every `api/...` string in `apps/web/src` against the backend OpenAPI; each prefix resolved to real routes (e.g. `/api/communications`, `/api/parent`, `/api/report-builder`, `/api/school-finance`, `/api/student/portal`, `/admin/audit-logs` → `/api/admin/audit-logs`).
3. **Behavioral attack matrix** (live HTTP, real demo users) — unauthenticated access, wrong tenant (cross-campus student/fee/audit/migration reads), wrong role, ID substitution, deleted resources, malformed input, duplicate requests, concurrent/idempotent payment replay.

### Attack matrix results (22/22 PASS)

- Unauthenticated requests to protected resources → 401.
- Tenant A token reading Tenant B student → 403/404 (tenant-scoped repository + post-fetch `assert_tenant_scope`).
- Tenant A token reading Tenant B fee/transaction/audit → denied.
- Parent token reading another parent's children → denied.
- Teacher token performing admin actions → 403.
- Malformed payloads → structured 422 (validation), never 500.
- Login rate limiting active (5 req / 60 s → 429) — verified empirically.
- Duplicate payment request with same key + same tenant → single ledger effect (idempotent replay).
- Cross-tenant payment with same key → **was** 409 (P1), **now** independent success (201) after fix.

---

## 3. P1 — Cross-tenant financial idempotency collision (FIXED)

### Root cause

Two DB unique constraints were **global across tenants**:

- `payments.idempotency_key` (`uq_payment_idempotency_key`)
- `transaction_logs.idempotency_key` (`uq_transaction_idempotency`, plus a second overlapping inline global unique `transaction_logs_idempotency_key_key`)

Since `idempotency_key` is **client-supplied** on `POST /api/fees/payments`, Tenant B's legitimate payment using the same key as an earlier Tenant A payment hit a spurious `IntegrityError` → 409, even though the two payments are entirely unrelated.

Additionally, `TransactionLogService.find_by_idempotency_key` was an **unscoped raw select** (no campus filter), so a cross-tenant lookup could resolve another tenant's ledger row — an IDOR on the idempotency lookup path.

**Live proof before fix:** Apex records payment with key `audit-cross-tenant-collision-key-v1` → 201; St. Jude's independent payment with the same key → **409**.

### Fix (migration 047 + model/service changes)

1. **`alembic/versions/047_scope_idempotency_keys_by_campus.py`** (new)
   - Scopes both unique constraints to `(campus_id, idempotency_key)`.
   - `transaction_logs`: collapses the two overlapping global uniques into one campus-scoped unique.
   - SQLite-safe: drops/recreates the `legacy_null_campus_records` view around the batch table rebuilds; tolerant constraint-name resolution via SQLAlchemy inspector (PG names vs SQLite auto-indexes).
   - `downgrade()` restores the original global constraints (verified round-trip: up 047 → down 046 → up 047 on fresh SQLite).
2. **`app/domains/fees/models.py`** — `Payment.idempotency_key` no longer `unique=True`; composite `UniqueConstraint("campus_id", "idempotency_key", name="uq_payment_idempotency_key")` added to `__table_args__`.
3. **`app/domains/school_finance/models.py`** — same treatment for `TransactionLog`.
4. **`app/domains/school_finance/service.py`** — `find_by_idempotency_key` now takes and filters on `campus_id`; the caller (`create_transaction`) passes it. No remaining unscoped idempotency lookups (single production call site verified).

### Verification

- Fresh SQLite `alembic upgrade head` → passes; idempotent second run passes.
- Fresh PostgreSQL chain (scratch DB) → passes; composite constraints present.
- Live PostgreSQL upgraded to `047_scope_idem_keys` (single head).
- API/worker restarted with new code.
- **Cross-tenant collision re-test:** Apex 201, St. Jude 201 with the same key — fixed.
- **Same-tenant replay re-test:** duplicate request with same key returns the original payment (no double ledger effect) — dedup intact.
- `get(log_id)` (transaction detail) is unscoped at the service layer but **every router call site applies `assert_tenant_scope` post-fetch** (16 assertions in the router) — verified at `GET /transactions/{log_id}`.

### Regression tests added

`tests/test_finance_security/test_school_finance.py`:

- `test_payment_idempotency_keys_are_campus_scoped` — two campuses may use the same key; same-campus duplicate is rejected by the composite DB constraint (savepoint-confined `IntegrityError`).
- `test_transaction_log_idempotency_scoped_by_campus` — `find_by_idempotency_key` cannot resolve another campus's row under the same key.

---

## 4. Other findings

| Severity | Finding | Status |
|---|---|---|
| OBSERVATION | `campus_id` is nullable on `payments`/`transaction_logs`; PG treats NULLs as distinct in unique constraints, so two NULL-campus rows with the same key would not collide | All live rows have `campus_id` populated (verified by count). Left nullable for backward compatibility; noted as a documented limitation. |
| OBSERVATION | Pre-existing lint debt in `school_finance/service.py` (unused imports/vars, long lines) predates this audit | Not part of this fix; flagged for cleanup. |
| INFO | Login rate limit (5/60 s) is aggressive for demo automation | Verified working; documented demo limitation. |

---

## 5. Files changed (this audit)

| File | Change |
|---|---|
| `apps/api/alembic/versions/047_scope_idempotency_keys_by_campus.py` | NEW — campus-scoped idempotency unique constraints |
| `apps/api/app/domains/fees/models.py` | Composite unique on `(campus_id, idempotency_key)` |
| `apps/api/app/domains/school_finance/models.py` | Composite unique on `(campus_id, idempotency_key)` |
| `apps/api/app/domains/school_finance/service.py` | Tenant-scoped `find_by_idempotency_key` |
| `apps/api/tests/test_finance_security/test_school_finance.py` | 2 regression tests + lint cleanup |

## 6. Tests executed / results

| Suite | Result |
|---|---|
| `tests/test_fees` + `tests/test_finance_security` | **181 passed** |
| `tests/test_finance_security/test_school_finance.py` + `test_payments.py` | **23 passed** |
| `tests/test_fees test_finance_security test_multi_tenant test_tenant_isolation.py test_permissions.py` | **302 passed** |
| `ruff check` (new files + touched lines) | Clean (remaining service.py errors pre-existing) |
| `alembic heads` | Single head `047_scope_idem_keys` |
| Migration round-trip (fresh SQLite up→down→up) | Passed |

## 7. Remaining work

- Optional follow-up: enforce `NOT NULL` on `payments.campus_id` / `transaction_logs.campus_id` once legacy NULL rows are confirmed absent in production.
- Clean up pre-existing lint debt in `school_finance/service.py` (separate from this audit).
