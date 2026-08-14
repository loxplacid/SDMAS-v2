# Multi-Tenant Security Audit — SDMAS-v2

**Date:** 2026-08-12
**Attacker model:** A valid admin/teacher user of **Tenant A (Apex Global School, campus 2)** attempting horizontal + vertical escalation against **Tenant B (St. Jude, campus 3)** and **Tenant C (Metro Institute, campus 4)**.
**Method:** Static review of every domain's service/repository/router, then live HTTP proof against the running 3-tenant stack, then fix + regression test + re-proof.

---

## 1. Executive summary

| Area | Result |
|---|---|
| Core architecture | Sound: `TenantScopedRepository.scoped_query`, `require_tenant_context`, `assert_tenant_scope` (16 call sites in school-finance router alone), `assert_tenant_scope_or_owner` for legacy NULL-campus rows |
| Domains verified clean (app + DB layer) | Students, guardians, academics, classes, attendance, fees, payments, ledger, reports, report-cards, documents, cases, timeline, billing, parent portal, risk, jobs — all post-fetch tenant assertions or campus-scoped queries verified |
| Vulnerabilities found | **4 cross-tenant IDOR/PII leaks (P1) + 1 pre-existing API-breaking bug (P1) + 2 P2** |
| All fixed + regression tested | Yes — **446 tests pass**, live re-proof **ALL CHECKS PASS** |

---

## 2. Confirmed vulnerabilities (proven live, then fixed)

### P1-1 — Migration runs/logs/report/rollback unscoped (cross-tenant read + destructive rollback)

**Reproduction (live):** Apex admin `GET /migration/runs/3`, `/runs/3/logs`, `/runs/3/report` → **200** with St. Jude's run data (source, counts, error details). `POST /runs/3/rollback/plan` also reached another tenant's run.

**Root cause:** `MigrationRunRepository.get_by_id` / `list_runs` and `MigrationLogRepository.list_by_run` had no `campus_id` filter; the `/migration/runs*` router endpoints required only `require_role("admin")` with **no tenant context**. `MigrationRun.campus_id` existed in the schema but was never enforced on reads — and the legacy `/migration/run` + `/migration/import` endpoints created runs without a campus at all.

**Fix:**
- `MigrationRunRepository.get_by_id(run_id, campus_id=None)` / `list_runs(..., campus_id=None)` now pin by campus.
- Router: all `/runs*`, `/logs`, `/report`, `/report/text`, `/rollback/plan`, `/rollback` endpoints take `get_school_context` and pass `tenant.campus_id`; a foreign run resolves to **404**.
- `MigrationEngine.run` / `run_bulk` accept `campus_id` and set it on created runs; legacy import endpoints pass the tenant's campus (fixes runs created with NULL campus).
- `RollbackService.plan_rollback` / `execute_rollback` accept `campus_id` and refuse foreign runs (defense in depth behind the router check).
- Fixed the `run_migration` endpoint's hardcoded `get_by_id(1)` (always returned run #1).

**Regression tests (4):** run get/list campus-scoped, rollback cross-campus → `ValueError`, engine pins campus.

### P1-2 — Message templates unscoped (cross-tenant read/write/delete/render)

**Reproduction (live):** Apex admin `POST /api/communications/templates/render` with St. Jude's template id → **200** rendered the other campus's template. `GET/PATCH/DELETE /templates/{id}` used unscoped `session.get(MessageTemplate, id)`.

**Root cause:** `MessageTemplateService.get/update/delete/render/list` had no campus filter; the router endpoints had no `require_tenant_context`.

**Fix:** All template service methods take `campus_id`; router endpoints require tenant context. Read scope = `campus_id == X OR campus_id IS NULL` (global templates remain visible); **write scope excludes global templates** so a tenant admin cannot mutate or delete a platform/global template other tenants rely on.

**Regression tests (4):** template get/update/delete/render/list campus-scoped; foreign campus → `NotFoundError`; denied writes leave rows untouched.

### P1-3 — Recipient resolution leaked cross-tenant PII (names/emails)

**Reproduction (live):** Apex admin `POST /api/communications/resolve-recipients` with St. Jude student id 299 → **200** with `{"name": "Zainab Abdullahi", "email": "zainab.abdullahi@stjude.demo"}`.

**Root cause:** `RecipientResolver.resolve_with_details` loaded `Student`/`User` rows by arbitrary id with no campus filter.

**Fix:** `resolve`/`resolve_with_details` take `campus_id`; student lookups filter `Student.campus_id`, user lookups filter `User.campus_id`, and class/section expansion joins through `Class.campus_id`/`Section.campus_id`. **Explicit cross-campus recipients are now rejected outright** (422 `ValidationError`) before any PII loads — so the existence of another campus's student cannot even be probed. `send_message` inherits this (cross-campus users can no longer be messaged or notified).

