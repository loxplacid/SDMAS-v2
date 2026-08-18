# DATA MODEL — Schema Inventory and Consistency Baseline

Date: 2026-08-16 · Verdict: **CONSISTENT** — SQLAlchemy models, Alembic
migrations, and the live PostgreSQL schema agree; no objectively-confirmed
schema discrepancy required a fix in this audit.

---

## 1. Inventory

* **137 ORM tables** (registered via `app.infrastructure.models` → `Base.metadata`),
  all present in the live database and produced by the 66-revision Alembic chain.
* **35 domains** under `apps/api/app/domains/` (academic, academic_ops,
  admission, analytics, attendance, attendance_intelligence, audit, auth,
  billing, cases, class_360, command_center, communications, data_quality,
  documents, events, fees, institution, jobs, leave, migration, notifications,
  parent, report_builder, report_cards, reports, risk, school_finance, search,
  student, student_360, student_portal, teacher_360, timeline, workflow).
* **Platform tables**: `institutions`, `campuses`, `users`, `roles`,
  `permissions`, `role_permissions`, `user_roles`, `refresh_tokens`,
  `user_school_memberships`, `alembic_version`.
* **Tenant boundary**: every tenant-owned aggregate root carries `campus_id`
  (students, classes, sections, fee_dues, payments, transaction_logs,
  attendance_records, documents, cases, migration_projects, notifications,
  communication_messages, …). Child tables (case_events, document_versions,
  message_recipients, admission_documents, …) are **scoped through their
  parent's campus_id** rather than duplicating the column — verified by the
  adversarial multi-tenant audit (see `docs/enterprise/TENANT-RBAC-VERIFICATION.md`).

## 2. Consistency verification (PostgreSQL 16)

| Dimension | Method | Result |
|---|---|---|
| Tables | ORM metadata vs live DB (`inspect`) | 103/103 present; only DB-only table is `alembic_version` (expected) |
| Columns | per-table column set | 0 missing, 0 extra |
| Nullability | per-column nullable flag | 0 mismatches |
| Types | family comparison (int/str/timestamp/bool/numeric/date) | 0 mismatches (JSON vs `_JSON` decorator is same DB type) |
| Foreign keys | FK set (child cols → referred table/col) | 0 missing |
| Uniques | UniqueConstraint + unique indexes | 0 missing (enforced as constraint or unique index) |
| Indexes | ORM-declared index column sets | 0 missing |
| Enums | python `Enum` columns | none in models — statuses are `VARCHAR` + app-level validation (no mismatch dimension) |
| Cascades | FK `ondelete` ORM vs DB | 0 mismatches |
| Fresh-migration parity | `alembic upgrade head` on empty DB, then same scan | identical to live DB |

The scanner checked both the **live `sdmas` database** and a **freshly-migrated
database**; both came back with zero CRITICAL/HIGH/MEDIUM findings. This
confirms the corrective migrations from the prior hardening passes (044–051)
fully closed the historical drift.

## 3. Known representation patterns (intentional, not defects)

1. **App-level timestamp defaults.** `created_at`/`updated_at` are set by
   Python `default=`/`onupdate=` in the models, not by DB `DEFAULT`. This is a
   consistent codebase-wide pattern (107 columns); every ORM write supplies
   them, so no NOT NULL violation is possible through the application.
2. **Dual-layer status defaults.** Some columns carry a DB `server_default`
   (e.g. `status='active'`, `admission_applications.status='inquiry'`) *and*
   a Python default with the same value. Both layers agree; raw SQL and ORM
   paths get the same default.
3. **DB-only performance/search indexes.** 181 indexes exist in the DB (trgm
   search, composite N+1 fixers, `uq_*` unique indexes) that are not mirrored
   into ORM `__table_args__`. They are created by migrations 007/022/024/046/
   048. `alembic check` reports these as noise; CI deliberately gates on
   single-head + `upgrade head`, not `alembic check`. See
   `docs/architecture/CURRENT_STATE.md` §3.
4. **Soft delete.** Only `documents.deleted_at` (nullable timestamp). Service
   filters `deleted_at IS NULL` on list/get and stamps it on delete; model,
   migration, schema, and service agree. No other table uses soft delete.
5. **Audit columns.** `audit_logs` uses the canonical event structure
   (action/actor/result/details) hardened in migration 035; domain tables carry
   `created_at`/`updated_at` per pattern 1.

## 4. Canonical identity layer (TASK 8)

