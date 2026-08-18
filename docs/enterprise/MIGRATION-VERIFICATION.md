# MIGRATION-VERIFICATION.md

Enterprise migration engine (D2 workspace) verification, end to end.
Date: 2026-08-16 · Verdict: **VERIFIED** — full lifecycle proven from upload to
rollback; **four genuine defects found, fixed, and regression-tested**.

---

## 1. Architecture under test

The existing migration domain (`apps/api/app/domains/migration/`) is the single
source of truth — no second engine was created. The workspace orchestrates:

```
UPLOAD  →  DISCOVERY  →  AUTO-MAPPING  →  VALIDATION  →  PREVIEW
    →  CORRECTION  →  EXECUTE (durable background job)  →  PROGRESS
    →  RECONCILIATION  →  REPORT  →  AUDIT  →  ROLLBACK
```

* **Engine**: `MigrationEngine` runs one `MigrationRun` per entity stream
  (students → academic → attendance → fees), ordered by FK dependency;
  migrators register into a global registry and each records legacy→SDMAS ID
  mappings per row so rollback is precise.
* **Workspace**: `MigrationProjectService` (tenant-scoped via
  `MigrationProjectRepository`) owns project state through the machine
  `draft → discovering → mapping → validating → ready → importing →
  reconciling → completed` (and `cancelled` / `failed` / `rolled_back`).
* **Execution**: `POST /import` only **enqueues** a durable job
  (`MIGRATION_IMPORT_JOB_TYPE`) — large imports never run inside the HTTP
  request. The background worker claims the job and executes it with progress
  tracked server-side (`records_processed`, `row_count`).
* **Rollback**: `RollbackService` deletes exactly the rows a run created
  (from `migration_mappings`), in FK-safe order — pre-existing data is never
  touched.
* **Inputs**: CSV, XLSX, JSON, JSONL, parsed by the existing readers.

## 2. Defects found and fixed

### D1 (HIGH) — project never reached `COMPLETED`; workspace rollback unreachable

* **Symptom**: after import the project sat in `RECONCILING` forever. The
  rollback endpoint requires the `COMPLETED → ROLLED_BACK` transition, so
  every rollback raised `ConflictError`. **Workspace rollback was dead code.**
* **Root cause**: `reconcile()` built the report but only transitioned
  `RECONCILING → COMPLETED` conditionally — and the condition never held.
* **Fix** (`project_service.py`): `reconcile()` now performs the
  `RECONCILING → COMPLETED` transition explicitly after building the report.
* **Tests**: `test_reconcile_transitions_project_to_completed`,
  `test_rollback_reachable_only_after_completed`,
  `test_rollback_from_reconciling_still_rejected` (the state machine remains
  intentional — rollback before reconcile still 409s).

### D2 (HIGH) — rollback covered only the first run of a multi-entity import

* **Symptom**: a project importing students + academic + attendance + fees
  produced 4 runs; rollback deleted only `project.run_id` (the students run),
  orphaning enrollments, attendance and payments.
* **Root cause**: `rollback()` used `project.run_id` instead of enumerating
  every run owned by the project.
* **Fix** (`project_service.py`): roll back **all** runs in reverse dependency
  order (`fees/attendance → academic → students`) so FK constraints never
  break.
* **Tests**: `test_rollback_removes_all_entity_streams`,
  `test_rollback_preserves_pre_existing_rows` (15 records across 4 runs
  removed; pre-existing rows untouched).

### D3 (HIGH) — per-run rollback deleted nothing for container migrators

* **Symptom**: academic and fees migrators record mappings per *subtype*
  (`academic_year`, `class`, `section`, `enrollment`, `fee_type`,
  `fee_structure`, `fee_due`, `payment`) while the base rollback looked
  mappings up by run entity type — empty for those runs. Attendance and
  payments recorded **no** mappings at all, so their rows could never be
  rolled back.
* **Fix**:
  * `migrators/academic.py`, `migrators/fees.py`: `rollback()` overrides that
    group the run's whole mapping set by subtype and delete children-first.
  * `migrators/attendance.py`, `migrators/fees.py`: record mappings for every
    attendance record and payment created.
  * `rollback.py` `plan_rollback()`: count the run's whole mapping set
    (`list_by_run`) instead of per-entity lookups.
* **Tests**: `test_plan_rollback_counts_all_subtype_mappings` (per-run plans:
  students 2, academic 5, attendance 2, fees 6).

### D4 (HIGH) — rollback deleted from the **wrong table** under full-app import

* **Symptom**: with the full application imported (as in production and every
  API-level test), attendance rollback removed **0** of 2 records. The
  `test_audit` suite running before the migration suite exposed it as
  order-dependent; in production it would fail every time.
* **Root cause**: `BaseMigrator._get_table()` matched the **first mapper whose
  tablename *contains* the entity type** — import-order dependent. With
  `attendance_intelligence` models registered (production), `"attendance"`
  resolved to `attendance_thresholds` instead of `attendance_records`; the
  base rollback deleted from the wrong table and silently "succeeded".
