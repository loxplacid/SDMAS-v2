# SDMAS — Enterprise Optimization Engine

This document describes the **intended** optimization engine for SDMAS v2: a
**generic constraint solver** built on **Google OR-Tools CP-SAT**. It is
deliberately *not* a timetable generator — timetabling is just one of the
problem domains it can express. The same engine solves room allocation, exam
scheduling, bus routing, teacher allocation, hostel allocation, invigilation
and sports scheduling, because all of them reduce to the same three things:
**decision variables, constraints, and an objective**.

The engine follows the deterministic, tenancy-preserving, audited design
philosophy already established by `domains/risk` and `app/simulation`: pure
problem definitions in, reproducible schedules out. CP-SAT is deterministic
given a fixed model and seed, which lets us golden-test schedules the same way
the simulation engine golden-tests forecasts.

Status: **design spec with a working core example.** Not yet wired into the
API. OR-Tools is deliberately deployed only in the **worker process** (heavy
native dependency); the web API never imports it.

Implementation status (see the Roadmap for the full plan):

| Piece | State |
|---|---|
| Variable model + named registry (`core/model.py`) | Implemented |
| Constraint abstraction, hard/soft, gateable (`core/constraints.py`) | Implemented |
| Objective functions incl. lexicographic (`core/objective.py`) | Implemented |
| Solver facade: time limits, parallel workers, warm starts (`core/engine.py`) | Implemented |
| Conflict explanation via assumption cores (`core/explain.py`) | Implemented |
| Problem adapter protocol (`adapters/base.py`) | Implemented |
| Invigilation adapter — working example (`adapters/invigilation.py`) | Implemented |
| Timetable / room / exam / bus / teacher / hostel / sports adapters | Spec only |
| Persistence, tenancy guards, API router, worker runner | Spec only |
| Benchmark suite, visualization, simulation mode | Spec only |

## 1. Purpose & scope

The engine answers questions of the form

> *"Given the school's data and these rules, produce the best schedule."*

where "best" means: satisfy every **hard constraint** (rules that must hold)
and minimise the weighted sum of **soft-constraint violations** (rules we
strongly prefer). Supported problem domains (all built on the same core):

| Domain | Decision variables | Typical hard constraints | Typical soft constraints |
|---|---|---|---|
| Timetables | class × period × room | teacher clash, room clash, teacher availability | lunch spacing, subject priority |
| Room allocation | meeting × room | capacity, lab requirement | minimising corridor walking |
| Exam scheduling | exam × slot × room | no two exams per student clash, room capacity | spread exams, morning preference |
| Bus routing | stop × bus / route order | capacity, stop windows, depot return | transport timing, sibling grouping |
| Teacher allocation | teacher × section | availability, max weekly periods | workload balance, subject match |
| Hostel allocation | student × bed | gender/block rules, sibling separation | preferences, proximity |
| Invigilation | exam × teacher × room × slot | capacity, no teacher clash, unavailability | balanced load, subject match |
| Sports scheduling | match × pitch × slot | team clash, pitch availability | rest days, home/away fairness |

The engine is **generic**: a new domain is a new *problem adapter* that
declares variables, constraints and an objective against the core — no engine
changes. Domain vocabulary (exam, bus, match) never leaks into the solver
layer; the adapter translates in and translates back out.

## 2. Non-negotiables

1. **CP-SAT, nothing else.** Every problem is modelled as an integral
   CP-SAT program: boolean/int/interval variables, linear and reified
   constraints, and a linear objective. No custom branch-and-bound, no
   heuristics-as-solver. Heuristics may *warm-start* the solver (solution
   hints) but never replace it.
2. **Deterministic and reproducible.** The same problem definition + the same
   `SolveParams` (notably `random_seed` and worker count) must yield the same
   schedule on any machine, for any tenant. This is the contract that makes
   golden tests, benchmarking and audit replay possible.
3. **Worker-process isolation.** `ortools` (a large native wheel) is imported
   only by the existing **worker** job runner. The web API enqueues a job and
   polls; it never loads the solver. Small instances may run in-process behind
   the same interface, but the deployment contract is the worker.
4. **Tenancy is preserved.** Every optimization job, input and result row is
   tenant-scoped the same default-deny way as `multi_tenant` /
   `TenantScopedRepository`. A problem built for one campus can never leak
   another campus's data into its constraints.
