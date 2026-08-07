"""The variable model.

Adapters declare their decision variables through :class:`ModelBuilder`,
which owns a single :class:`cp_model.CpModel` and a name-indexed registry.
Keeping every decision variable in one registry is what lets the engine:

- apply solution hints (warm starts) by name,
- extract a JSON-able ``{name: value}`` solution without knowing the domain,
- gate hard constraints with assumption literals for conflict explanation.

All decisions are integral, per the CP-SAT contract: bools for assignments,
integers for selection, fixed-size intervals for durations.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.optimization.core.constraints import Constraint


@dataclass(frozen=True)
class Domain:
    """Integer domain [lower, upper] for a decision variable.

    Domains must be tight: a slot index is ``Domain(0, n_slots - 1)``, never
    a wide range — wide domains enlarge the search space and slow down
    propagation.
    """

    lower: int
    upper: int


class ModelBuilder:
    """Owns the CP-SAT model, the named variable registry and constraints."""

    def __init__(self, *, gate_hard: bool = False) -> None:
        self.model = cp_model.CpModel()
        # When True, every hard constraint is reified by its own assumption
        # literal (see explain.py). Semantics are unchanged: the engine
        # asserts all gates before solving.
        self.gate_hard = gate_hard
        self._decision_vars: dict[str, object] = {}
        self._interval_vars: dict[str, object] = {}
        self._constraints: list[Constraint] = []
        self._gates: dict[object, str] = {}
        self.objective_terms: list[tuple[object, float]] = []

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def bool_var(self, name: str):
        """A 0/1 decision variable (e.g. ``x[exam, teacher]``)."""
        if name in self._decision_vars:
            raise ValueError(f"Duplicate decision variable: {name}")
        var = self.model.NewBoolVar(name)
        self._decision_vars[name] = var
        return var

    def int_var(self, name: str, domain: Domain):
        """An integral selection variable (slot, room, load, arrival time)."""
        if name in self._decision_vars:
            raise ValueError(f"Duplicate decision variable: {name}")
        var = self.model.NewIntVar(domain.lower, domain.upper, name)
        self._decision_vars[name] = var
        return var

    def interval_var(self, name: str, start, duration: int):
        """A fixed-duration interval anchored at ``start`` (structural)."""
        if name in self._interval_vars or name in self._decision_vars:
            raise ValueError(f"Duplicate interval variable: {name}")
        var = self.model.NewFixedSizeIntervalVar(start, duration, name)
        self._interval_vars[name] = var
        return var

    @property
    def decision_vars(self) -> dict[str, object]:
        """Name-indexed bool/int variables (the solution surface)."""
        return self._decision_vars

    @property
    def interval_vars(self) -> dict[str, object]:
        """Structural interval variables (excluded from the solution dict)."""
        return self._interval_vars

    # ------------------------------------------------------------------
    # Hard constraints
    # ------------------------------------------------------------------

    def _register(self, name: str, description: str, ct, gate) -> Constraint:
        constraint = Constraint(name=name, description=description, hard=True, gate=gate)
        self._constraints.append(constraint)
        if gate is not None:
            self._gates[gate] = name
        return constraint

    def _gate_for(self, name: str):
        if not self.gate_hard:
            return None
        return self.model.NewBoolVar(f"__gate_{name}")

    def exactly_one(self, literals, name: str, description: str = "") -> Constraint:
        """Exactly one of ``literals`` is true (e.g. one teacher per exam)."""
        gate = self._gate_for(name)
        ct = self.model.Add(sum(literals) == 1)
        if gate is not None:
            ct.OnlyEnforceIf(gate)
        return self._register(name, description, ct, gate)

    def at_most_one(self, literals, name: str, description: str = "") -> Constraint:
        """At most one of ``literals`` is true (optional exclusivity)."""
        gate = self._gate_for(name)
        ct = self.model.Add(sum(literals) <= 1)
        if gate is not None:
            ct.OnlyEnforceIf(gate)
        return self._register(name, description, ct, gate)

    def all_different(self, variables, name: str, description: str = "") -> Constraint:
        """All ``variables`` take pairwise distinct values.

        The canonical encoding for "no two jobs share a resource at a slot":
        pass composed expressions like ``slot[e] * n_rooms + room[e]``.
        """
        gate = self._gate_for(name)
        if gate is None:
            self.model.AddAllDifferent(variables)
        else:
            # AddAllDifferent cannot be reified directly; decompose pairwise
            # when gating (exact, just less compact).
            for a, b in itertools.combinations(variables, 2):
                self.model.Add(a != b).OnlyEnforceIf(gate)
        return self._register(name, description, None, gate)

    def no_overlap(self, intervals, name: str, description: str = "") -> Constraint:
        """``intervals`` must not overlap in time (rooms, pitches, buses)."""
        gate = self._gate_for(name)
        if gate is None:
            self.model.AddNoOverlap(intervals)
        else:
            # Disjunctive decomposition when gating: for each pair, one must
            # finish before the other starts.
            for a, b in itertools.combinations(intervals, 2):
                a_before = self.model.NewBoolVar(f"__order_{name}_{a.Name()}_{b.Name()}")
                self.model.Add(a.StartExpr() + a.SizeExpr() <= b.StartExpr()).OnlyEnforceIf(
                    [gate, a_before]
                )
                self.model.Add(b.StartExpr() + b.SizeExpr() <= a.StartExpr()).OnlyEnforceIf(
                    [gate, a_before.Not()]
                )
        return self._register(name, description, None, gate)

    def allowed_assignments(
        self, var, allowed_values, name: str, description: str = ""
    ) -> Constraint:
        """``var`` may only take one of ``allowed_values``.

        The canonical encoding for capacity, lab requirements and holiday
        rules. Single-variable only (multi-variable tables are decomposed by
        the adapter into pairwise constraints).
        """
        gate = self._gate_for(name)
        if gate is None:
            self.model.AddAllowedAssignments([var], [(v,) for v in allowed_values])
        else:
            # Gated path: ``gate ⇒ var ∈ allowed_values``. Encode via one
            # indicator per allowed value — exactly one is picked, and each
            # pick forces var to its value. (Conjunction of reified
            # equalities would wrongly force var to *every* value.)
            picks = [
                self.model.NewBoolVar(f"__pick_{name}_{k}") for k in range(len(allowed_values))
            ]
            for k, value in enumerate(allowed_values):
                self.model.Add(var == value).OnlyEnforceIf(picks[k])
            self.model.Add(sum(picks) == 1).OnlyEnforceIf(gate)
        return self._register(name, description, None, gate)

    def only_if(self, expression, literals, name: str, description: str = "") -> Constraint:
        """Reification: ``expression`` is enforced whenever every literal in
        ``literals`` is true.

        The canonical encoding for availability and clash rules, e.g.
        "teacher T is never double-booked": ``slot(e1) != slot(e2)`` enforced
        when ``x[e1, T]`` and ``x[e2, T]`` are both true.
        """
        gate = self._gate_for(name)
        ct = self.model.Add(expression)
        if gate is not None:
            ct.OnlyEnforceIf([gate, *literals])
        else:
            ct.OnlyEnforceIf(literals)
        return self._register(name, description, ct, gate)

    def forbid_true(self, bool_var, name: str, description: str = "") -> Constraint:
        """Force a boolean decision to False (teacher unavailable, holiday)."""
        gate = self._gate_for(name)
        ct = self.model.Add(bool_var == 0)
        if gate is not None:
            ct.OnlyEnforceIf(gate)
        return self._register(name, description, ct, gate)

    # ------------------------------------------------------------------
    # Soft constraints (weighted penalty terms)
    # ------------------------------------------------------------------

    def soft_term(self, name: str, expr, weight: float, description: str = "") -> Constraint:
        """Penalise ``expr`` (a non-negative linear expression) by ``weight``.

        Used for preference mismatches: ``1 - x[exam, preferred_teacher]``.
        """
        self.objective_terms.append((expr, weight))
        constraint = Constraint(
            name=name, description=description, hard=False, weight=weight, term=expr
        )
        self._constraints.append(constraint)
        return constraint

    def soft_excess(
        self,
        name: str,
        expr,
        bound: int,
        weight: float,
        description: str = "",
        max_excess: int = 10_000,
    ) -> Constraint:
        """Penalise the amount by which ``expr`` exceeds ``bound``.

        The penalty is exactly ``max(0, expr - bound)`` via a dedicated
        violation variable. Used for maximum weekly periods, load balance and
        transport-timing overruns.
        """
        excess = self.model.NewIntVar(0, max_excess, f"{name}__excess")
        self.model.AddMaxEquality(excess, [expr - bound, 0])
        self.objective_terms.append((excess, weight))
        constraint = Constraint(
            name=name, description=description, hard=False, weight=weight, term=excess
        )
        self._constraints.append(constraint)
        return constraint

    # ------------------------------------------------------------------
    # Introspection (engine / explainer surface)
    # ------------------------------------------------------------------

    @property
    def constraints(self) -> tuple[Constraint, ...]:
        return tuple(self._constraints)

    @property
    def hard_constraints(self) -> tuple[Constraint, ...]:
        return tuple(c for c in self._constraints if c.hard)

    @property
    def soft_constraints(self) -> tuple[Constraint, ...]:
        return tuple(c for c in self._constraints if c.is_soft)

    def gate_literals(self) -> list[object]:
        """Assumption literals asserting all gated hard constraints."""
        return [c.gate for c in self._constraints if c.gate is not None]

    def name_for_gate(self, literal) -> str:
        """Constraint name behind an assumption literal (explanation core)."""
        return self._gates[literal]

    def hint_map(self, name_values: dict[str, int]) -> dict[object, int]:
        """Resolve a name→value warm start to CP-SAT variables."""
        return {
            var: int(value)
            for name, value in name_values.items()
            if (var := self._decision_vars.get(name)) is not None
        }
