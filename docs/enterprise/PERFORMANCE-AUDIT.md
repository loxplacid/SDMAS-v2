# Performance Audit — SDMAS v2

Date: 2026-08-13 · Scope: backend query paths, database indexes, frontend bundle

## Summary

Measured at realistic scale (100k students / 300k ledger rows per campus) on
PostgreSQL 16. Three hot query shapes were doing full scans; targeted indexes
fix all three with **8–74x** speedups. The frontend's heaviest on-demand chunk
was split so report pages no longer pay for export libraries they don't use.

| Query shape (100k students) | Before | After | Speedup |
|---|---|---|---|
| Student search (`ILIKE %q%`) + count | 237–249 ms | 3.2–3.4 ms | **~74x** |
| Ledger list, campus + last 90 days | 159 ms | 5.6 ms | **~28x** |
| Student list page 1 (filtered) | 43 ms | 4.9 ms | **~9x** |
| Student list deep page (offset 50k) | 79 ms | 21.5 ms | **3.7x** |
| Ledger list by student | 17.6 ms | 2.6 ms | **6.8x** |
| Dashboard aggregates (payments/fee_dues) | 11 ms | 3.9 ms | **2.8x** |

## Method

- Scratch databases created from scratch, migrated with `alembic upgrade head`
  (PostgreSQL 16 + SQLite — both dialects verified).
- 100,000 students + 300,000 `transaction_logs` rows seeded with the same
  shapes the app produces (status mix, date spread).
- The exact SQL shapes emitted by the app's services were run with
  `EXPLAIN (ANALYZE, BUFFERS)` before/after.
- Reproducible benchmarks shipped in the repo:
  - `apps/api/scripts/perf_bench.py` — SQLite sweep (1k / 10k / 100k).
  - `apps/api/scripts/perf_pg.py` — PostgreSQL full benchmark (defaults to
    100k; `PERF_DATABASE_URL` + `PERF_STUDENTS` env overrides).

## Findings & fixes

### 1. Student search — full scan per keystroke (HIGH impact)

`StudentRepository.search` runs
`(first_name ILIKE '%q%' OR last_name ILIKE '%q%' OR student_number ILIKE
'%q%' OR email ILIKE '%q%')` inside the campus scope.

The repo already had *per-column* trigram GIN indexes (migration 022), but the
planner never combined them for OR queries at this scale — every search was a
sequential scan of the campus subset (237 ms at 100k).

**Fix:** migration `048_perf_indexes` adds one multi-column GIN over exactly
the OR'd columns (`ix_students_trgm` on `(first_name, last_name,
student_number, email) gin_trgm_ops`) plus `CREATE EXTENSION IF NOT EXISTS
pg_trgm`. The planner now bitmap-scans the index: **3.2 ms** (~74x).

Note: the extension creation requires a DB role that can create extensions.
The compose setup runs as the postgres superuser; managed production DBs
should pre-create `pg_trgm` (the migration fails loudly otherwise).

### 2. Ledger list by campus + date range — full campus scan (HIGH impact)

The `/school-finance/transactions` list and the 90-day views filter
`campus_id = X AND created_at >= now() - 90 days ORDER BY created_at DESC`.
`transaction_logs` had `campus_id` (from the unique idempotency constraint)
and `created_at` indexes separately, but no combined index — the range filter
scanned every campus row (159 ms at 300k rows).

**Fix:** `ix_transaction_logs_campus_created` on `(campus_id, created_at)` —
a seek + backward index scan: **5.6 ms** (~28x).

### 3. Student filtered list — campus subset scan (MEDIUM impact)

`/students?status=active` list + count used the single-column `campus_id`
index. The page-1 LIMIT query had to scan the campus subset before finding the
first 50 matches (43 ms).

**Fix:** `ix_students_campus_status` on `(campus_id, status)`: **4.9 ms**
(~9x).

The companion `count(*)` query was analyzed and intentionally NOT indexed
further: at 75% selectivity (75000/100000 rows) the planner correctly prefers
a sequential scan (33 ms) — a covering index would add write overhead for a
case the planner already handles.

### 4. Frontend — export libraries bundled into every report page (HIGH impact)

`useExport` statically imported `jspdf` + `jspdf-autotable` + `xlsx` (~29 MB
on disk, **740 KB raw / 238 KB gz** in the bundle). Every report page pulled
that chunk on open, even when the user exported nothing.

**Fix:** dynamic `import()` inside each export callback. Report pages now load
**0 KB** of export libraries; PDF loads 124 KB gz only on the PDF click, Excel
loads 157 KB gz only on the Excel click.

Verified: build shows separate `jspdf.es.min` (382 KB/124 KB gz) and `xlsx`
(488 KB/157 KB gz) chunks + a 1 KB hook wrapper. `tsc --noEmit` clean; full
frontend suite 516 tests pass; new `src/__tests__/use-export.test.ts` (4
tests) pins the on-demand behavior.

## Checked and found healthy

- **No N+1 in hot list endpoints.** Student list/search are single queries
  with a companion count; 37 eager-load (`selectinload`/`joinedload`) sites.
  The only per-row loop awaits are small bounded batches (subscription
  expiry, per-assignee case counts, fixed built-in category checks) — not hot
  paths.
- **Initial frontend bundle is well-split:** entry 141 KB gz; route chunks
  lazy; charts (117 KB gz) and sqlite-wasm search worker load on demand.
- **Dashboard aggregates** use indexed `campus_id` filters; 2.8x win came for
  free from the new indexes.
- **OFFSET pagination** is used throughout. Deep pages degrade linearly
  (79 ms at offset 50k). Keyset pagination would change the API contract;
  noted as a future option, not needed at current scale.

## Migration

`alembic/versions/048_add_performance_indexes.py`

- `ix_students_trgm` (GIN, PostgreSQL-only, guarded by dialect check)
- `ix_students_campus_status` (both dialects)
- `ix_transaction_logs_campus_created` (both dialects)
- `CREATE EXTENSION IF NOT EXISTS pg_trgm` (idempotent; extension left in
  place on downgrade)

Verified on fresh databases in both dialects: `alembic upgrade head` succeeds
from empty, single head (`048_perf_indexes`), downgrade drops the indexes.

## Evidence

- Baseline + after-index EXPLAIN (ANALYZE, BUFFERS) timings above, produced
  by `apps/api/scripts/perf_pg.py` on a fresh migrated `sdmas_perf` database.
- SQLite sweep confirms the scaling story at 1k/10k/100k
  (`apps/api/scripts/perf_bench.py`): search 2.5 → 9.4 → 119 ms; ledger range
  2.4 → 15 → 151 ms before indexes.
- Regression: backend `tests/test_finance_exports.py` + `tests/test_multi_tenant`
  (90 passed); full frontend suite 516 passed; `tsc --noEmit` clean.

## Remaining opportunities (not acted on — avoid premature optimization)

1. **Keyset pagination** for very deep list pages (contract change; OFFSET is
   fine at current scale).
2. **Postgres FTS / unaccent** over ILIKE for ranked search (already outlined
   in migration 022's comments; the trigram index covers current needs).
3. **Covering index** for the 75%-selectivity count (planner already chooses
   seq scan correctly).