5. **Audited.** Running an optimization is a planning act with real-world
   consequences; job submission, solves, published results and any
   write-back are written to the audit log.
6. **The solver never writes the DB.** Solves are pure: inputs are a frozen
   problem snapshot (see §11 simulation mode), outputs are immutable result
   rows. Publishing a schedule to live tables is a separate, gated,
   audit-trailed step.

## 3. Core objects

New package: `apps/api/app/optimization/` (mirrors the `app/simulation`
layout: pure core in, adapters out).

```
optimization/
  core/
    model.py        ModelBuilder, Domain, named variable registry
    constraints.py  Constraint (hard/soft/weight/gate) + global constraints
    objective.py    Objective (weighted terms), lexicographic levels
    engine.py       SolveParams, SolveResult, SolverEngine (+ warm starts)
    explain.py      ConflictExplainer → ConflictReport (assumption cores)
  adapters/
    base.py         ProblemAdapter protocol (build / interpret / hints / relax)
    invigilation.py working example: exams × rooms × slots × teachers
  persistence/      job/run/solution repos, result rows      (spec only)
  orchestration/    worker job adapter, async runner          (spec only)
  writer/           visualization feeds, exporters            (spec only)
```

### 3.1 The pipeline at a glance

```
           problem definition (adapter)          SolveParams (budget/seed/workers)
                    │                                          │
   ┌────────────────┴────────────────┐     ┌───────────────────┘
   │ ModelBuilder (variables,        │     │
   │ constraints, objective)         │     │
   └───────────────┬─────────────────┘     │
                   ▼                       ▼
           SolverEngine.solve ──────► CP-SAT (worker)
                   │                       │
                   ▼                       ▼
            SolveResult            ConflictExplainer (if infeasible)
           (status, objective,           │
            solution, stats)             ▼
                   │               ConflictReport (names + relaxations)
                   ▼
        adapter.interpret(solution) → domain-shaped JSON
```

## 4. Constraint abstraction

A constraint is a **named, documented rule** with a hard/soft nature and a
weight:

```python
@dataclass(frozen=True)
class Constraint:
    name: str            # stable id: "room_capacity_3", "load_T4", ...
    description: str     # human sentence, surfaced in explanations & UI
    hard: bool = True    # False → contributes `weight * term` to objective
    weight: float = 0.0
    term: object | None  # penalty expression for soft constraints
    gate: object | None  # assumption literal (explanation mode only)
```

The builder exposes **global constraints** that map 1:1 to CP-SAT
propagators — never hand-rolled loops for the common cases:

| Builder method | CP-SAT behind it | Used for |
|---|---|---|
| `exactly_one(lits)` | `sum == 1` | each exam has one teacher; each class one room |
| `at_most_one(lits)` | `sum <= 1` | optional resource exclusivity |
| `all_different(vars)` | `AddAllDifferent` | no two exams in same room+slot; unique beds |
| `no_overlap(intervals)` | `AddNoOverlap` | classes in a room over the day; matches on a pitch |
| `allowed_assignments(var, values)` | `AddAllowedAssignments` | room capacity, lab requirements, unavailable slots |
| `only_if(expr, lits)` | reified `OnlyEnforceIf` | "teacher T is never double-booked": `slot(e1) != slot(e2)` if T invigilates both |
| `forbid_true(bool)` | `x == 0` | teacher unavailable; holiday slot closed |
| `soft_excess(expr, bound, w)` | `max(0, expr - bound)` penalty | max weekly periods, lunch spacing overflow |
| `soft_term(expr, w)` | raw weighted objective term | preference mismatch penalties |

### 4.1 Hard vs soft

- **Hard constraints** must hold; a model with any violated hard constraint
  is infeasible. In explanation mode every hard constraint is additionally
  gated by its own assumption literal (see §7) so infeasibility can be
  dissected.
- **Soft constraints** never make the model infeasible: each one declares a
  non-negative *penalty expression* that enters the objective weighted by
  `weight`. The solver trades soft violations off against each other exactly
  as the weights say.

### 4.2 The example catalog

Every example constraint from the product brief maps onto the vocabulary
above (hard unless noted):