**Regression tests (2):** own-campus resolve returns full PII; foreign-campus recipient id → `ValidationError`.

### P1-4 — Message get/update/delete unscoped (cross-tenant read/write of messages)

**Reproduction (live):** Apex admin `GET/PATCH /api/communications/messages/{id}` reached St. Jude's messages (previously masked by the P1-5 serialization 500; the unscoped by-id lookup was confirmed statically).

**Root cause:** `CommunicationService.get_message(msg_id, user)` selected by id only — the `user` argument was ignored.

**Fix:** `get_message` now pins `(id, campus_id)`; staff/teachers additionally pin `sender_id` (own messages only), while admin/principal may manage any message **within their campus** (preserves retrying a failed broadcast sent by staff). `update/delete/retry/send-now` inherit via `get_message`. `list_messages` also gained a campus filter.

**Regression tests (1):** owner sees own message; other user's message → `NotFoundError`.

### P1-5 — Response schemas missing `from_attributes=True` (entire messaging API 500s)

**Reproduction (live):** Same-tenant `GET /api/communications/messages/{id}` → **500** even for the owner; `POST /send` → 500.

**Root cause:** `MessageResponse`, `MessageTemplateResponse`, `MessageRecipientResponse`, `MessageAttachmentResponse`, `MessageScheduleResponse`, `InboxItemResponse` were `BaseModel` without `model_config = ConfigDict(from_attributes=True)`, so `model_validate(orm_obj)` raised `ValidationError`. Tests bypassed it by calling services directly, so the suite stayed green while every messaging endpoint was broken.

**Fix:** Added `from_attributes=True` to the six response models. (This also means the previously-hidden P1-4 IDOR is now fully reachable — and closed by the P1-4 fix.)

### P2 — `GET /api/communications/schedules/pending` returned all tenants' schedules

**Fix:** Joins `CommunicationMessage` and filters by `tenant.campus_id`.

---

## 3. What was verified clean (not just claimed)

- **App layer:** every router we reviewed for the flagged domains (reports, report-cards, documents, academic_ops, cases, timeline, billing, parent, jobs, risk, analytics, communications context) applies `assert_tenant_scope` post-fetch or passes `tenant.campus_id` into service queries. `CaseService.get_case_detail` filters `Case.campus_id`. `TransactionLogService.get` is unscoped but **every** router call site applies `assert_tenant_scope` (16 call sites).
- **DB layer:** live distribution confirms data is stored per campus (`students`: campus 2 = 288, campus 3 = 160, campus 4 = 112). Tenant keys exist on every major table and are enforced at query time.
- **Existing suites:** `tests/test_tenant_isolation.py` (9 tests), `tests/test_multi_tenant/` (74 tests) cover the guard/repository/legacy-NULL mechanics and were re-run green.

---

## 4. Files changed

| File | Change |
|---|---|
| `app/domains/migration/repository.py` | Campus-pinned `get_by_id`/`list_runs` |
| `app/domains/migration/router.py` | Tenant context on runs/logs/report/rollback/import endpoints; fixed `get_by_id(1)` bug |
| `app/domains/migration/engine.py` | `campus_id` threaded through `run`/`run_bulk`/`rollback` |
| `app/domains/migration/rollback.py` | `campus_id` on plan/execute rollback |
| `app/domains/communications/service.py` | Template/recipient/message campus scoping + global-template write guard |
| `app/domains/communications/router.py` | Tenant context on templates/resolve-recipients/schedules; import cleanup |
| `app/domains/communications/schemas.py` | `from_attributes=True` on 6 response models |
| `tests/test_migration_workspace.py` | +4 regression tests |
| `tests/test_communications_context.py` | +6 regression tests |

## 5. Tests executed / results

| Suite | Result |
|---|---|
| communications + notifications + migration + multi-tenant + permissions + fees + finance security | **446 passed** |
| `test_communications_context.py` | 23 passed |
| `test_migration_workspace.py` + `test_migration_step2.py` + multi-tenant + tenant isolation | 156 passed |
| `ruff check` (changed files, E9/F821/F822/I001) | Clean |
| `alembic heads` | Single head `047_scope_idem_keys` |
| Live re-proof (final) | **ALL CHECKS PASS** — 8/8 cross-tenant paths blocked, 3/3 same-tenant paths OK |

## 6. Known limitations / notes

- `campus_id` remains nullable on some tables for legacy rows; NULL-campus rows are visible only to the platform scope (`assert_tenant_scope_or_owner` handles legacy ownership).
- Pre-existing lint debt (unused imports, long lines) remains in `communications/service.py` and `school_finance/service.py` — unrelated to this audit.
- The 5 legacy students with NULL `campus_id` in the live DB predate this audit; the enterprise demo seeder does not produce them.
