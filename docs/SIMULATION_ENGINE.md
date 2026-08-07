# SDMAS - Enterprise Simulation Engine

This document describes the **intended** "what happens if…" simulation
engine for SDMAS v2. It inherits the deterministic design philosophy already
established by `domains/risk` (see `risk/rules.py` and `risk/evaluator.py`):
*no prediction, no machine learning, no randomness*. Every consequence is a
pure, reproducible function of persisted school data plus scenario inputs.

Status: **design spec with a working core example.** Not yet wired into the
API.

Implementation status (see the Roadmap for the full plan):

| Piece | State |
|---|---|
| Scenario / Lever model — all 7 product-brief levers (`model/scenario.py`, `model/lever.py`) | Implemented |
| Baseline snapshot — teachers, fleet, rooms, schedule, baselines (`snapshot/snapshot.py`) | Implemented |
| Coefficient registry — all nine models (`coefficient/registry.py`) | Implemented |
| DAG engine (`engine/dag.py`, `engine/default_graph.py`) | Implemented |
| Revenue forecast (`forecasts/revenue.py`) | Implemented |
| Budget forecast with full cost lines (`forecasts/budget.py`, DAG reuse) | Implemented |
| Workload / attendance / dropout / rooms / transport / performance / resource forecasts | Implemented |
| Comparison — deltas, direction, flags, composite score (`engine/compare.py`) | Implemented |
| Persistence, tenancy guards, API router, worker runner, visualization | Spec only |

## 1. Purpose & scope

The engine answers forward-looking questions of the form

> *"What happens if <I change one or more school parameters>?"*

without ever letting a chance/subjective model produce a result. Given the
same baseline snapshot and the same scenario, the engine must produce the
*identical* output on every run, on any machine, for any tenant.

Example scenarios the engine models (input *levers*):

| Scenario | Levers changed |
|---|---|
| Raise tuition 7% | `fee_scale.tuition` multiplier ×1.07 |
| Remove a teacher | remove membership in `teacher_capacity` |
| Add two buses | `transport.fleet +2` |
| Change school timing | `schedule.day_start`, `periods_per_day`, `period_minutes` |
| Reduce class size | `section.capacity` cap → rebalancing |
| Increase scholarships | `scholarship_pool` increase + `fee_discount` eligibility |
| Merge classes | remove one `class`/`section`, reassign students |

The engine then forecasts the *consequence metrics* list:

- Revenue impact
- Teacher workload
- Attendance prediction
- Dropout probability
- Budget impact
- Room utilization
- Transport load
- Student performance
- Resource utilization

## 2. Non-negotiables

1. **Deterministic, not predictive.** No sampling, no stochastic terms, no
   learned weights. Each forecast is an affine/step function over persisted
   data multiplied by a **coefficient registry** (defaults seeded with an
   admin-overridable per-tenant overrides, like `risk_rule_configs`).
   Coefficients are just data — never trained.
2. **Snapshot, not live querying.** A scenario runs over a frozen
   `SimulationSnapshot` (a copy of the relevant fields at a point in time),
   never over the mutable OLTP tables. This is what makes rollback and
   cross-run reproducibility possible and keeps heavy runs off the live DB.
3. **Tenancy is preserved.** A snapshot belongs to `campus_id`/`institution_id`
   and every scenario/result row is tenant-scoped the same default-deny way as
   `multi_tenant`/`TenantScopedRepository`; results can never leak across
   campuses.
4. **Audited.** Running a scenario is a mutating, money-related planning act;
   it is written to the audit log like any other operation.

---

## 3. Core objects

New package: `apps/api/app/simulation/`.

```
simulation/
  snapshot/         snapshot.py  (baseline snapshot builder)
  model/            scenario.py, context.py, lever.py, consequence.py
  coefficient/      registry.py  (per-model deterministic coefficients)
  engine/           dag.py, default_graph.py, compare.py
  forecasts/        revenue.py, workload.py, attendance.py, dropout.py,
                    budget.py, rooms.py, transport.py, performance.py,
                    resource.py, common.py (band helpers)
  persistence/      scenario_repo.py, run_repo.py, rollback.py
  orchestration/    runner.py, parallel.py, compare.py, lock.py
  writer/           results.py, viz.py, exporters.py
  rules.py          deterministic forecast definitions (like risk/rules.py)
```