`app/platform/identities/` adds six tenant-owned tables (migration
`053_add_identity_layer`):

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `canonical_people` | One canonical record per real-world person, referencing existing Student/Teacher/Guardian/User rows via `entity_type` + `entity_id` (soft references — no FK, survives entity deletion) | `campus_id`, `(campus_id, entity_type, entity_id)` index |
| `external_identities` | Identifiers from external systems (legacy ERP, biometric, RFID, transport, external orgs) with confidence + status | UNIQUE `(campus_id, source_system, external_id)` — per-campus uniqueness |
| `identity_aliases` | Alternate names/identifiers for a person | active-flag + person index |
| `identity_matches` | Deterministic match proposals with confidence + manual review state | UNIQUE `(person_a_id, person_b_id, matched_by)` — idempotent proposals |
| `identity_merges` | Source→target merges with before/after snapshots (JSON) | performed_by/at, status |
| `identity_history` | Append-only lifecycle audit trail | action, actor_id, details (JSON) |

All six are auto-classified `TENANT_DIRECT` by the multi-tenant registry
(`campus_id` column present) and only reachable through `IdentityRepository`
(tenant-scoped). JSON columns use the canonical `JSONType` decorator
(`app/infrastructure/types.py`).

## 5. Data lineage layer (TASK 9)

`app/platform/lineage/` adds six tenant-owned tables (migration
`054_add_lineage_tables`):

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `lineage_data_sources` | Named source systems/tables/files/records (legacy ERP, CSV uploads, `sdmas.students`) | `source_type`, `external_ref`, `record_ref`; `(campus_id, source_type, external_ref)` index |
| `lineage_data_assets` | Datasets, metrics, dashboards, reports, exports | `asset_type`, `ref` (pointer to the concrete object), `schema_info` (JSON) |
| `lineage_transformations` | The step between source and asset (SQL, mapping, aggregation, import) | `transform_type`, `definition` (JSON) |
| `lineage_edges` | Directed polymorphic edges `(upstream_type, upstream_id) → (downstream_type, downstream_id)` | UNIQUE `(campus_id, upstream_type, upstream_id, downstream_type, downstream_id, edge_type)` |
| `lineage_calculation_versions` | Versioned calculation/metric definitions | UNIQUE `(campus_id, calc_name, version)`; `is_current` + `superseded_by` chain |
| `lineage_evidence_refs` | Evidence pointers (audit entries, migration runs, files, reports, source records) — never copied, only referenced | `node_type`+`node_id` polymorphic, `kind`, `reference`, `checksum` |

Edges are polymorphic so the graph can later span reports, migration runs
and reconciliation without re-migrating the edge table.  All six are
auto-classified `TENANT_DIRECT`; `LineageService.register_migration_import`
records lineage when the migration engine completes an import
(`import_job.py`), so every migrated value traces back to its source file
and run.

## 6. Universal reconciliation engine (TASK 10)

`app/platform/reconciliation/` adds six tenant-owned tables (migration
`055_add_reconciliation_tables`):

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `reconciliation_runs` | One reconciliation pass between a source and a target dataset | UNIQUE `(campus_id, idempotency_key)` — idempotent re-runs; status machine draft→running→completed/exceptions_pending→approved→closed |
| `reconciliation_rule_configs` | Named, reusable matching/comparison rules | UNIQUE `(campus_id, name)`; match_keys + comparison_fields (JSON) |
| `reconciliation_matches` | Per-record result: matched / source_only / target_only / exception | UNIQUE `(run_id, source_ref)`; source/target payloads + per-field differences (JSON) |
| `reconciliation_exceptions` | Out-of-tolerance / unmatched records requiring manual review | code, severity, status open→resolved→closed, resolution (JSON) |
| `reconciliation_approvals` | Approval trail (approve / reject / escalate) | decision, approver_id, comment |
| `reconciliation_evidence` | Evidence pointers (audit, files, source records, reports) | `(run_id, kind, reference)` index |

A *generic* framework — the domain-specific `payment_reconciliations` /
`reconciliation_items` tables in `school_finance` are untouched.  The
matcher is deterministic (normalizers + side-aware match keys + tolerance
rules: exact / absolute / percent / days) and runs are idempotent via
`idempotency_key`.  All six are auto-classified `TENANT_DIRECT`.

## 7. Policy-as-code layer (TASK 11)

`app/platform/policy/` adds three tenant-owned tables (migration
`056_add_policy_tables`):

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `policy_definitions` | A named policy with a stable business key + scope | UNIQUE `(campus_id, policy_id)`; scope ∈ {attendance, fees, admissions, approvals, compliance, security, workflow, global} |
| `policy_versions` | Immutable versioned snapshots: rules + exceptions + applicability + effective dates + approval metadata | UNIQUE `(policy_def_id, version)`; `effective_from ≤ now < effective_until` authoritative; `is_current` fast-path flag |
| `policy_evaluations` | Every evaluation persisted — traceable to policy version + input data + result | `(policy_id, version)` and `(subject_type, subject_id)` indexes |

