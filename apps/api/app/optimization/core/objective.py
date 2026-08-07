"""Objective functions.

The default objective is a weighted sum of soft-constraint penalty terms
(``minimize Σ w_k · penalty_k``). The engine also supports strict-priority
*lexicographic* objectives, where each level's optimum is fixed before the
next level is optimised.

Weights are rational but the resulting expression must be integral for
CP-SAT; adapters use a documented scaling factor where needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class Objective:
    """A single weighted linear objective over the model's variables."""

    terms: tuple[tuple[object, float], ...] = ()
    sense: str = "minimize"

    def linear_expr(self):
        """The CP-SAT linear expression, or None when there are no terms.

        Float weights are fine inside the objective (Minimize/Maximize
        accept them), but not inside constraints.
        """
        if not self.terms:
            return None
        exprs = [expr for expr, _ in self.terms]
        weights = [weight for _, weight in self.terms]
        return cp_model.LinearExpr.weighted_sum(exprs, weights)

    def integer_expr(self, scale: int = 100):
        """Integer-coefficient version of the objective (``scale`` × terms).

        Used for the freeze constraints of lexicographic solves, where
        CP-SAT requires integral coefficients. Weights must be integral at
        ``scale`` (documented convention, §6.3); anything else raises rather
        than silently truncating precision and producing an infeasible
        freeze.
        """
        if not self.terms:
            return None
        exprs: list[object] = []
        weights: list[int] = []
        for expr, weight in self.terms:
            scaled = weight * scale
            if abs(scaled - round(scaled)) > 1e-9:
                raise ValueError(
                    f"Weight {weight} is not integral at weight_scale "
                    f"{scale}; weights must form an integral objective "
                    "(see OPTIMIZATION_ENGINE.md §6.3)."
                )
            exprs.append(expr)
            weights.append(int(round(scaled)))
        return cp_model.LinearExpr.weighted_sum(exprs, weights)

    def register_on(self, model: cp_model.CpModel) -> None:
        """Attach the objective to the model (Minimize or Maximize)."""
        expr = self.linear_expr()
        if expr is None:
            return
        if self.sense == "maximize":
            model.Maximize(expr)
        else:
            model.Minimize(expr)

    @classmethod
    def from_builder(cls, builder, sense: str = "minimize") -> "Objective":
        """Collect the soft terms a :class:`ModelBuilder` accumulated."""
        return cls(terms=tuple(builder.objective_terms), sense=sense)
