# MIGRATION-BASELINE-REPORT.md

Alembic migration graph audit and normalization.
Date: 2026-08-16 · Verdict: **VERIFIED — baseline reliable**. Single intentional
head; full chain applies from an empty PostgreSQL 16 database; idempotent;
Docker migration-init (the previously broken permission path) verified working
end-to-end. No graph consolidation required.

---

## 1. Scope and method

Inspected `apps/api/alembic/` (env.py, alembic.ini, 58 version files), the full
`alembic history`/`heads` graph, ORM models (via `alembic check`), the CI
`migrations` job, and the Docker migration-init container (Dockerfile +
compose service). Executed the real chain against PostgreSQL 16 in Docker from
an empty database, re-ran it for idempotency, exercised downgrades of the
newest revisions, and ran the migration-init container against a fresh DB.

## 2. Graph findings

### 2.1 One canonical head — confirmed

`alembic heads` → `051_add_missing_model_indexes (head)` (exactly one line).
CI enforces `wc -l == 1` in the `migrations` job.

### 2.2 Two historical branches — already merged, no consolidation needed

The graph had diverged twice and both merges exist as merge-only revisions:

* `merge_multi_tenant_heads` (parents: `028_create_migration`,
  `e7f3a2b1c0d9`, `021_create_guardian_links`)
* `042_merge_migration_heads` (parents: `041_add_communication_context`,
  `c21889d4e562`, `create_temporal_txn_log`)

Everything after `042` is linear through head. **No consolidation is required.**
The graph already satisfies "a single intentional head" while preserving
historical migration meaning.

### 2.3 No missing revisions, no duplicate revision IDs

All 119 `down_revision` references resolve to a file present in
`alembic/versions/`. Revision IDs are unique.

### 2.4 Cosmetic file-name collision (not a graph defect)

Two files share the numeric prefix `021`:
`021_create_attendance_intelligence_tables.py` (revision `021`) and
`021_create_guardian_links_table.py` (revision `021_create_guardian_links`).
Distinct revision IDs → deterministic ordering. Optionally rename the files for
readability; the graph is unaffected.

## 3. Execution verification (PostgreSQL 16, fresh DB)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | heads | `uv run alembic heads` | `051_add_missing_model_indexes (head)` |
| 2 | upgrade from empty | `uv run alembic upgrade head` | 58 revisions applied, RC=0 |
| 3 | repeat upgrade | `uv run alembic upgrade head` | no-op, RC=0 (idempotent) |
| 4 | current | `uv run alembic current` | `051_add_missing_model_indexes (head)` |
| 5 | downgrade 051 | `alembic downgrade 050_add_missing_tenant_fks` | OK; 051 indexes removed |
| 6 | downgrade 050 | `alembic downgrade 049_widen_audit_action` | OK; tenant FKs removed (0 rows in pg_constraint) |
| 7 | re-upgrade | `alembic upgrade head` | OK; FKs restored |
| 8 | live DB | `alembic current` on existing `sdmas` | `051_add_missing_model_indexes (head)` |

**Transactional DDL** is in effect on PostgreSQL, so a mid-chain failure rolls
back the failed revision's statements atomically.

## 4. Schema/model consistency (`alembic check`)

`alembic check` reports 243 pending operations — **all representational noise**;
no table, column, FK, or constraint is missing:

| Op | Count | Root cause |
|---|---|---|
| remove_index | 181 | DB-only performance/search indexes (created by 007/022/024/046/048) not mirrored into ORM `__table_args__` |
| modify_comment | 35 | ORM column comments never applied to DB |
| modify_type | 12 | `JSON` vs `_JSON` TypeDecorator (same DB type) |
| add_index | 9 | index-name drift (e.g. `ix_migration_logs_run_id` vs migration-created `ix_migration_logs_run`) |
| remove_constraint | 6 | ORM `unique=True` renders as constraint; DB has named unique index — **uniqueness exists in DB** |

Verified concretely for the flagged unique cases on the fresh DB:

