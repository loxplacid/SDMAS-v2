"""Conflict explanation.

When a problem is infeasible the user needs to know *which rules* conflict.
The explainer rebuilds the problem in gate mode — every hard constraint
reified by its own assumption literal — then asks CP-SAT for a sufficient
subset of assumptions that proves infeasibility
(:meth:`CpSolver.sufficient_assumptions_for_infeasibility`). The returned
variable indices resolve back to constraint names through the builder's gate
registry, and the adapter translates them into domain language.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.optimization.core.engine import SolveParams, SolverEngine, SolveStatus
from app.optimization.core.model import ModelBuilder


@dataclass(frozen=True)
class ConflictReport:
    """Human-addressable result of an infeasibility investigation."""

    feasible: bool
    status: str
    conflicting_constraints: tuple[str, ...] = ()
    detail: str = ""
    relaxations: tuple[str, ...] = ()

    def render(self) -> str:
        """One-paragraph summary for logs, notifications and the UI."""
        if self.feasible:
            return f"Model is {self.status}; no conflicts."
        lines = [
            f"Model is infeasible. Conflicting constraints ({len(self.conflicting_constraints)}):"
        ]
        lines.extend(f"  - {name}" for name in self.conflicting_constraints)
        if self.relaxations:
            lines.append("Suggested relaxations:")
            lines.extend(f"  * {relaxation}" for relaxation in self.relaxations)
        return "\n".join(lines)


class ConflictExplainer:
    """Explains an infeasible :class:`ProblemAdapter` in domain language."""

    def __init__(self, engine: SolverEngine | None = None) -> None:
        self.engine = engine or SolverEngine()

    def explain(self, problem, params: SolveParams | None = None) -> ConflictReport:
        builder = ModelBuilder(gate_hard=True)
        objective = problem.build(builder)
        result = self.engine.solve(builder, objective, params=params)
        if result.status != SolveStatus.INFEASIBLE:
            return ConflictReport(feasible=True, status=result.status.value)

        names = tuple(
            sorted(
                {
                    builder.name_for_gate(builder.model.get_bool_var_from_proto_index(index))
                    for index in result.sufficient_assumptions
                }
            )
        )
        return ConflictReport(
            feasible=False,
            status=result.status.value,
            conflicting_constraints=names,
            detail="CP-SAT sufficient assumptions core",
            relaxations=tuple(problem.suggest_relaxations(names)),
        )