* **Fix** (`base.py` + migrators): migrators that rely on the base rollback
  declare an exact `table_name` (`attendance_records`, `students`, `users`);
  `_get_table()` prefers an exact match, deterministic regardless of import
  order. The substring scan remains only as a legacy fallback for migrators
  that never declared a table.
* **Tests**: `test_rollback_table_resolution_is_import_order_independent` —
  imports the full app, asserts `attendance → attendance_records`, then runs
  the complete import→reconcile→rollback cycle (15 records removed).

### D5 (MEDIUM) — progress counter over-counted on multi-entity imports

* **Symptom**: for a 425-row import touching multiple entity streams,
  `records_processed` (850) exceeded `row_count` (425) — the progress bar
  would show "processed 850 of 425". (The frontend clamps at 100%, hiding it.)
* **Root cause**: `import_job.py` summed each entity stream's processed rows
  into one `records_processed` total, but `row_count` is the source-file row
  count shared by all streams.
* **Fix** (`import_job.py`): each entity stream gets an equal share of the
  row-count budget, so `records_processed` never exceeds `row_count` and the
  percentage stays truthful.
* **Test**: `test_large_file_chunked_import_and_resume` asserts
  `records_processed == row_count` for a 425-row / 3-chunk import, plus
  idempotent re-run.

## 3. Acceptance scenario coverage

| Scenario | Test | Result |
|---|---|---|
| Messy CSV | `test_demo_fixture_blocks_and_explains_every_defect` (duplicates, bad dates, bad amounts, orphans, missing values detected with samples) | PASS |
| Correction loop | `test_corrected_mapping_reaches_ready_and_imports` (19 rows created, 0 rejected) | PASS |
| XLSX | pre-existing workspace suite (`test_accepts_xlsx_extension`) | PASS |
| Duplicate students | demo fixture `duplicate == 1` + `test_repeated_import_is_idempotent` | PASS |
| Invalid dates / amounts | demo fixture categories | PASS |
| Missing values | demo fixture `missing_optional == 2` | PASS |
| Inconsistent columns | `test_inconsistent_columns_do_not_crash` (ragged row) | PASS |
| Orphan references | demo fixture `orphan_reference == 2` | PASS |
| Unicode | `test_unicode_names_roundtrip` (Zoë Müller, José García through DB) | PASS |
| Large files | `test_large_file_chunked_import_and_resume` (425 rows, 3 chunks, resume) | PASS |
| Repeated import | `test_repeated_import_is_idempotent` | PASS |
| Failed import | `test_failed_import_marks_project_failed_and_audits` (project FAILED, run failed, FAILURE audit entry) | PASS |
| Cancellation | `test_cancellation_from_ready` + `test_cancellation_while_importing_cancels_job` | PASS |
| Tenant isolation | pre-existing workspace suite + multi-tenant suites (campus-scoped runs, deny cross-tenant) | PASS |
| Full API flow | `test_full_api_flow_upload_to_report` — real `POST /migration/projects` → validate → preview → enqueue → worker claims+executes → reconcile → report | PASS |

## 4. Evidence

* **New regression suite**: `tests/test_migration_verification.py` — 17 tests.
* **Combined migration + audit run**: 142 passed, 0 failed (3 consecutive
  runs) — includes the `test_audit` suite that exposed D4.
* **Broad regression** (audit + migration + async-hardening + outbox + domain
  events): 239 passed, 0 failed.
* **Static checks** on all changed files: `ruff check` clean, `ruff format
  --check` clean, `mypy` clean.
* No migration/schema changes — all fixes are application-layer.

## 5. Reproduction commands

```bash
cd apps/api
uv run pytest tests/test_migration_verification.py -q                    # 17 new tests
uv run pytest tests/test_migration_workspace.py tests/test_migration_step2.py -q
uv run pytest tests/test_audit tests/test_migration_verification.py -q   # D4 ordering case
uv run ruff check app/domains/migration/ tests/test_migration_verification.py
```

## 6. Known limitations

* Rollback is per-project and precise only for rows created through the
  migration engine (mapping-tracked). Rows created outside a migration are
  never candidates — by design.
* Import execution is driven through the durable jobs worker; the API test
  simulates the worker by claiming+executing the enqueued job against the
  same database (the real worker performs the identical `JobService
  .execute_job` path).
* Cancellation is supported at the project level (READY/IMPORTING); a fully
  chunk-level abort/resume is intentionally simple (re-run is idempotent).

## 7. Files changed (this pass)

| File | Change |
|---|---|
| `app/domains/migration/base.py` | exact `table_name` resolution in `_get_table()` (D4) |
| `app/domains/migration/migrators/attendance.py` | `table_name`, mapping recording, import cleanup |
| `app/domains/migration/migrators/students.py` | `table_name`, import cleanup |
| `app/domains/migration/migrators/users.py` | `table_name`, import cleanup |
| `tests/test_migration_verification.py` | 17-test end-to-end + regression suite (D1–D5) |

Earlier fixes already committed to the working tree (verified this pass):
`project_service.py` (D1, D2), `migrators/academic.py` + `migrators/fees.py` +
`rollback.py` + `repository.py` (D3), `import_job.py` (D5).