| Example | Domain | Encoding |
|---|---|---|
| Teacher unavailable | Timetable, Invigilation | `forbid_true(x[teacher, assignment])` (hard) |
| Maximum weekly periods | Teacher allocation, Timetable | `soft_excess(Σ weekly_periods[teacher], cap, weight)` |
| Room capacity | Room allocation, Exams | `allowed_assignments(room[e], rooms where cap ≥ students)` |
| Lab requirements | Timetable, Room allocation | `allowed_assignments(room[c], rooms where has_lab)` |
| Subject priority | Teacher allocation, Invigilation | `soft_term(1 − x[exam, preferred_teacher], weight)` |
| Lunch spacing | Timetable | gap: `only_if(start_after ≥ lunch_end, ...)` on consecutive intervals |
| Holiday rules | Exams, Timetable | prune slots: `allowed_assignments(slot[e], non_holiday_slots)` |
| Sibling constraints | Transport, Hostel | reified implications: same bus / same block via `only_if` |
| Transport timing | Bus routing | `soft_excess(arrival_time − window_end, 0, weight)` |
| Penalty weights | all | objective term weights (integral scaling, §6.3) |
| Hard constraints | all | gateable, explanation-backed (§7) |
| Soft constraints | all | weighted penalty terms (§6) |

## 5. Variable model

Adapters declare decision variables through `ModelBuilder`, which owns one
`CpModel` and a **name-indexed registry**. The registry is what decouples the
adapter from the solver: the engine applies hints and extracts solutions by
name, and every variable name is stable, debuggable, and JSON-addressable.

| Variable kind | CP-SAT type | Used for |
|---|---|---|
| `bool_var(name)` | `BoolVar` | assignments: `x[exam, teacher]` |
| `int_var(name, Domain(lower, upper))` | `IntVar` | slots, rooms, loads, arrival times |
| `interval_var(name, start, duration)` | fixed-size `IntervalVar` | classes, bus trips, matches |

Modeling rules enforced by the design:

- **Tight domains.** A slot index is `Domain(0, n_slots-1)`, never a wide
  range; wide domains slow propagation and enlarge the search space.
- **Prefer booleans for assignment, integers for selection.** An exam's room
  is an `IntVar` over room ids; *whether* teacher T invigilates exam E is a
  `BoolVar`.
- **Composed keys for exclusivity.** "No two exams in one room at one slot"
  is one `all_different(slot[e] * n_rooms + room[e])`, not a loop.
- **Only integral arithmetic.** CP-SAT is integral; distances, durations and
  money are scaled by a documented multiplier before modelling (and
  un-scaled in `interpret`).

The working core implements the registry (`decision_vars` for bool/int vars,
`interval_vars` structurally separate), duplicate-name rejection, and the
`hint_map(name→value)` bridge used by warm starts.

## 6. Objective functions

### 6.1 Weighted soft penalties

The default objective is

```
minimize Σ_k w_k · penalty_k
```

where each `penalty_k` is a non-negative linear expression (a violation
counter, an excess, a mismatch indicator). `soft_excess` builds the penalty
as `max(0, expr − bound)` via a dedicated violation variable — the solver
pulls it to its minimal feasible value, so it is exactly the violated amount.

### 6.2 Lexicographic objectives

Some decisions are categorical priorities (first: no hard violations; then:
balance load; then: honour preferences). `SolverEngine.solve_lexicographic`
runs objectives one at a time, and after each level adds
`model.Add(level_expr == optimum)` before optimising the next — strict
priority with no trade-off between levels.

### 6.3 Weights and integrality

Weights are rational numbers (`2.0`, `0.5`…) but must form an integral
objective; the builder scales by a fixed factor when needed. This is a
documented, testable convention — not something adapters may improvise.

## 7. Optimization pipeline

A solve is a pure function `(problem, SolveParams) → SolveResult`:

1. **Validate** — problem invariants (non-empty domains, capacity lists
   non-empty, teacher set non-empty) fail fast with a clear reason. The
   working invigilation adapter implements ``validate()`` (called at the
   start of ``build``); a future 422-style API layer reuses the same hook.
2. **Build** — the adapter declares variables, constraints and objective on a
   `ModelBuilder`.
3. **Presolve** — CP-SAT's built-in presolve prunes fixed variables and
   redundant constraints (reported in solve stats for benchmarking).