Rules are JSON data over a **closed operator set** (eq/neq/lt/lte/gt/gte,
in/not_in, contains, exists/not_exists, is_true/is_false, and/or/not) — no
code evaluation; unknown operators fail closed.  Evaluation is a pure
function of the effective version + input data (deterministic, explainable:
every result carries per-rule outcomes + applied exceptions + reason).
Publishing a new version ends the previous current version's window, keeping
the chain contiguous.  No board-specific policies are hard-coded — the
registry (``app/platform/policy/registry.py``) only catalogs scopes and
their allowed effects.  All three are auto-classified `TENANT_DIRECT`.

## 8. Enterprise evidence layer (TASK 12)

`app/platform/evidence/` adds six tenant-owned tables (migration
`057_add_evidence_tables`):

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `evidence_packages` | A claim bundled with its supporting evidence | UNIQUE `(campus_id, package_key)` — idempotent re-creation; status draft→open→approved→archived |
| `evidence_items` | Claims/assertions (*what was claimed*), with the policy version that applied | `item_type`, `entity_type`/`entity_id`, `policy_id` + `policy_version` (denormalized) |
| `evidence_references` | Pointers to external supporting data (audit, files, migration runs, reports, source records, policy evaluations) — never copied | `(package_id, ref_type, reference)` index; optional `checksum` |
| `evidence_snapshots` | Immutable captures of data + calculations (*what data supported it*, *what calculation was performed*) | `content` + `calculation` (JSON); `content_hash` = SHA-256 of canonical serialization; immutable by contract |
| `evidence_hashes` | Per-package hash chain over snapshots + items (*has it changed?*) | `prev_hash` + `hash_value` = chain_hash(prev, target_type, target_id, digest); `chain_index` ordering |
| `evidence_approvals` | Approval trail (*who approved it*) | decision, approver_id, comment |

Canonical-JSON SHA-256 hashing follows the same conventions as the build-time
`scripts/evidence/` tool (JUnit manifests + artifact checksums) — the platform
layer is the *runtime* store, the script stays the *build-time* generator.
`verify_package` recomputes every snapshot digest and replays the chain; any
change (content or link) breaks the verdict.  Snapshots have no update path;
approved packages reject additions.  All six are auto-classified
`TENANT_DIRECT`.

## 9. Tamper-evident audit chain (TASK 13)

`app/platform/cryptography/` adds two tenant-owned tables (migration
`058_add_audit_chain_tables`) over the existing `audit_logs` table:

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `audit_chain_entries` | One per audit event: the link, payload hash, current hash, HMAC signature | UNIQUE `(audit_log_id)`; `chain_index` per campus; `prev_hash` + `current_hash` = chain_hash(prev, payload, campus, index) |
| `audit_chain_checkpoints` | Periodic signed state hashes covering the chain up to a point | `up_to_chain_index` + `state_hash` over the ordered current hashes; HMAC signature |

