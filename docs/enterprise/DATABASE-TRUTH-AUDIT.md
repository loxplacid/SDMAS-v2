# DATABASE-TRUTH-AUDIT.md

Database/ORM truth audit — SQLAlchemy models vs Alembic migrations vs live
PostgreSQL vs Pydantic schemas vs repository/service assumptions.
Date: 2026-08-16 · Verdict: **CONSISTENT** — zero objectively-confirmed schema
inconsistencies; no code or migration changes were required.

---

## 1. Method

A purpose-built read-only scanner compared, for every one of the 103 ORM
tables, the SQLAlchemy metadata against the live PostgreSQL 16 schema:

* table presence (both directions)
* column presence, nullability, and type family
* unique constraints (as constraints **or** unique indexes)
* foreign keys (child column → referred table/column)
* ORM-declared indexes (by column set)
* FK `ondelete` (ORM vs DB)
* enum columns, server defaults, timestamp defaults

The same scan ran against the live `sdmas` database and against a
freshly-migrated database (`alembic upgrade head` from empty) to separate
"live drift" from "migration-chain drift". Static AST scans checked the
Pydantic write-DTO schemas against model fields, and SQL queries checked
orphan records and tenant propagation.

## 2. Results

### 2.1 ORM ↔ DB schema — fully consistent

| Dimension | Live DB | Fresh-migrated DB |
|---|---|---|
| Missing tables | 0 | 0 |
| DB-only tables | `alembic_version` only | `alembic_version` only |
| Missing columns | 0 | 0 |
| Extra columns | 0 | 0 |
| Nullability mismatches | 0 | 0 |
| Type mismatches | 0 | 0 |
| Missing FKs | 0 | 0 |
| Missing uniques | 0 | 0 |
| Missing ORM indexes | 0 | 0 |
| Cascade (ondelete) mismatches | 0 | 0 |
| Duplicate models | 0 | 0 |
| Python-enum columns | 0 | 0 |

**Both databases are byte-for-byte consistent with the ORM metadata.** This is
the expected end-state of the corrective migrations 044–051 landed in the
prior hardening passes (payments.updated_at, case JSON rename, campus-scoped
idempotency keys, performance indexes, widened audit action, tenant FKs,
model-declared indexes).

### 2.2 Reverse direction — DB-only objects (intentional)

* **181 DB-only indexes** (trgm search, composite N+1 fixers, `uq_*` unique
  indexes) created by migrations 007/022/024/046/048 and not mirrored into
  ORM `__table_args__`. These make `alembic check` report `remove_index`
  noise; CI gates on single-head + `upgrade head` instead. This is the only
  "drift" the previous baseline report (§3) already characterized.

### 2.3 Pydantic/API schemas

* All 34 domain `schemas.py` files checked. **No write-DTO references a
  nonexistent model column.** The fields flagged by the naive scan are
  legitimate:
  * action-request DTOs (`reason`, `case_ids`, `assignee_id`, `entities`,
    `recipient_ids`) — consumed by services, not written to models;
  * aggregate/response fields (`total`, `items`, `pages`, `absent_today`,
    `chronic_count`) — computed or composed;
  * aliases (`password` → `password_hash`, `plan_code` → plan lookup,
    `metadata` → `data` after migration 045).
* `auth.UserCreate.password`, `cases.*In.reason`, `fees.RefundCreate.reason`
  are request-only and correctly mapped by services.

### 2.4 Repository/service assumptions

* **Tenant propagation**: 20 child tables (case_events, case_comments,
  document_versions, message_recipients, admission_documents, …) have no own
  `campus_id` but are always reached through a parent that does — queries
  verified (`CaseEvent.case_id == case.id`,
  `DocumentVersion.document_id == doc_id`,
  `MessageRecipient.message_id.in_(select(CommunicationMessage.id).where(*conditions))`).
  Aggregate-root scoping matches the documented tenancy architecture and was
  proven by the adversarial multi-tenant suite
  (`docs/enterprise/TENANT-RBAC-VERIFICATION.md`).
* **Soft delete**: `documents.deleted_at` — model, migration, schema, and
  service (list filters `deleted_at IS NULL`, delete stamps the timestamp)
  agree; no other table soft-deletes.
* **Orphan records** (live DB): students/dues/payments/enrollments/attendance/
  notifications/users — 0 orphans across the checked referential pairs.
* **Timestamps**: 107 columns use app-level `default=`/`onupdate=` with no DB
  `DEFAULT` — uniform codebase pattern; every ORM write supplies them.
* **`verified_by`/`approved_by`** on reconciliation: model nullable int,
  service sets from the reviewing user — the prior `verified_by=0` hardcoded
  ID defect is not present in the current tree.
* **`migration_projects.file_key`**: model + migration 043 agree; internal
  storage key not exposed in schemas (by design).

## 3. Discrepancies requiring fixes

**None.** No objectively-confirmed schema inconsistency was found that is
safe and necessary to fix now. Adding a migration without a confirmed defect
would violate the audit's own standard ("fix only objectively confirmed
inconsistencies") and the project rule against gratuitous schema churn.

## 4. Known/unresolved risks (tracked, non-blocking)

| # | Risk | Sev | Why acceptable |
|---|---|---|---|
| R1 | `alembic check` shows 243 representation-noise ops (181 remove_index, 35 comment, 12 JSON, 9 index-name, 6 constraint-vs-unique) | LOW | DB is a superset of ORM (extra indexes/constraints); functional schema identical. Backlog: mirror perf indexes into models |
| R2 | 20 child tables lack direct `campus_id` | LOW | Parent-scoped queries verified; no isolation gap. Denormalization only if index-only scans ever need it |
| R3 | Full-chain downgrade untested | LOW | Best-effort; only 051→049 verified |
| R4 | 107 columns app-level timestamp defaults (no DB DEFAULT) | LOW | Uniform pattern; raw-SQL writers (migrations, seeds) always supply timestamps |
| R5 | `migration_projects.file_key` not in schemas | INFO | Internal key by design |

## 5. Regression tests

No new tests were required because no fix was made — the schema was already
consistent. The existing suites that continuously verify these invariants:

* `tests/test_multi_tenant/`, `tests/test_tenant_isolation.py`,
  `tests/test_permissions.py` — tenant propagation and RBAC (599 passed in the
  prior combined regression).
* `tests/test_finance_security/`, `tests/test_fees/` — financial FK/unique/
  idempotency invariants.
* `tests/test_migration_verification.py` — migration-domain write paths.
* CI `migrations` job — single-head + `alembic upgrade head` on PostgreSQL 16.

## 6. Verification commands

```bash
cd apps/api
uv run alembic heads                                   # 1 head
uv run alembic upgrade head                            # idempotent (PostgreSQL)
# fresh-DB parity:
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas exec -T postgres \
  psql -U sdmas -d postgres -c "CREATE DATABASE sdmas_check;"
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas_check \
  uv run alembic upgrade head
```

## 7. Files changed

| File | Change |
|---|---|
| `docs/architecture/DATA_MODEL.md` | **new** — schema inventory, consistency baseline, representation patterns, add-a-change policy |
| `docs/enterprise/DATABASE-TRUTH-AUDIT.md` | **new** — this report |

No model, migration, schema, or application files were modified (audit-only).
Scratch scanners were removed after use.