### 3.1 Scenario object

A scenario is a declarative, validated set of inputs (JSON-serialisable):

```
Scenario
  id, campus_id, name, description, author_user_id
  base_snapshot_id
  levers: list[Lever]          # the "if..." change
  horizon: Horizon             # term / semester / months ahead
  assumptions: dict            # coefficient overrides scoped to this scenario
  status: draft | validated | queued | running | ran | rolled_back
  created_at, version
```

A **`Lever`** is a typed mutation of one baseline element:

```python
Lever = Union[FeeMultiplier, RemoveTeacher, AddBuses, ChangeSchedule,
              ClassSizeChange, ScholarshipDelta, MergeClasses, ...]
```

Each lever declares: `target` (what it changes), `delta` (the numeric/boolean
change), and a pure **application function** `apply(baseline) → ScenarioContext`,
i.e. the lever produces the *changed* school state. It never
consults the DB — it operates purely on the snapshot passed to it.

A **`Lever`** describes the change; the **`Context`** produced by applying
levers to a snapshot is the only input that subsequent forecast models read.

### 3.2 Baseline snapshot

`SimulationSnapshot` freezes a minimal, deterministic projection of the
school:

- Students (count per class/section, fee liability, tier).
- Teachers (assignment, load, salary).
- Classes/sections (enrollment, capacity, schedule).
- Rooms (capacity, timetable occupancy), Bus fleet & routes.
- Tuition/fee rate sheet + scholarship eligibility population.
- Attendance & performance baselines by class.

Serialized as JSONB (idempotent hash as snapshot_id). Building a snapshot is a
batch(es) SQL read — no N+1, mirroring `risk/evaluator.py`'s set-based
approach — and commits once so all later runs share one byte-identical base.

---

## 4. Consequence forecast models (deterministic)

Every forecast is a **pure function** `model(ctx: SimulationContext) -> Metric`,
where `ctx` = snapshot + applied levers. Coefficients come from the registry
(see §11). Randomness is impossible: there are no random sources in any model.

### 4.1 Revenue impact
```
revenue = Σ_grade fee_rate[grade] × enroll[grade]
        − scholarships_granted
        − expected_collection_loss (attrition-adjusted recovery)
```
Deterministic inputs: enroll (context), fee_rate (context/registry), pool of
scholarship (context), collection-recovery ratio (registry coefficient).

### 4.2 Teacher workload
```
load[teacher] = Σ (service_hours × students_in_section)
              + administrative_fixed (registry)
utilization = load / load_capacity (registry)
```
Removing a teacher (lever) redistributes that teacher's sections to peers with
remaining capacity ≥ needed time — using a **deterministic assignment priority**
(tenure descending). If no teacher can absorb it, the engine returns an
explicit "over capacity" flag rather than a forced number.

### 4.3 Attendance prediction
```
expected_attn[class] = base_attn[class]
                    + Δ_timing(schedule_model)       # schedule-change multiplier
                    + Δ_transport(bus_fleet, distance)  # transport-catchment
                    + Δ_class_size(class_size_effect)
```
The `Δ_*` terms are lookup tables (coefficient registry) keyed by schedule
band / fleet delta / class-size band. Deterministic given the context.

### 4.4 Dropout (retention) probability
Derives from the existing **risk score** already computed by `domains/risk`,
plus an explicit economic-pressure term:
```
dropout_prob = clamp( base_risk_pct
                    + fee_pressure (from tuition/scholarship levers)
                    − retention_bonus (from scholarship increase),
                    0, 100 )
```
`base_risk_pct` is the persisted deterministic risk score — no new model is
invented; the engine just links forecasting to the school's own risk numbers.

### 4.5 Budget impact
```
budget_Δ = revenue_Δ                       (from §4.1)
         + cost_change(teachers)           # hire/rebalance per removed
         + cost_change(fleet)              # new buses + maintenance
         + cost_change(rooms, schedule)    # operating cost
         + scholarships_costΔ
```
Each cost line uses public salary/fuel/overhead table coefficients.

### 4.6 Room utilization
```
avail_periods = rooms × periods × day_length
used = Σ class utilization per required periods
util = used / avail_periods  (peak_period: max over sliding window)
```

