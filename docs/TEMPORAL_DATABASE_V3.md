# SDMAS Temporal Database v3 — "The Archive"

> The tenth expansion of the Corridor. Codename: **The Archive**.
>
> **Scope:** the complete, production-grade architecture for making SDMAS a
> **true temporal database** — every table bitemporal, every edit preserved
> with old value / new value / timestamp / actor / reason / transaction id,
> and every query (lists, relationships, reports, attendance, fees,
> permissions, dashboards, search, analytics) automatically time-travelable:
> *"View the system as it existed on 15 June 2024."*
>
> **This is an architecture document. No code is implemented here.**
>
> **Grounding in the real codebase:**
>
> | Reality | Evidence |
> |---|---|
> | RDBMS | PostgreSQL 16 (docker-compose), MySQL via legacy lineage, SQLite for dev |
> | ORM | SQLAlchemy 2 async, `DeclarativeBase` in `infrastructure/database.py` |
> | Migrations | Alembic (`apps/api/alembic/versions/00*.py`) |
> | Current change tracking | `created_at`/`updated_at` columns (mutable current state only) |
> | Existing audit | `audit_logs` — append-only, JSON `before_state`/`after_state`, actor, request/correlation ids, result, IP |
> | Events | Domain-event catalog + transactional outbox |
> | Multi-tenancy | `TenantScopedRepository`, campus scoping |
> | The Forge (metadata platform) | Generated CRUD must inherit temporal behavior (§10) |
>
> **The critical distinction — what The Archive is NOT:** the existing
> `audit_logs` table is an *audit trail* (a security record of *that an event
> happened*). The Archive is a **bitemporal database** (the *state* of every
> row at any point in time, queryable). Audit tells you who did what; temporal
> tells you what the system *was*. Both coexist: audit stays the security
> record; temporal becomes the storage substrate beneath it. This design
> deliberately rejects the naive pattern of "add an audit row on every write
> and call it history" — that cannot answer "as of 15 June" without replaying
> thousands of rows.

---

## 0. The thesis — time is a first-class dimension

In a normal SDMAS, a row's state is its current state; `updated_at` is a
hand-wave. In The Archive, **every fact has two clocks**:

1. **Valid time** (`vt_from`, `vt_to`) — *when the fact was true in the real
   world*. "Amina was in Class 10A from 1 Sept 2025 to 30 June 2026."
2. **Transaction time** (`tt_from`, `tt_to`) — *when the system recorded it*.
   "The system has known Amina is in Class 10A since 12 Aug 2025 09:41."

This is **bitemporal** modeling (Snodgrass / Bitemporal data model). It is
what enterprise financial systems use, because it separates *reality* from
*knowledge*:

- **AS OF** a transaction-time instant answers *"what did the system know on
  15 June 2024?"* — the primary requirement.
- **AS OF VALID** an instant answers *"what was true in the world then?"* —
  for retroactive corrections (a fee record backdated to last term).
- **Both together** answer *"what did we know was true then?"* — for audits,
  disputes, and regulatory questions.

Only bitemporality supports **undo/redo** (transaction-time) and
**retroactive edits** (valid-time) without corrupting history.

### 0.1 The ten-second proof

```
current table  students        history table  students_history
┌────────┬───────────────┐   ┌────────┬──────────┬──────────┬──────────────────┐
│ id=7   │ Amina Kante   │   │ id=7   │ vt 2025-09│tt 2025-08│ first_name: Amina│
│ class  │ 10A           │   │ id=7   │ vt 2024-09│tt 2024-08│ first_name: Amina│
└────────┴───────────────┘   │        │ vt 2024-09│tt 2024-08│ class: 9B        │
                             └────────┴──────────┴──────────┴──────────────────┘
  SELECT class FROM students AS OF '2024-06-15'  →  '9B'
```

No replay, no reconstruction — the answer is one indexed range lookup.

---

## 1. Architecture

### 1.1 The temporal engine, in one diagram