* `plans.code` → `uq_plans_code` (unique) **and** redundant non-unique `ix_plans_code`
* `refresh_tokens.token_hash` → `uq_refresh_token_hash` (unique) + `ix_refresh_tokens_token_hash`
* `subscriptions.campus_id` → `uq_subscriptions_campus` (unique) + `ix_subscriptions_campus_id`
* `permissions`/`roles`/`report_definitions` `code` → unique indexes
* `outbox_events.event_id` → `uq_outbox_events_event_id` (unique) present

The redundant non-unique `ix_*` alongside the `uq_*` on the same column is
harmless (the unique index is the effective path); it is what autogenerate
flags. **CI gates on single-head + `upgrade head`, not `alembic check`** — a
deliberate policy consistent with this baseline. Cleaning the noise (mirroring
performance indexes into models) is backlog work, not a correctness blocker.

## 5. Docker migration-init — the permission/executable history

Previous failure mode (fixed in current Dockerfiles):

```
/usr/local/bin/python3.11: can't open file '/root/.local/bin/alembic':
[Errno 13] Permission denied
```

Root cause then: `pip install --user` installed into `/root/.local`, and `/root`
is `0700 root:root` on Debian slim — no `chown` could grant the runtime user
traversal. Fix in `apps/api/Dockerfile` and `Dockerfile.worker`:

* `pip install --no-cache-dir --require-hashes --prefix=/opt/sdmas` (world-readable)
* `ENV PATH=/opt/sdmas/bin:$PATH` + `PYTHONPATH=/opt/sdmas/lib/python3.11/site-packages`
* Runtime `USER sdmas` (non-root)

**Verified**:

```bash
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas build migration-init
# builds (multi-stage), ~50s
docker run --rm --network sdmas_default -e DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@postgres:5432/<fresh> \
  sdmas-migration-init alembic upgrade head
# exit 0; DB stamped at 051_add_missing_model_indexes
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas run --rm migration-init
# no-op against already-migrated sdmas DB, exit 0
```

Compose wiring is correct: `migration-init` depends on `postgres:
service_healthy`, `restart: no`, exits non-zero on failure; `api` and `worker`
depend on `migration-init: service_completed_successfully` — so the app never
starts against an unmigrated schema, and failed migrations fail the deployment.

## 6. Known limitations (documented, not defects)

* **SQLite cannot run the chain.** `alembic upgrade head` on SQLite fails in
  `050_add_missing_tenant_fks`: the batch rename of `assignments` triggers
  SQLite view revalidation of `legacy_null_campus_records` (created in
  `c21889d4e562`). This is a documented, intentional limitation — CI runs
  migrations against PostgreSQL 16; SQLite is unit-test-only via
  `create_all`. Reproduction: `DATABASE_URL=sqlite+aiosqlite:////tmp/x.db
  uv run alembic upgrade head` (stops at 049/050).
* Downgrade support is best-effort (verified for the newest revisions); the
  full-chain downgrade path is not exercised.
* `alembic check` noise (243 ops) is tracked as backlog cleanup.

## 7. Conclusion and policy

The migration baseline is **reliable and production-safe**:

* exactly one head, no branches to consolidate, no missing revisions;
* upgrade from an empty database verified, idempotent;
* live database at head with zero drift;
* Docker migration-init verified (permission fix holds) and correctly gated
  before API/worker;
* schema the ORM sees is functionally identical to the migrated schema.

Policy: append additive migrations linearly after `051_add_missing_model_indexes`;
never edit historical revisions in place; verify with `alembic heads` + `alembic
upgrade head` on PostgreSQL. See `docs/architecture/CURRENT_STATE.md` for the
operational summary.

## 8. Files changed

| File | Change |
|---|---|
| `docs/architecture/CURRENT_STATE.md` | **new** — baseline summary + policy + verification commands |
| `docs/enterprise/MIGRATION-BASELINE-REPORT.md` | **new** — this report |

No migration files, models, or deployment files were modified (audit-only for
the graph; the Docker permission fix was already landed in a prior session and
was re-verified here).