### 4.7 Transport load
Deterministic assignment of students → routes → buses; then:
```
util = assigned / (seats × buses + added_buses)         # seat ratio
midday_peak = max load on any single bus
```
When `assigned > capacity`, engine flags "insufficient fleet" (does not fake
a number).

### 4.8 Student performance
Deterministic band table (class-size effect, hours effect, stability effect):
```
Δperf[class] = coeff[band_of_new_capacity] + Σ_hrs_effect
perf[class] = base_perf[class] + Δperf (capped 0-100)
```
Same input → same output; coefficients are copied-not-learned.

### 4.9 Resource utilization
Composite, weighted aggregation over room/teacher/fleet utilization produced
above, grouped per resource category with explicit, documented weights.

---

## 5. Dependency graph & scheduler

Forecast models are wired into a dependency **DAG** derived from each model's
declared inputs. Execution order is guaranteed by a topological sort, so the
result is correct even when a lever changes a model's inputs:

```
                 baseline_snapshot
                       │
        ┌──────────────┼───────────────────────┐
   revenue        workload                attendance
        │              │                        │
        ├─ budgetΔ     ├─ rooms          ┌─────┴──────┐
        │              │                 │            │
   budgetΔ← revenueΔ+costs(workload,fleet,rooms)
   resource ← util(workload, rooms, fleet)
   dropout ← retention(fee_pressure) + risk;  performance ← class-size/hours
```

- Each node declares `inputs: list[metric_id]`.
- A **cycle check** rejects intrinsic cycles at define-time.
- A **topological scheduler** walks nodes, computing each metric exactly once;
  a metric reads only already-computed results or the frozen context.
- **Cut set**: any metric that depends only on context (no other consequence)
  is a *root*; only roots read the snapshot.

The DAG is metadata (list of metric `entry` + `depends_on`); the engine is a
generic executor. Adding a model = adding a node + its coefficients; no change
to the runner.

---

## 6. Scenario lifecycle & rollback

```
draft → validated → queued → running → … → ran
                                        └→(cancel) failed/stopped
```

1. **Snapshot** built (once) if missing from baseline at scenario creation.
2. **Validate** — levers are checked against snapshot invariants (e.g. can't
   remove the last proportional teacher; capacity ≥ enroll). Invalid → 422
   with the failing reason.
3. **Dry-run** — a no-commit preview returns forecasts without persisting run
   output.
4. **Run** — engine produces `SimulationRun` + `MetricResult` rows, all
   committed in one transaction (deterministic, so idempotent).
5. **Rollback** — because runs never touch the live DB and only write
   immutable result rows, "rollback" is trivial: discard the run rows. An
   optional one-step live **apply** (write-back) is strictly gated behind a
   separate explicit permission and logged to audit; `apply` is reversible by
   removing the run and reverting the audit-trailed changes.

No scenario ever mutates school data. That is the core guarantee. "Rollback"
is simply never having applied in the first place (runs are pure), or an
audit-trailed reversal of a prior explicit `apply`.

---

## 7. Parallel simulations

- Runs are **independent** (read-only over a frozen snapshot), so they are
  trivially parallelisable.
- **Async**: `engine/parallel.py` uses `asyncio` concurrency within a run
  (DAG layers in parallel).
- **Out-of-band**: a scenario triggering many metrics is dispatched to the
  existing **worker process** (jobs table) so web API stays responsive; the
  API posts a `SimulationJob` and the client polls/streams the run.
- **Multi-run**: a batch `compare` launches N scenario runs concurrently;
  each writes only its own result rows, so results are never merged in
  memory — they are compared from persisted rows.
- Deterministic means shared reads are safe for the pure engine; no locks
  needed on snapshots.

## 8. Comparison

- Any scenario can be compared to **baseline** or another scenario of the
  same `base_snapshot_id`.
- `ComparisonReport(id, base_run, against_run, deltas[])`:
  - per-metric absolute + relative diff (relative uses `abs(base)` so the
    sign reflects direction even when the baseline is negative),
  - **direction** (up/down/neutral) per consequence,
  - flagged "constraint violation" (over-capacity rooms / workloads / fleet),
  - a single **composite score** = documented signed weighted sum of
    relative deltas (clamped to ±1), with weights from the coefficient
    registry (`comparison_weights`).
- Comparisons are stored, immutable, and can be re-rendered (tables,
  waterfall) without recomputing the metrics.

## 9. Visualization