4. **Solve** — the engine configures the solver from `SolveParams`:
   - `time_limit_seconds` — wall-clock budget (interactive tooling: seconds;
     overnight batch: minutes),
   - `num_search_workers` — parallel portfolio workers,
   - `random_seed` — determinism anchor,
   - `stop_after_first_solution` — TTFS-first mode (see §10),
   - `log_search_progress` — off by default, on for debugging.
5. **Extract** — `SolveResult` carries status (optimal / feasible /
   infeasible / unknown), objective value + best bound, wall time, conflict
   and branch counts, and the named solution (if any).
6. **Interpret & persist** — the adapter converts the raw `{name: value}`
   solution into domain-shaped JSON; results are stored as immutable rows,
   tenant-scoped and audited.

The status ladder: `OPTIMAL` (proven best), `FEASIBLE` (valid, gap to bound
non-zero), `INFEASIBLE` (→ conflict explanation, §8), `UNKNOWN` (budget
exhausted, best incumbent returned if any).

## 8. Incremental solving

School schedules are rarely built once. The engine treats every change —
a teacher resigns, a room is closed, a bus breaks down — as *repair over the
previous solution*:

- **Solution hints (warm starts).** `engine.solve(..., hints=previous_solution)`
  feeds `model.AddHint(var, value)` for every variable name both runs share.
  CP-SAT's repair phase keeps the parts that still satisfy the new hard
  constraints and re-optimises around them — dramatically faster than a cold
  solve and, critically, it produces schedules *close to the previous one*
  (fewer surprises for teachers and students).
- **Heuristic hints.** An adapter may offer `hints()` — a cheap greedy start
  (e.g. largest exam first, first free slot/room/teacher) — so even the first
  solve gets the speed and stability benefits. The greedy solution never
  constrains correctness; it only seeds the search.
- **Domain pinning.** For "freeze this week, re-plan next week", the adapter
  narrows variable domains to the already-fixed values instead of adding
  equality constraints — cheaper and trivially reversible.
- **Model reuse.** Because the builder is a thin registry over one `CpModel`,
  a repair run can *extend* the previous model (new constraints) rather than
  rebuild it, as long as no variable is deleted. The working core's
  incremental-repair test demonstrates this contract.

## 9. Conflict explanation

When a problem is over-constrained (common with real school data), the engine
must tell the user *which rules conflict*, not just "infeasible". Mechanism:

1. **Rebuild in gate mode** — `ModelBuilder(gate_hard=True)` adds each hard
   constraint reified by its own assumption literal
   (`ct.OnlyEnforceIf(gate_k)`), and the gates are declared on the model via
   `model.add_assumptions([...])`. Semantics are unchanged: every gate is
   asserted. Global constraints that cannot be reified directly
   (`all_different`, `no_overlap`, `allowed_assignments`) are decomposed
   exactly — pairwise inequality / pairwise ordering / one-hot indicator
   picks — behind the same gate.
2. **Ask CP-SAT for a proof** — on `INFEASIBLE`,
   `solver.sufficient_assumptions_for_infeasibility()` returns the variable
   indices of a *sufficient* subset of assumptions that alone prove
   infeasibility. These resolve back to constraint names via the builder's
   gate registry.
3. **Humanise** — `ConflictReport` lists the conflicting constraint names,
   and the adapter's `suggest_relaxations(conflicts)` translates them into
   domain language:

   > Model is infeasible. Conflicting constraints: `room_slot_conflicts`,
   > `unavailable_0_1`. Suggested relaxations: *Add a room, or schedule the
   > overlapping exams in different slots.* / *Allow teacher T2 to invigilate
   > exam Math, or add another invigilator.*

The core uses the "sufficient core" (fast); a *minimal* core can be obtained
by iterated re-solving with the core shrunk by one assumption at a time
(optional, budget-gated — the doc lists it as a roadmap refinement).

Because every hard constraint is named and described at build time, the
explanations stay accurate even as adapters grow — no string-parsing of
solver internals anywhere.

## 10. Visualization

Read-only feeds the frontend renders; the client never re-solves:

- `GET /api/optimization/jobs/{id}/solution` → adapter-shaped JSON
  (e.g. `{"assignments": [{exam, slot, room, teacher}, …]}`).
- **Timetable grid / Gantt** — render slot × resource cells from the
  interpreted solution; interval adapters (classes, bus trips) produce
  start/end data for Gantt rendering.
