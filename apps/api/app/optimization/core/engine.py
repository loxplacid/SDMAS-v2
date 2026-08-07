"""The optimization pipeline: parameters, the solver facade, and results.

:class:`SolverEngine` wraps :class:`cp_model.CpSolver` with a stable,
JSON-serialisable result surface, applies solution hints (warm starts),
honours time/worker limits, and — when the model was built in explanation
mode — records the assumption core on infeasibility so :mod:`explain` can
name the conflicting constraints.

A solve is a pure function ``(builder, objective, params, hints) → result``;
the engine never touches the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ortools.sat.python import cp_model

from app.optimization.core.objective import Objective


class SolveStatus(str, Enum):
    """Outcome ladder documented in OPTIMIZATION_ENGINE.md §7."""

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"
    MODEL_INVALID = "model_invalid"


@dataclass(frozen=True)
class SolveParams:
    """Determinism + budget knobs for one solve."""

    time_limit_seconds: float = 30.0
    num_search_workers: int = 4
    random_seed: int = 0
    stop_after_first_solution: bool = False
    log_search_progress: bool = False
    # Scales float weights to integers for lexicographic freeze constraints
    # (CP-SAT constraints need integral coefficients). Weights must be
    # integral at this scale — see OPTIMIZATION_ENGINE.md §6.3.
    weight_scale: int = 100


@dataclass(frozen=True)
class SolveResult:
    """Stable result surface; every field is JSON-serialisable."""

    status: SolveStatus
    objective_value: float | None = None
    objective_bound: float | None = None
    wall_time_seconds: float = 0.0
    num_conflicts: int = 0
    num_branches: int = 0
    solution: dict[str, int] | None = None
    sufficient_assumptions: tuple[int, ...] = ()
    hints_used: bool = False

    @property
    def solved(self) -> bool:
        return self.status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)


@dataclass(frozen=True)
class LexSolveResult:
    """Result of a strict-priority multi-level solve."""

    levels: tuple[SolveResult, ...] = ()
    solution: dict[str, int] | None = None


class SolverEngine:
    """Thin, deterministic wrapper around CP-SAT."""

    _STATUS_MAP = {
        cp_model.OPTIMAL: SolveStatus.OPTIMAL,
        cp_model.FEASIBLE: SolveStatus.FEASIBLE,
        cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
        cp_model.MODEL_INVALID: SolveStatus.MODEL_INVALID,
    }

    def solve(self, builder, objective: Objective | None, params=None, hints=None) -> SolveResult:
        """Solve one objective. ``hints`` is a name→value warm start."""
        params = params or SolveParams()
        self._apply_hints(builder, hints)
        if objective is not None:
            objective.register_on(builder.model)
        solver = self._configured_solver(params)
        return self._run(solver, builder, params, hints is not None and bool(hints))

    def solve_lexicographic(
        self, builder, objectives: list[Objective], params=None, hints=None
    ) -> LexSolveResult:
        """Solve objectives in strict priority; each level freezes the
        previous level's optimum as a hard constraint."""
        params = params or SolveParams()
        self._apply_hints(builder, hints)
        levels: list[SolveResult] = []
        for index, objective in enumerate(objectives):
            objective.register_on(builder.model)
            solver = self._configured_solver(params)
            result = self._run(solver, builder, params, hints is not None and index == 0)
            levels.append(result)
            if not result.solved or result.objective_value is None:
                break
            freeze = objective.integer_expr(params.weight_scale)
            if freeze is None:
                continue  # level has no objective expression; nothing to freeze
            builder.model.Add(freeze == int(round(result.objective_value * params.weight_scale)))
        solution = levels[-1].solution if levels else None
        return LexSolveResult(levels=tuple(levels), solution=solution)

    # ------------------------------------------------------------------

    def _apply_hints(self, builder, hints) -> None:
        if not hints:
            return
        for var, value in builder.hint_map(hints).items():
            builder.model.AddHint(var, value)

    def _configured_solver(self, params: SolveParams) -> cp_model.CpSolver:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = params.time_limit_seconds
        solver.parameters.num_search_workers = params.num_search_workers
        solver.parameters.random_seed = params.random_seed
        solver.parameters.stop_after_first_solution = params.stop_after_first_solution
        solver.parameters.log_search_progress = params.log_search_progress
        return solver

    def _run(
        self, solver: cp_model.CpSolver, builder, params: SolveParams, hints_used: bool
    ) -> SolveResult:
        gates = builder.gate_literals()
        if gates:
            # Explanation mode: hard constraints are reified by assumption
            # literals; asserting the gates restores the original semantics.
            builder.model.add_assumptions(gates)
        status = solver.Solve(builder.model)
        sufficient = (
            tuple(solver.sufficient_assumptions_for_infeasibility())
            if status == cp_model.INFEASIBLE and gates
            else ()
        )
        return SolveResult(
            status=self._STATUS_MAP.get(status, SolveStatus.UNKNOWN),
            objective_value=float(solver.ObjectiveValue())
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None,
            objective_bound=float(solver.BestObjectiveBound())
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None,
            wall_time_seconds=float(solver.WallTime()),
            num_conflicts=int(solver.NumConflicts()),
            num_branches=int(solver.NumBranches()),
            solution=self._extract(solver, builder)
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None,
            sufficient_assumptions=sufficient,
            hints_used=hints_used,
        )

    @staticmethod
    def _extract(solver: cp_model.CpSolver, builder) -> dict[str, int] | None:
        return {name: int(solver.Value(var)) for name, var in builder.decision_vars.items()}