Read-only `GET /api/simulation/...` endpoints returning structured data the
frontend renders (React/force-chart, mobile):

- `GET …/scenario/{id}/run/{run_id}/metrics`
- `GET …/scenario/{id}/compare?against={run_id}` → deltas + waterfalls
- `GET …/scenario/{id}/sensitivity` → one-factor sweep result table
- Exporters: `csv`, `json`, `png`(chart card), `pdf` report — gated by the
  existing export permission.

Visual elements: metric vs baseline, delta arrows, per-class drilldown,
capacity breach flags, and a dependency "impact tree" drawn from the DAG.
All feeds are pure JSON of already-computed metrics — the client renders
only, never re-figures numbers.

## 10. Performance

- **Batch reads** for snapshot (one/two set-query, modelled on
  `risk/evaluator.py`).
- **Immutable snapshot**: a run never contends for live tables; long runs
  cost the DB nothing beyond the initial snapshot.
- **DAG reuse**: a metric computed once is memoised; a changed lever only
  invalidates downstream metrics.
- **Coefficient registry** resolved once per run into a flat dict.
- **Caching**: plan/compare results scheduled in Redis keyed by
  `(scenario, run_ids, version)`; snapshot hashes comparable to validate.
- Runs stored as JSONB rows; `pg` aggregations aggregate over the compact
  metric result table rather than scanning payload blobs.

## 11. Architecture

```
Web / Mobile ─► /api/v1/simulation/* (tenancy-guarded, audit)
                     │
        ┌────────────┴──────────────────────────┐
   Scenario Service               Job enqueue (worker) for heavy
        │                        └─ SimulationRunner (async / parallel)
   Engine (DAG executor)
        │                                     │
  Forecast metric models ───── coefficients registry ─── overrides / ceiling
        │                                     │
   SimulationSnapshot (JSONB)             SimulationResult rows (immutable)
        │
   Baselines built batching from PostgreSQL (source of truth)
```

No new runtime deps required for the core. Optional `orjson` for fast JSONB
serialization. Runs live in the worker; light scenarios can run in-process.

---

## 12. Roadmap

Phase 1 – core model & pipeline
- Snapshot builder + Scenario/Lever model + DAG engine.
- The three revenue core metrics (revenue, workload, budget).
- Persistence: snapshot/run/result tables, Alembic migration, tenancy
  scoping + audit.

Phase 2 – full metric set + comparison
- Remaining consequence models (attendance, dropout, rooms, fleet,
  performance, resource).
- Scenario vs baseline comparison + sensitivity sweep.
- Batch compare, unit tests on a deterministic fixture school.

Phase 3 – operation & scale
- Worker async runner + parallel batch runs.
- Redis result caching, `pg_trgm` query path, in-process preview.
- Rollback/apply gate + audit trace.

Phase 4 – product surface
- Visualization (metric cards, waterfall, impact tree).
- Exporters (csv/JSON/report).
- Coefficient registry admin UI (per-tenant overrides).

## 13. Testing (determinism guarantee)

Implemented now:

- **Golden tests** (`test_revenue.py`, `test_models.py`): every model on the
  canonical fixture school; exact float pins (e.g. revenue 8,325,750.0,
  workload utilisation 0.7567) plus run-twice exact-equality for the full
  nine-metric run.
- **Lever semantics** (`test_levers.py`): each lever's pure effect on the
  snapshot, validation failures, and that levers never mutate the source.
- **Capacity flags** (`test_models.py`): over-capacity workload, insufficient
  fleet, transport shortfall, insufficient rooms — flagged, never faked.
- **Comparison** (`test_compare.py`): deltas, direction, composite score,
  flag propagation, determinism.
- **DAG tests**: cycle rejection, unknown dependency rejection, topological
  ordering (budget reads upstream metric breakdowns).

Spec only (phases 2–4):

- **Persistence tests**: two runs of the same scenario produce byte-identical
  metric rows.
- **Tenancy suite**: a `test_simulation/test_tenancy.py` proving cross-campus
  scenario/result isolation (mirror the existing multi-tenant security suite).
- **No-AI audit**: a lint-style test asserting no model module imports any
  stochastic/ML dependency.

## Related docs
- [`risk/rules.py`](apps/api/app/domains/risk/rules.py) — the deterministic
  rule style this layer and the school built on.
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`TENANCY.md`](TENANCY.md)