```
                ┌────────────────────────────────────────────────┐
                │                 APPLICATION LAYER              │
                │   FastAPI · metadata engine (The Forge) ·      │
                │   search · reports · dashboards                │
                └──────────────────────┬─────────────────────────┘
                                       │  (all SQL passes through)
                                       ▼
                ┌────────────────────────────────────────────────┐
                │  TEMPORAL ENGINE — the only writer & rewriter  │
                │                                                │
                │  WRITE PATH        │    READ PATH              │
                │  ┌─────────────┐   │   ┌───────────────────┐   │
                │  │ TxnManager  │   │   │ QueryRewriter     │   │
                │  │ (close-open │   │   │ (AS OF rewrite,   │   │
                │  │  bi-temporal│   │   │  session context) │   │
                │  │  write)     │   │   └─────────┬─────────┘   │
                │  └──────┬──────┘   │             │             │
                │         │          │   ┌─────────▼─────────┐   │
                │  ┌──────▼──────┐   │   │ TemporalIndex     │   │
                │  │ Repository  │   │   │ (GiST over ranges)│   │
                │  │ adapters    │   │   └───────────────────┘   │
                │  └──────┬──────┘   │                           │
                └─────────┼──────────┴───────────────────────────┘
                          ▼
                ┌────────────────────────────────────────────────┐
                │   POSTGRESQL 16  (MySQL 8 / SQLite adapters)   │
                │   current tables + *_history tables +         │
                │   txn registry + snapshot store + GC worker   │
                └────────────────────────────────────────────────┘
```

### 1.2 Principles

1. **The engine owns time.** No domain code writes `updated_at` by hand
   anymore. Every write goes through `TxnManager`, which stamps
   `tt_from`/`vt_*` and the change envelope (old, new, actor, reason, txn_id).
   Domain code keeps its business logic; the temporal concern is cross-cutting.
2. **Current state stays in the current table** (fast OLTP, no history on the
   hot path). History lives in mirror `*_history` tables. Reads with no time
   context hit current tables untouched (zero overhead); reads with AS OF hit
   history via range indexes.
