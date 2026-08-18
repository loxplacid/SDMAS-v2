# CURRENT STATE — Database Migration Baseline

Date: 2026-08-16 · Status: **BASELINE VERIFIED** (single Alembic head, full chain
applies from an empty PostgreSQL database, Docker migration-init verified)

---

## 1. Migration graph

* **Total migrations**: 67 files in `apps/api/alembic/versions/`
* **Canonical head**: `060_add_migration_factory_tables` — exactly **one** head
  (`alembic heads` returns one line; CI enforces this).
* **Branches**: two historical branches were already converged with merge-only
  revisions — the graph is **linear from head**, no consolidation needed:
  * `merge_multi_tenant_heads` — merged `028_create_migration`,
    `e7f3a2b1c0d9` (search tables), `021_create_guardian_links`.
  * `042_merge_migration_heads` — merged `041_add_communication_context`,
    `c21889d4e562` (legacy null-campus view), `create_temporal_txn_log`.
* **Revision integrity**: all 65 `down_revision` references resolve to a real
  migration file — **no missing revisions**, no duplicate revision IDs.
* **File-name vs revision-ID collisions** (cosmetic only, not graph defects):
  * `021_create_attendance_intelligence_tables.py` → revision `021`
  * `021_create_guardian_links_table.py` → revision `021_create_guardian_links`
  * The two `021_*` filenames are ambiguous but their revision IDs are distinct,
    so Alembic ordering is deterministic. Renaming files is optional polish;
    it would not change the graph.

## 2. Verified operations (PostgreSQL 16, empty database)

| Check | Command | Result |
|---|---|---|
| Single head | `uv run alembic heads` | `060_add_migration_factory_tables (head)` — exactly 1 |
| Upgrade from empty DB | `uv run alembic upgrade head` | **success**, all 67 revisions applied |
| Idempotent re-upgrade | `uv run alembic upgrade head` (again) | no-op, exit 0 |
| Current stamp | `uv run alembic current` | `060_add_migration_factory_tables (head)` |
| Downgrade 060→059 | `alembic downgrade 059_add_extension_tables` | success; migration-factory columns + `migration_snapshots` dropped |
| Downgrade 051→050 | `alembic downgrade 050_add_missing_tenant_fks` | success; 051 indexes dropped |
| Downgrade 050→049 | `alembic downgrade 049_widen_audit_action` | success; `fk_assignments_campus_id`, `fk_guardian_links_campus_id` dropped (count 0) |
| Upgrade back to head | `alembic upgrade head` | success; FKs re-created |
| Live `sdmas` DB state | `alembic current` on live DB | `060_add_migration_factory_tables (head)` — no drift |

The **transactional DDL** path is used on PostgreSQL (default); the entire chain
applies within transactions, so a mid-chain failure rolls back cleanly.

## 3. Schema/model consistency (`alembic check`)

`alembic check` reports **243 pending operations**, all of which are
**representational noise — no table, column, foreign key, or constraint is
actually missing**:

| Op | Count | Meaning |
|---|---|---|
| `remove_index` | 181 | DB has indexes the ORM metadata does not declare (performance/search indexes created by migrations 007/022/024/046/048 — e.g. `ix_students_trgm`) |
| `modify_comment` | 35 | column comments exist only in the ORM models, never applied to the DB |
| `modify_type` | 12 | `JSON` vs the `_JSON` TypeDecorator — same DB type, different Python wrapper |
| `add_index` | 9 | model-declared index name vs migration-created name (e.g. `ix_migration_logs_run_id` vs `ix_migration_logs_run`) |
| `remove_constraint` | 6 | DB has named unique **indexes** (`uq_plans_code`, `uq_refresh_token_hash`, …) where the ORM renders `unique=True` as a constraint — **the unique guarantees exist in the DB** |

Concretely verified on the fresh DB: `plans`, `refresh_tokens`, `subscriptions`
each carry both a redundant non-unique `ix_*` and the real unique `uq_*` index;
`permissions`/`roles`/`report_definitions` have unique `code` indexes; the
outbox `event_id` unique index exists (`uq_outbox_events_event_id`).

**Conclusion**: the schema the ORM reads is the schema the migrations produce —
functionally identical. The reported diff is entirely naming/decorator/comment
drift that would only matter if a developer ran `alembic revision --autogenerate`
blindly. **CI deliberately does not gate on `alembic check`** (it gates on
single-head + `upgrade head`), matching this baseline. If `alembic check` output
must be clean, the corrective work is to mirror performance indexes into the
models' `__table_args__` — a large mechanical change, tracked as a backlog item,
not a correctness blocker.

## 4. Docker migration-init (permission/executable history — RESOLVED)

The documented migration-init failure (`/usr/local/bin/python3.11: can't open
file '/root/.local/bin/alembic': Permission denied`) is **fixed in the current
Dockerfiles** (`apps/api/Dockerfile`, `apps/api/Dockerfile.worker`):

* pip installs with `--prefix=/opt/sdmas` instead of `--user` — `/root` is
  `0700 root:root` on Debian slim, so the previous layout was untraversable by
  the runtime user. `/opt/sdmas` is world-readable.
* `ENV PATH=/opt/sdmas/bin:$PATH` puts `alembic` on the non-root user's PATH.
* Runtime runs as `USER sdmas` (non-root) with `PYTHONPATH` set explicitly.

Verified end-to-end:

```bash
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas build migration-init   # builds
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas run --rm migration-init # runs alembic upgrade head, exit 0
```

The compose `migration-init` service (command `alembic upgrade head`, depends on
`postgres` healthy, `restart: no`) reached `060_add_migration_factory_tables` on a
fresh database and exited 0. The API and worker both gate on
`migration-init: service_completed_successfully`, so application services never
start before the schema is at head.

## 5. Known limitations

* **SQLite chain (resolved 2026-08-17)**: `alembic upgrade head` previously
  failed on SQLite in `050_add_missing_tenant_fks` because SQLite revalidates
  the `legacy_null_campus_records` view when the batch-altered `assignments`
  table is renamed. 050 was repaired to drop and recreate the view around the
  rebuild — the same pattern migrations 044/047 already used — so the full
  chain now applies from an **empty SQLite database** too (verified; the repair
  is SQLite-only and does not change PostgreSQL DDL, so already-applied
  databases are unaffected).
* Migration **downgrades** work for the newest revisions (verified 060→059,
  059→058, 051→049) but are not exercised for the entire chain; downgrade
  support is best-effort and mainly intended for local development.
  `alembic check` noise is tracked as a backlog cleanup item.

## 6. Additive migration policy

All schema changes must be **additive** migrations appended linearly after
`060_add_migration_factory_tables`. Do not edit historical revisions in place
(production data compatibility). Use `op.batch_alter_table` only where
necessary (SQLite portability of FKs), and verify:

```bash
uv run alembic heads                      # exactly one head
uv run alembic upgrade head               # applies cleanly (PostgreSQL)
uv run alembic upgrade head               # idempotent
```

## 7. Verification commands an acquirer can run

```bash
cd apps/api
uv run alembic heads                                      # expect 1 head
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas \
  uv run alembic current                                  # expect head
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas run --rm migration-init
```