Every ``AuditService.record()`` appends a chain entry (guarded, non-fatal —
a chaining failure never loses the audit event; such rows are reported as
uncovered).  Chains are **per campus** (a tamper in one tenant can never
break another's chain); every link binds the campus id.  Detection:
modification (payload/current-hash mismatch), deletion (index gap,
prev-mismatch, or checkpoint tail-deletion), reordering (link break),
missing audit row (dangling reference).  Signatures are HMAC-SHA256 with
``AUDIT_CHAIN_SECRET`` (dev default warns; production must set a real
secret).  **Security guarantee (honest):** tamper-*evident*, not absolute
immutability — a database administrator holding both write access and the
secret could re-sign.  Both tables are auto-classified `TENANT_DIRECT`.

## 10. Zero-fork extension architecture (TASK 14)

`app/platform/extensions/` adds four tenant-owned tables (migration
`059_add_extension_tables`; the migration-factory snapshot table followed at
`060_add_migration_factory_tables`):

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `extension_definitions` | The registry entry: stable `extension_id` business key, provider metadata, lifecycle status, core compatibility range | UNIQUE `(campus_id, extension_id)` — idempotent registration |
| `extension_versions` | Immutable manifest snapshots (the declared contract: permissions, routes, events, config schema, migrations, frontend, policy) | UNIQUE `(extension_def_id, version)`; `is_current` fast-path flag |
| `extension_grants` | Approved permissions — the authorization gate | UNIQUE `(extension_def_id, permission)`; revoke resurrects the row (one row per permission forever) |
| `extension_configs` | Validated configuration (values must match the manifest's declared config schema) | UNIQUE `(extension_def_id)` — one per extension |

Lifecycle: ``register`` → ``publish_version`` (validated manifest + core-compat
check; ``pending``) → ``grant_permission`` (per declared permission) →
``enable`` (fails while any declared permission is un-granted). ``disable``
pauses; ``retire`` is terminal; publishing a newer version supersedes the
previous current one.  Revoking a permission an enabled version requires
auto-disables it.  The manifest contract is **closed**: permissions use the
``scope.action`` grammar from the registry catalogs, routes must live under
``/api/v1/ext/{extension_id}/``, event subscriptions come from the platform
event catalog, policy scopes from the policy registry, and configuration
values are validated against the declared schema before persist.  Every
lifecycle mutation is audited.  All four tables are auto-classified
`TENANT_DIRECT`.

## 11. Migration factory (TASK 15)

`app/domains/migration/` (existing engine — extended, not replaced) gains the
enterprise pipeline stages: DISCOVER → PROFILE → IDENTITY MATCH → MAP →
TRANSFORM → VALIDATE → DRY RUN → RECONCILE → APPROVE → MIGRATE → VERIFY →
CUTOVER. Migration `060_add_migration_factory_tables` is additive:

| Table | Purpose | Key columns / constraints |
|---|---|---|
| `migration_snapshots` | Immutable dry-run / verify evidence snapshots | `(project_id, kind)` — `kind` ∈ dry_run/verify; `payload` JSON (rows, summary), `row_count`, `created_by` |

`migration_projects` gains JSON columns (no new tables beyond the snapshot):

| Column | Purpose |
|---|---|
| `profile` | Source profiling: entity distribution, quality scorecard, PII columns, duplicate-key candidates |
| `identity_match` | Deterministic legacy→SDMAS match decisions per row (matched / ambiguous / no_match) |
| `mapping_versions` | Append-only mapping history (auto-discovered = v1; every manual save appends, bounded to 50) |
| `approval` | Optional approval workflow `{status, requested_by, approver_id, note, reason}` — statuses pending/approved/rejected |
| `verification` | Post-import source-vs-target verification results (per-entity counts + spot checks) |
| `cutover` | Cutover state — `{status, at}`; `live` blocks rollback (rollback safety) |

New project statuses: `APPROVAL_REQUIRED` / `APPROVED` (the READY → IMPORTING
transition is gated only while approval is pending; projects that never
request approval import directly — back-compatible).  Dry-run snapshots are
persisted as evidence but never touch target tables; verification and cutover
package an evidence package via the TASK 12 evidence foundation (non-fatal on
failure).  All rows remain `campus_id`-scoped `TENANT_DIRECT`; every factory op
is tenant-isolated and audited.

## 12. Discrepancy inventory (this audit)

**Zero objectively-confirmed schema inconsistencies were found.** The write-DTO
Pydantic schemas were checked field-by-field against their models: all flagged
fields are legitimate (action-request DTOs like `reason`/`case_ids`,
aggregate-response fields, or aliases like `password` → `password_hash`,
`plan_code` → plan lookup). No schema references a nonexistent model column in
a way that would break a write path.

## 13. Unresolved risks (tracked, non-blocking)

| Risk | Severity | Notes |
|---|---|---|
| `alembic check` reports 243 representation-noise ops | LOW | Backlog: mirror perf/search indexes into models' `__table_args__` to make `alembic check` clean |
| 20 child tables lack direct `campus_id` | LOW | By design (aggregate-root scoping); a future denormalization could add the column for direct index-only scans, but no isolation gap exists |
| Full-chain downgrade not exercised | LOW | Downgrades verified only for 051→049; best-effort support |
| `file_key` on `migration_projects` not exposed in schemas | INFO | Internal storage key; upload flow uses it server-side only |

## 14. Adding a schema change

1. Edit the ORM model first (single source of truth).
2. Create an **additive** Alembic revision appended after
   `060_add_migration_factory_tables` (never edit historical revisions).
3. Verify: `alembic heads` (1 head), `alembic upgrade head` on a fresh
   PostgreSQL DB, then re-run this audit's ORM-vs-DB comparison.
4. Add a regression test that asserts the new column/constraint exists.

## 15. Re-running the consistency check

```bash
# Fresh DB parity (PostgreSQL 16)
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas up -d postgres
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas exec -T postgres \
  psql -U sdmas -d postgres -c "CREATE DATABASE sdmas_check;"
cd apps/api
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas_check \
  uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas_check \
  uv run alembic check          # expect representation noise only (see §3.3)
```