3. **AS OF is a session/request context, not a per-query flag** — the UI sets
   "system as of 2024-06-15" once; every downstream query (nav, lists, detail,
   reports, search) inherits the context (the requirement's *"the entire
   application must automatically show that historical state"*).
4. **Undo/redo is transaction-time travel.** Undo = open a new transaction
   that re-asserts the previous state. It is *not* a destructive DELETE; it is
   another version (and is itself undoable, and fully auditable).
5. **Retention is explicit and policy-driven** — hot history (GiST-indexed),
   warm history (compressed/columnar), cold snapshots (encrypted archive).
   The Archive never silently deletes; GC operates on closed transaction-time
   ranges under policy (§7).

---

## 2. Folder structure

```
apps/api/app/temporal/               # the temporal engine (new package)
├── __init__.py
├── context.py                       # TimeContext (AS OF / VALID / none)
├── txn.py                           # TxnManager: close-open bitemporal write
├── envelope.py                      # ChangeEnvelope: old/new/actor/reason/txn
├── registry.py                      # TemporalTable registry (schema discovery)
├── metadata.py                      # which columns are vt/tt/plain per table
├── rewriter.py                      # QueryRewriter: SQL AS OF rewriting
├── repository.py                    # TemporalRepository (async, per entity)
├── indexes.py                       # TemporalIndex: GiST (vt,tt) maintenance
├── snapshots.py                     # SnapshotService: point-in-time restore
├── compression.py                   # history compaction + columnar/TOAST
├── gc.py                            # retention policy worker
├── api.py                           # /api/time (set context), /api/history,
│                                    #   /api/diff, /api/undo, /api/restore
├── migrations.py                    # Alembic-side: backfill + enable tables
└── workers.py                       # background jobs (compaction, GC, snapshot)

apps/api/alembic/versions/           # existing migrations +
    0xx_enable_temporal_*.py         #   per-table temporal enablement
apps/api/app/infrastructure/database.py   # add temporal hooks to session
apps/api/app/domains/*/models.py          # add TemporalMixin columns
```

### 2.1 The mixin (SQLAlchemy)

```python
class TemporalMixin:
    vt_from: Mapped[datetime]   # valid-time period open
    vt_to:   Mapped[datetime | None]   # NULL = open (current)
    tt_from: Mapped[datetime]   # transaction-time period open
    tt_to:   Mapped[datetime | None]   # NULL = open (current)
```

`Base` models gain the mixin; the `*_history` mirror tables are generated by
Alembic from the same metadata plus `change` JSONB + `txn_id` FK.

---

## 3. Temporal schema

### 3.1 Table shapes

**Current table** (unchanged columns + four time columns):

```sql
CREATE TABLE students (
    id          BIGINT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    class_id    BIGINT,
    campus_id   BIGINT NOT NULL,
    vt_from     TIMESTAMPTZ NOT NULL,        -- valid-time open
    vt_to       TIMESTAMPTZ,                 -- NULL = still valid
    tt_from     TIMESTAMPTZ NOT NULL,        -- transaction-time open
    tt_to       TIMESTAMPTZ,                 -- NULL = current knowledge
    -- Exclude current row of (id) for tt overlap:
    EXCLUDE USING gist (id WITH =, tstzrange(tt_from, tt_to) WITH &&)
);
```

**History table** (mirror + the change envelope):

```sql
CREATE TABLE students_history (
    id          BIGINT NOT NULL,             -- entity id (not PK — many versions)
    first_name  TEXT,
    class_id    BIGINT,
    campus_id   BIGINT,
    vt_from     TIMESTAMPTZ NOT NULL,
    vt_to       TIMESTAMPTZ,
    tt_from     TIMESTAMPTZ NOT NULL,        -- when this version was known
    tt_to       TIMESTAMPTZ,                 -- when this version was superseded
    txn_id      BIGINT NOT NULL REFERENCES txn_log(id),
    actor_id    BIGINT,                      -- denormalized for fast filters
    reason      TEXT,                        -- 'fee correction', 'rollover', ...
    change      JSONB NOT NULL,              -- {"old": {...}, "new": {...}}
    PRIMARY KEY (id, tt_from),
    EXCLUDE USING gist (id WITH =, tstzrange(tt_from, tt_to) WITH &&)
);
```

**Transaction log** — one row per write transaction (the "why" store):

```sql
CREATE TABLE txn_log (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tx_id        UUID NOT NULL UNIQUE,       -- end-to-end id (request_id)
    actor_id     BIGINT,
    actor_type   TEXT,                       -- user / worker / system / webhook
    campus_id    BIGINT,
    reason       TEXT,                       -- required for non-trivial writes
    committed_at TIMESTAMPTZ NOT NULL,
    payload      JSONB,                      -- full before/after per touched row
    parent_txn   BIGINT REFERENCES txn_log(id)   -- undo/redo chains
);
```

### 3.2 The write protocol — close-open, bitemporal

Every write is a **close-open transaction** (the enterprise pattern):

```
BEGIN;
  -- 1. close the current version's transaction time
  UPDATE students
     SET tt_to = now()
   WHERE id = $id AND tt_to IS NULL;

  -- 2. insert the new version (new tt_from = now, vt from the edit)
  INSERT INTO students (id, first_name, class_id, vt_from, vt_to, tt_from, tt_to)
  VALUES ($id, $new, $class, $vt, NULL, now(), NULL);

  -- 3. move the closed version into history (with the change envelope)
  INSERT INTO students_history SELECT ..., $txn_id, $actor, $reason,
         jsonb_build_object('old', row_to_json(OLD), 'new', row_to_json(NEW))
    FROM (SELECT * FROM students WHERE id=$id AND tt_to = now()) x;

  -- 4. append the txn_log row (atomic with the change — same commit)
COMMIT;
```

**Why this beats "insert a delta row":**
- current-table reads are always the *latest knowledge* — no replay needed;
- the current row and the history row commit atomically — no torn states;
- valid-time edits *also* close-open the valid range, so a backdated fee edit
  is an honest new version, not a rewrite of the past;
- the history row is a **complete snapshot** of the version, so AS OF needs
  exactly one row lookup, and diff = comparing two history rows' `change`.

---

## 4. Query rewriting

### 4.1 The time context

```python
@dataclass
class TimeContext:
    as_of:  datetime | None   # transaction-time instant ("what we knew")
    valid:  datetime | None   # valid-time instant ("what was true")
    mode:   Literal['none','as_of','valid','both'] = 'none'
```

The API layer sets it from:
- a query param (`?as_of=2024-06-15`),
- a header (`X-Time-As-Of`),
- or the UI's global "view system as of" picker (persisted in session storage,
  propagated by the frontend to every request).