- **Conflict overlay** — when a job fails, the UI highlights the conflicting
  constraint names and shows the suggested relaxations inline, so an admin
  can edit data and re-run without a solver in the loop.
- **Objective breakdown** — per-soft-constraint penalty contributions, so
  "why is the score 6.0?" is answerable at a glance.
- Exporters (`json`, `csv`, `pdf` report) gated by the existing export
  permission, mirroring the simulation writer.

## 11. Simulation mode

Optimization and simulation are two sides of the same planning coin, and the
engine is designed to interoperate with `app/simulation`:

- The **baseline snapshot** the simulation engine already builds (`§3.2` of
  `SIMULATION_ENGINE.md`) becomes the *frozen problem input* for an
  optimization run — rooms, teachers, sections, fleet, hostel blocks.
- A **scenario lever** (remove a teacher, add two buses, change school
  timing) is replayed as a *constraint delta*: the optimization job rebuilds
  the problem from the modified snapshot and re-solves.
- The result is a **comparison**: schedule vs baseline-schedule — what moved,
  which soft penalties changed, whether the new fleet is sufficient (if the
  problem becomes infeasible, the conflict report *is* the "insufficient
  fleet" answer — the engine never fakes a number, same rule as the
  simulation engine).
- Heavy runs (full timetable + routing sweep) are queued on the worker like
  simulation jobs; the same job table, polling and audit path are reused.

This gives admins the "what if we drop one bus?" question a *concrete* answer:
either a re-planned route set, or an explicit conflict report saying the fleet
is insufficient and why.

## 12. Benchmarking

The engine must prove it scales before it ships. A benchmark suite ships with
the package:

- **Instance library** — fixed, checked-in problem instances per domain:
  small / medium / large (e.g. 6-exam invigilation up to a 400-class
  timetable; 20-stop bus routes; an 8-team sports round-robin). Instances are
  data, committed to the repo, and reproducible by construction.
- **Metrics** — recorded per run from `SolveResult`:
  - **TTFS** — time to first solution (interactive budget),
  - **primal-dual gap** — `(best_bound − best_objective) / best_objective`
    at timeout (optimization quality),
  - **solver stats** — conflicts, branches, presolve elimination rate,
  - **wall vs deterministic time** — the latter (CP-SAT's deterministic
    time) is the fair cross-machine comparison unit.
- **Regression gate** — benchmark runs run in CI (worker container) with
  time budgets; a table of expected TTFS/gap per instance is checked against
  a tolerance so a modelling regression (a wide domain, a lost global
  constraint) fails the build instead of silently slowing production.

## 13. Performance

- **Worker isolation.** The solver never shares a process with request
  threads: a hung search cannot stall the API, and the native OR-Tools wheel
  ships only in the worker image.
- **Global constraints, not loops.** `all_different`, `at_most_one`,
  `no_overlap` and reification delegate to CP-SAT's tuned propagators. The
  design rule — "the adapter expresses intent, never the encoding loop" —
  is the single biggest performance lever, and it is enforced by code review
  and the benchmark gate.
- **Parallel workers.** `num_search_workers` mirrors cores; CP-SAT's
  portfolio + shared learned clauses make this near-linear on hard instances.
- **Warm starts.** Repair solves (§8) typically finish in a fraction of the
  cold-solve budget, which is why interactive editing stays responsive.
- **Budget discipline.** Every public solve carries a time limit; interactive
  jobs use `stop_after_first_solution` to guarantee a schedule fast, with a
  background refinement run to close the gap.
- **Batch reads.** Problem snapshots are built with set-based SQL (the
  `risk/evaluator.py` pattern), never N+1; result rows are compact JSONB,
  aggregated server-side.
- **Caching.** Published results are cached keyed by
  `(problem_hash, params_hash, version)`; identical re-runs are served
  without re-solving (the problem hash is the same idempotent snapshot hash
  the simulation engine uses).

## 14. Extensibility

Adding a new scheduling domain is a **pure additive** exercise:

1. Define the problem dataclasses (exams, rooms, buses, matches…).
2. Write an adapter implementing `ProblemAdapter`:
   - `build(builder)` — declare variables/constraints, return the objective;
   - `interpret(solution, builder)` — domain-shaped JSON back out;
   - `hints(builder)` (optional) — greedy warm start;
   - `suggest_relaxations(conflicts)` (optional) — domain explanations.