### 4.2 Rewriting rules

| Query | No context (mode none) | AS OF context |
|---|---|---|
| `SELECT ... FROM students` | untouched (zero overhead) | `FROM students_history h WHERE tstzrange(h.tt_from, h.tt_to) @> $as_of AND id = ANY($ids)` — one range lookup per entity |
| `WHERE` predicates | untouched | predicate + range containment |
| Joins (relationships) | untouched | every joined temporal table rewritten independently |
| Aggregates / reports | untouched | rewritten to history, then aggregated |
| Search | `search index` on current | **temporal search**: search the version set valid at $as_of (see §8.5) |
| Permissions | current role graph | **historical permissions**: role/campus membership read AS OF (see §8.3) |
| Dashboard widgets | current metrics | all KPI queries rewritten — the dashboard *becomes* the historical dashboard |

The rewriter is a **SQLAlchemy-level hook**: it intercepts ORM queries
(`with_loader_criteria` / event listeners) and rewrites entity → history
with range predicates. Domain code writes ordinary queries; the engine adds
time. Because the engine is at the ORM layer, **The Forge's generated CRUD
inherits temporal behavior for free** (§10).

### 4.3 The AS OF view (convenience + correctness)

For SQL-heavy consumers (reports), the engine exposes per-entity **AS OF
views**:

```sql
CREATE VIEW students_as_of AS
SELECT h.* FROM students_history h
WHERE h.tt_to IS NULL  -- maintained incrementally by the close-open writer
```

Plus `temporal_at(rel, instant)` table functions for ad-hoc "as of" queries,
so analysts write `SELECT * FROM temporal_at('students', '2024-06-15')`
instead of hand-rolling range logic.

---

## 5. Historical indexes

The hot index for time travel is a **GiST index over the transaction-time
range** (PostgreSQL native):

```sql
CREATE INDEX ix_students_history_tt
    ON students_history USING gist (tstzrange(tt_from, tt_to));

-- plus btree for point filters and joins
CREATE INDEX ix_students_history_entity
    ON students_history (id, tt_from DESC);
CREATE INDEX ix_students_history_txn
    ON students_history (txn_id);
```

- **Point AS OF** (`id` + containment): GiST → O(log n) per entity, not a scan.
- **Entity timeline** (`id` ORDER BY tt_from): btree → instant version list.
- **Actor/reason scans** (history by `actor_id`, `reason`): btree over the
  denormalized columns.
- **Valid-time lookups**: a second GiST over `tstzrange(vt_from, vt_to)` for
  "what was true in the world at X" queries.

The exclusion constraints (`&&` overlap) enforce **temporal integrity**: no
two versions of an entity may overlap in transaction time or valid time —
the database itself rejects double-booked history.

---

## 6. Storage optimization

1. **History tables are append-heavy, read-sometimes** — they get:
   - **Partitioning** by `tt_from` month (list partitions on `date_trunc('month',
     tt_from)`); old partitions detach to cold storage without touching live
     queries.
   - **TOAST + compression**: `change` JSONB and TEXT columns are compressed
     (`pglz`/`lz4`); large payloads (document metadata) move to a separate
     `*_history_blob` table so hot rows stay small.
   - **Columnar history** (optional, PG 17+ or TimescaleDB): history is read
     mostly by `id`+range and by aggregates; columnar storage on the
     `*_history` partitions slashes I/O for report-time AS OF.
2. **Delta compression inside `change`** — a version stores the *full
   snapshot* (fast AS OF) and the envelope keeps `old`/`new` (fast diff);
   the two are complementary, not alternatives. For extremely churny rows
   (e.g. attendance status per student per day), a `change = {field: [old,
   new]}` sparse form is stored and the snapshot is reconstructed lazily.
3. **Warm/cold tiers** — policy-driven (per entity):
   - *hot*: `tt_from` within N months → partitioned + GiST + TOAST;
   - *warm*: older → compressed partition / columnar;
   - *cold*: beyond retention → detached partition → encrypted archive blob
     (S3-compatible) with a manifest; still queryable via the snapshot
     loader on demand.

---

## 7. Snapshots & garbage collection

### 7.1 Incremental snapshots

Snapshots are **not** full dumps (too slow, too big). The Archive uses
**incremental log + periodic base**:

- a **base snapshot** per entity (or per campus) is taken on a schedule —
  a consistent set of current-row versions at instant T (a compact
  `temporal_snapshots` row: `{entity, as_of, blob_ref, checksum}`), stored
  compressed + encrypted;
- between bases, the **txn_log** is the delta; restore = base + replay of
  txn_log rows with `tt_from > base.as_of` and `tt_to <= restore_at`.
- **Point-in-time restore** (`POST /api/time/restore {at, scope}`) creates a
  **new branch**: it does NOT mutate live tables. It materializes the
  historical state into a `restored_*` set (or a temporary schema), so
  restore is reversible and auditable — the same rule as undo.

### 7.2 Undo / redo

- **Undo** = open a new transaction that closes the offending versions'
  transaction time and re-asserts the prior state (which still lives in
  history). `txn_log.parent_txn` links the undo to the original write.
- **Redo** = same mechanism against the undo.
- Both are *new history*, never deletion — undo of an undo is allowed, and
  the entire chain is reviewable in the timeline UI.

### 7.3 Garbage collection (policy-driven, never silent)