3. Register it in the adapter registry (metadata: problem id, permission
   required, worker/in-process flag, default `SolveParams`).
4. Add benchmark instances + golden tests.

The engine, explainer, persistence, tenancy and audit layers are untouched.
Extending the *constraint vocabulary* (e.g. a new `circuit` helper for
routing loops) is likewise a builder method + tests, and every new constraint
is automatically explanation-aware by virtue of the gate registry.

## 15. Architecture

```
Web / Mobile ─► /api/v1/optimization/* (tenancy-guarded, audit)
                     │
        ┌────────────┴──────────────────────────┐
   Job enqueue (light)              Poll / fetch results
        │                                     │
   Optimization Service ──► worker: OptimizationRunner
        │                         │  SolverEngine (CP-SAT, ortools)
        │                         └  ConflictExplainer
   Problem snapshot (frozen,      │
   from simulation snapshot /     │
   live batch read)               ▼
                             SolveResult rows (immutable, tenant-scoped)
                                     │
                     interpret → JSON feeds (grid/Gantt/breakdown)
```

- **API layer**: submit job, list jobs, fetch solution/conflict feeds.
  Never imports `ortools`.
- **Worker**: runs `SolverEngine`; heavy native wheel lives here only.
- **Tenancy**: job + result repos are `TenantScopedRepository` subclasses;
  problem snapshots carry `campus_id` like simulation snapshots.
- **Audit**: submit / solve / publish / write-back all logged.

## 16. Roadmap

Phase 1 — core model & pipeline
- `core/` (model, constraints, objective, engine, explain) + adapter
  protocol + invigilation working example. ✅ (this document's working core)
- Unit + determinism tests, tenancy hooks, pyproject dependency.

Phase 2 — adapters & API
- Timetable, room allocation, exam scheduling adapters on the `academic_ops`
  models (rooms, time slots, timetables already exist there).
- Teacher allocation + hostel + invigilation on real data.
- Persistence (job/result tables, Alembic migration), API router, worker
  job runner, audit wiring.

Phase 3 — routing & simulation mode
- Bus routing adapter (circuit/route encoding) + transport timing.
- Simulation interop: scenario levers → constraint deltas → re-solve →
  schedule-vs-baseline comparison.
- Sports scheduling (round-robin) adapter.

Phase 4 — operations & product surface
- Benchmark suite + CI regression gate.
- Visualization feeds (grid, Gantt, conflict overlay, objective breakdown)
  and exporters.
- Minimal-core refinement for explanations; result caching.

## 17. Testing strategy

- **Golden determinism tests** — the same adapter + `SolveParams` must yield
  the same objective and solution on repeated runs (CP-SAT is deterministic;
  this proves we never accidentally set a random seed or machine-dependent
  default). The invigilation suite asserts exact objective values.
- **Hard-constraint audit tests** — for every solved instance, assert the
  interpreted solution satisfies every hard constraint (no double-booked
  teachers, capacity respected, unavailability honoured) *independently of
  the solver's self-report*.
- **Soft-objective tests** — assert the weighted objective equals the sum of
  documented penalties; lexicographic tests assert level-1 optimum is frozen
  while level-2 improves.
- **Conflict tests** — known-infeasible instances produce reports naming the
  expected constraints; feasible instances report clean.
- **Warm-start tests** — repair a changed problem from a previous solution
  and assert feasibility + the changed hard constraint now holds.
- **Tenancy suite** — cross-campus isolation of jobs/results, mirroring the
  existing multi-tenant security suite.
- **Benchmark regression** — the CI gate from §12.
- **No-AI audit** — a lint-style test asserting `adapters/*` import only the
  core and `ortools.sat.python.cp_model` (no stochastic/ML dependencies),
  mirroring the simulation engine's audit.

## Related docs
- [`SIMULATION_ENGINE.md`](SIMULATION_ENGINE.md) — the deterministic
  forecasting engine this layer interoperates with (§11).
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`TENANCY.md`](TENANCY.md)
- [`ACADEMIC_OPS`](../apps/api/app/domains/academic_ops/service.py) — rooms,
  time slots and timetable data the Phase-2 adapters consume.