GC operates only on **closed** transaction-time ranges and only under
explicit retention policy per entity (e.g. "attendance history: keep 7
years, then archive"). Workflow:

1. scan partitions for `tt_to < cutoff`;
2. move rows to cold archive (encrypted) and record the archive manifest in
   `temporal_snapshots`;
3. drop the detached partition;
4. **no irreversible deletion ever happens without a manifest** — restore
   from archive is always possible.

GC is a background worker (`workers.py`), rate-limited, transactional, and
fully idempotent (resumable after a crash).

---

## 8. Capabilities mapped to the requirements

| Requirement | Mechanism |
|---|---|
| Every table temporal | `TemporalMixin` + generated `*_history` per table (registry-driven) |
| Edit stores old/new/ts/actor/reason/txn | `txn_log` + `change` envelope + `actor_id`/`reason` on history rows; committed atomically |
| AS OF queries | QueryRewriter at the ORM layer; `temporal_at()` for SQL; session context for "the whole app" |
| Historical relationships | joins rewritten per table — a student's class, fees, attendance all resolve AS OF |
| Historical reports | report queries rewritten; `students_as_of` views + columnar history make aggregates fast |
| Historical attendance / fees / permissions | each domain table is bitemporal; permission lookups read the role/campus graph AS OF |
| Historical dashboards | KPI queries inherit the time context — the dashboard re-renders the historical state |
| Historical search | the search index (see §8.5) is temporal; results respect AS OF |
| Undo / redo | transaction-time travel via close-open + `parent_txn` |
| Point-in-time restore | base snapshot + txn replay into a new branch |
| Historical analytics | aggregates over history (columnar) |
| Version comparison | diff two versions' `change` envelopes |
| Diff visualization | UI compares `old`/`new` JSONB (field-level, see §8.6) |

### 8.5 Temporal search

The universal search index (the local FTS5 mirror) is **regenerated from the
AS OF state** when a time context is active: the search worker re-syncs the
index projection from `temporal_at(entity, context)` instead of the current
tables. This is a *projection switch*, not a new index — the FTS5 schema is
unchanged, only the source rows are historical.

### 8.6 Version comparison & diff

- **API:** `GET /api/history/{entity}/{id}/versions` → timeline;
  `GET /api/history/{entity}/{id}/diff?v1=ts&v2=ts` → `{field: {old, new}}`.
- **UI:** a version timeline rail on detail pages; selecting two versions
  renders a field-level diff (side-by-side + inline "old → new"), reusing the
  Ledger's diff styling.

---

## 9. Performance

1. **Zero cost for normal use** — no time context = current-table queries,
   byte-identical to today. Temporal columns add one NULLable check per row.
2. **AS OF is index-bound** — GiST containment is O(log n); a 10-year
   history partition still answers "as of" in single-digit ms for an entity.
3. **Write amplification is controlled** — one UPDATE (close) + one INSERT
   (new) + one history INSERT per changed row, all in one transaction; the
   exclusion constraints validate overlap at insert time only (no full scan).
4. **History is write-once** — no in-place updates, so no dirty-page churn on
   old partitions; PG's index bloat stays flat.
5. **Columnar/partitioned history** for report-time AS OF keeps aggregates
   over millions of versions in seconds, not minutes.
6. **The hot-path guardrail**: every AS OF request is measured; if a query
   planner picks a scan over a range lookup (visible in `EXPLAIN`), the
   missing index is raised as a release-blocking defect — temporal queries are
   *expected* to be index-bound.

---

## 10. Migration strategy

**Phase A — substrate (no schema change to business tables).**
`txn_log`, `temporal_snapshots`, the engine package, session hook. Existing
`audit_logs` stays untouched.

**Phase B — per-table enablement (one Alembic migration per domain).**
For each table (students → attendance → fees → …):

1. `ALTER TABLE ADD COLUMN vt_from, vt_to, tt_from, tt_to` (defaults
   backfill: `vt_from = created_at`, `vt_to = NULL`, `tt_from = created_at`,
   `tt_to = NULL`);
2. create `*_history` mirror + copy current rows (backfill = the first
   version);
3. create GiST/btree indexes + exclusion constraints;
4. flip the domain's repository to `TemporalRepository` (close-open writes);
5. leave `updated_at` in place (denormalized convenience) but stop hand-writes.

**Phase C — backfill from existing audit (optional, per domain).**
Where `audit_logs.before_state/after_state` exist and are reliable, the
migration replays them as early history versions, so AS OF works before the
enablement date. This is a best-effort reconstruction — the Archive is
authoritative from enablement forward.

**Phase D — read-side cutover.** Domain endpoints begin passing the time
context; the UI gains the "view system as of" picker; reports/dashboards
inherit it.

**Backwards compatibility:** every domain keeps its existing API shape; the
temporal change is *behind* the repository. Old clients that never send a
time context see identical behavior. Rolling back = revert the migration
(history tables are additive; current tables keep their data).

---

## 11. Security

1. **History is sensitive.** `*_history` and `txn_log` carry actor, reason,
   and full before/after data. Access is governed by the same RBAC engine as
   live data, **plus** a `history.read` / `history.export` permission that is
   granted explicitly (rarely to non-admins).
2. **AS OF is not a bypass.** The rewriter applies the *current* permission
   context to historical rows — a teacher can see a student's history, not
   another campus's, and not fee records they cannot view today. Permissions
   themselves are temporal (§8.3), so "who could see what then" is also
   answerable — but *current* policy always gates *current* access.
3. **Actor & reason are tamper-evident.** `txn_log` is append-only with no
   UPDATE/DELETE grants; history rows are immutable (enforced by DB grants +
   the engine's never-write-past rule).
4. **Cold archives are encrypted** (KMS-managed keys), checksummed, and
   access-logged; restore requires `history.restore` + `snapshot.read`.
5. **Restore and undo are audited** as privileged operations (existing audit
   domain records the operation, the scope, the requester, and the new
   `parent_txn`).
6. **Tenant isolation is preserved** — every history partition and txn row
   carries `campus_id`; all temporal queries route through the scoped
   repository, exactly like live data.

---

## 12. Event flow — temporal × outbox

The existing transactional outbox remains the durability substrate; the
temporal engine publishes into it:

```
  write request ──► TxnManager (close-open, txn_log row)
        │
        ├── commit (atomic: current + history + txn_log)
        │
        ├── EventBridge: entity versioned → outbox event
        │     (student.updated.v2 with version_ts, txn_id)
        │
        └── background worker:
              ├── notifications / workflows (existing handlers)
              ├── search re-sync (current or AS OF projection)
              └── snapshot inker (record version for restore base)
```

Sequence (AS OF read):

```
  UI "view system as of 2024-06-15"
    │  setTimeContext(as_of)        API /api/time {context}
    ▼
  request list students             GET /api/g/student?as_of=...
    ▼
  TemporalRepository.list(filters, as_of)
    │  QueryRewriter: students → students_history
    │    + tstzrange(tt_from, tt_to) @> '2024-06-15'
    │  (permission mask applied to the result set)
    ▼
  renderer (React / CustomTkinter)  → historical list, banner "viewing
    as of 15 June 2024 · read-only · exit to return to live"
```

---

## 13. Folder structure (recap + runtime layout)

```
apps/api/app/temporal/           §2 — engine, repository, rewriter, snapshots,
                                      compression, gc, api, workers
apps/api/alembic/versions/       §10 — temporal enablement migrations
apps/web/src/features/time/      UI: as-of picker, history rail, diff view
apps/desktop/src/features/time/  CustomTkinter equivalents (The Forge desktop)
infrastructure/                  snapshot archive target config (S3-compatible)
```

---

## 14. Implementation milestones

| # | Milestone | Deliverable | Exit criterion |
|---|---|---|---|
| M1 | Engine core (2–3 wk) | `temporal/` package: TimeContext, TxnManager, envelope, txn_log migration | one hand-run close-open write produces current + history + txn rows atomically |
| M2 | Rewriter (3–4 wk) | ORM query rewriting + `temporal_at()` | AS OF query returns historical row via GiST, EXPLAIN shows index-bound plan |
| M3 | Students enablement (2 wk) | full Phase B for `students` + Timeline/diff API | UI shows "as of" state; diff endpoint works |
| M4 | UI (3 wk) | as-of picker + history rail + diff view (web), banner, read-only enforcement | "view system as of" flows through lists/detail/reports for students |
| M5 | Broad enablement (6–8 wk) | attendance, fees, academic, admissions per Phase B | AS OF across 6+ domains |
| M6 | Snapshots + undo/redo (4 wk) | base + txn replay restore, undo/redo chain | point-in-time restore to a branch; undo→redo→undo audit chain |
| M7 | Compression + GC (3–4 wk) | partitions, TOAST, cold archive, retention worker | detached old partitions, manifest-driven restore works |
| M8 | Historical analytics/reports (4 wk) | columnar history, report AS OF, temporal search | historical dashboard + search return AS OF data at budget |
| M9 | Hardening (4 wk) | perf guardrails, security audit, backfill from audit, docs | the §8 capability matrix is demonstrably true in QA |

---

## 15. Acceptance criteria

- **The flagship requirement:** selecting 15 June 2024 changes *every*
  surface — lists, detail, relationships, reports, attendance, fees,
  permissions, dashboards, search — and a persistent banner marks read-only
  mode.
- Every edit produces old/new/timestamp/actor/reason/txn_id committed
  atomically (verified by fault injection: crash between close and insert
  leaves no torn state — the txn either fully committed or rolled back).
- `AS OF` queries are index-bound (EXPLAIN gate in CI).
- Undo/redo chains are fully reversible and fully audited.
- Point-in-time restore targets a branch, never mutates live tables, and is
  reversible.
- No history row is ever silently deleted; GC only archives under policy with
  a manifest.
- The `audit_logs` table remains the security record, unchanged in contract;
  the temporal layer is a new substrate beneath it, not a replacement.
- 60fps/≤300ms budgets from The Ascent hold in historical mode (the AS OF
  dashboard renders at the same budget as the live one).
