"""Unit tests for the optimization core.

Coverage:
- Variable model: named registry, duplicate rejection, hint bridge
- Global constraints: exactly_one, all_different, soft_excess
- Objectives: weighted terms, lexicographic levels with frozen optimum
- Engine: deterministic results, status mapping, solution extraction
- Explanation plumbing: gated model semantics are unchanged
"""

from __future__ import annotations

import pytest

from app.optimization.core.constraints import Constraint
from app.optimization.core.engine import SolveParams, SolverEngine, SolveStatus
from app.optimization.core.model import Domain, ModelBuilder
from app.optimization.core.objective import Objective

# ---------------------------------------------------------------------------
# Variable model
# ---------------------------------------------------------------------------


class TestVariableModel:
    def test_named_registry_and_duplicate_rejection(self):
        builder = ModelBuilder()
        builder.bool_var("x0")
        builder.int_var("v", Domain(0, 4))
        assert set(builder.decision_vars) == {"x0", "v"}
        with pytest.raises(ValueError):
            builder.bool_var("x0")

    def test_interval_vars_are_structural(self):
        builder = ModelBuilder()
        start = builder.int_var("start", Domain(0, 10))
        builder.interval_var("period", start, 3)
        assert "period" in builder.interval_vars
        assert "period" not in builder.decision_vars

    def test_hint_map_resolves_by_name(self):
        builder = ModelBuilder()
        builder.bool_var("a")
        hint_map = builder.hint_map({"a": 1, "missing": 7})
        assert len(hint_map) == 1


# ---------------------------------------------------------------------------
# Constraints & objectives
# ---------------------------------------------------------------------------


class TestConstraintsAndObjectives:
    def test_exactly_one_is_optimal_and_extracted(self):
        builder = ModelBuilder()
        x = [builder.bool_var(f"x{i}") for i in range(3)]
        builder.exactly_one(x, "pick_one", "choose exactly one")
        builder.soft_term("prefer_last", 1 - x[2], 1.0, "prefer the last option")
        result = SolverEngine().solve(
            builder, Objective.from_builder(builder), params=SolveParams(random_seed=1)
        )
        assert result.status is SolveStatus.OPTIMAL
        assert result.objective_value == 0.0
        assert result.solution is not None
        assert result.solution["x2"] == 1
        assert sum(result.solution[f"x{i}"] for i in range(3)) == 1

    def test_all_different_forces_distinct_values(self):
        builder = ModelBuilder()
        vs = [builder.int_var(f"v{i}", Domain(0, 2)) for i in range(3)]
        builder.all_different(vs, "distinct", "all values distinct")
        result = SolverEngine().solve(builder, Objective.from_builder(builder))
        assert result.solved
        values = [result.solution[f"v{i}"] for i in range(3)]
        assert len(set(values)) == 3

    def test_soft_excess_penalised_to_zero(self):
        builder = ModelBuilder()
        picks = [builder.bool_var(f"p{i}") for i in range(4)]
        builder.soft_excess("load", sum(picks), 1, 10.0, max_excess=4)
        result = SolverEngine().solve(
            builder, Objective.from_builder(builder), params=SolveParams(random_seed=1)
        )
        assert result.solved
        assert result.objective_value == 0.0
        assert sum(result.solution[f"p{i}"] for i in range(4)) <= 1

    def test_soft_excess_exact_violation(self):
        """Two independent picks must exceed the bound by exactly one."""
        builder = ModelBuilder()
        a = builder.bool_var("a")
        b = builder.bool_var("b")
        builder.exactly_one([a], "pick_a", "a is on")
        builder.exactly_one([b], "pick_b", "b is on")
        builder.soft_excess("load", a + b, 1, 5.0, max_excess=2)
        result = SolverEngine().solve(builder, Objective.from_builder(builder))
        assert result.solved
        # Both a and b are forced true, so excess must be exactly 1.
        assert result.objective_value == 5.0
        assert result.solution["a"] == 1
        assert result.solution["b"] == 1

    def test_constraint_metadata_registered(self):
        builder = ModelBuilder()
        builder.exactly_one([builder.bool_var("x")], "one", "description here")
        builder.soft_term("soft", 1, 2.0, "a soft term")
        hard = [c for c in builder.constraints if c.hard]
        soft = [c for c in builder.constraints if not c.hard]
        assert len(hard) == 1
        assert len(soft) == 1
        assert isinstance(hard[0], Constraint)
        assert hard[0].name == "one"
        assert hard[0].description == "description here"
        assert soft[0].weight == 2.0


# ---------------------------------------------------------------------------
# Lexicographic objectives
# ---------------------------------------------------------------------------


class TestLexicographic:
    def test_level_one_optimum_is_frozen(self):
        """Level 1 minimises the excess; level 2 then minimises mismatches
        among level-1-optimal solutions without trading level 1 off."""
        builder = ModelBuilder()
        a0, a1 = builder.bool_var("a0"), builder.bool_var("a1")
        c0, c1 = builder.bool_var("c0"), builder.bool_var("c1")
        builder.exactly_one([a0, a1], "pick_a", "pick one of a")
        builder.exactly_one([c0, c1], "pick_c", "pick one of c")
        level1 = Objective(terms=((a0 + a1 + c0 + c1 - 1, 10.0),))
        level2 = Objective(terms=((1 - a1, 1.0), (1 - c1, 1.0)))
        result = SolverEngine().solve_lexicographic(
            builder, [level1, level2], params=SolveParams(random_seed=2)
        )
        assert result.levels[0].status is SolveStatus.OPTIMAL
        # Level 1: (a0+a1+c0+c1-1) = 1, weighted by 10.0 → 10.0.
        assert result.levels[0].objective_value == 10.0
        assert result.levels[1].objective_value == 0.0
        assert result.solution["a1"] == 1
        assert result.solution["c1"] == 1


# ---------------------------------------------------------------------------
# Determinism & explanation plumbing
# ---------------------------------------------------------------------------


class TestEngine:
    def test_deterministic_across_runs(self):
        builder1 = ModelBuilder()
        x1 = [builder1.bool_var(f"x{i}") for i in range(5)]
        builder1.exactly_one(x1, "one", "choose exactly one")
        builder1.soft_excess("load", sum(x1), 1, 3.0, max_excess=5)
        builder2 = ModelBuilder()
        x2 = [builder2.bool_var(f"x{i}") for i in range(5)]
        builder2.exactly_one(x2, "one", "choose exactly one")
        builder2.soft_excess("load", sum(x2), 1, 3.0, max_excess=5)
        params = SolveParams(random_seed=0, num_search_workers=1)
        r1 = SolverEngine().solve(builder1, Objective.from_builder(builder1), params=params)
        r2 = SolverEngine().solve(builder2, Objective.from_builder(builder2), params=params)
        assert r1.solution == r2.solution
        assert r1.objective_value == r2.objective_value

    def test_gated_model_semantics_unchanged(self):
        """A gated build (explanation mode) must find the same solution."""

        def build(gate: bool):
            builder = ModelBuilder(gate_hard=gate)
            picks = [builder.bool_var(f"p{i}") for i in range(3)]
            builder.exactly_one(picks, "one", "choose exactly one")
            builder.soft_term("pref", 1 - picks[2], 1.0, "prefer last")
            return builder, Objective.from_builder(builder)

        b1, o1 = build(False)
        b2, o2 = build(True)
        params = SolveParams(random_seed=0)
        r1 = SolverEngine().solve(b1, o1, params=params)
        r2 = SolverEngine().solve(b2, o2, params=params)
        assert r1.solved and r2.solved
        assert r1.solution == r2.solution
        assert r1.objective_value == r2.objective_value

    def test_hints_are_applied(self):
        """Hints are applied via AddHint; with a matching objective the
        hinted variable deterministically wins."""
        builder = ModelBuilder()
        picks = [builder.bool_var(f"p{i}") for i in range(3)]
        builder.exactly_one(picks, "one", "choose exactly one")
        builder.soft_term("prefer_p1", 1 - picks[1], 1.0, "prefer p1")
        result = SolverEngine().solve(
            builder,
            Objective.from_builder(builder),
            hints={"p1": 1},
        )
        assert result.hints_used is True
        assert result.solution["p1"] == 1


# ---------------------------------------------------------------------------
# Interval / global-constraint paths (no_overlap, at_most_one, gating)
# ---------------------------------------------------------------------------


class TestGlobalConstraints:
    def test_no_overlap_forces_gap(self):
        """Two 3-unit intervals must start at least 3 apart."""
        builder = ModelBuilder()
        s1 = builder.int_var("s1", Domain(0, 5))
        s2 = builder.int_var("s2", Domain(0, 5))
        builder.interval_var("iv1", s1, 3)
        builder.interval_var("iv2", s2, 3)
        builder.no_overlap(
            [builder.interval_vars["iv1"], builder.interval_vars["iv2"]],
            "no_overlap",
            "rooms are exclusive",
        )
        result = SolverEngine().solve(builder, Objective.from_builder(builder))
        assert result.solved
        assert abs(result.solution["s1"] - result.solution["s2"]) >= 3

    def test_no_overlap_gated_matches_ungated(self):
        def build(gate: bool):
            b = ModelBuilder(gate_hard=gate)
            s1 = b.int_var("s1", Domain(0, 5))
            s2 = b.int_var("s2", Domain(0, 5))
            b.interval_var("iv1", s1, 3)
            b.interval_var("iv2", s2, 3)
            b.no_overlap(
                [b.interval_vars["iv1"], b.interval_vars["iv2"]],
                "no_overlap",
                "rooms are exclusive",
            )
            return b, Objective.from_builder(b)

        params = SolveParams(random_seed=0, num_search_workers=1)
        b1, o1 = build(False)
        b2, o2 = build(True)
        r1 = SolverEngine().solve(b1, o1, params=params)
        r2 = SolverEngine().solve(b2, o2, params=params)
        assert r1.solved and r2.solved
        assert abs(r1.solution["s1"] - r1.solution["s2"]) >= 3
        assert abs(r2.solution["s1"] - r2.solution["s2"]) >= 3

    def test_at_most_one_gated_matches_ungated(self):
        def build(gate: bool):
            b = ModelBuilder(gate_hard=gate)
            xs = [b.bool_var(f"x{i}") for i in range(3)]
            b.at_most_one(xs, "at_most", "at most one is picked")
            b.soft_term("pref", 1 - xs[2], 1.0, "prefer x2")
            return b, Objective.from_builder(b)

        params = SolveParams(random_seed=0, num_search_workers=1)
        b1, o1 = build(False)
        b2, o2 = build(True)
        r1 = SolverEngine().solve(b1, o1, params=params)
        r2 = SolverEngine().solve(b2, o2, params=params)
        assert r1.solution == r2.solution == {"x0": 0, "x1": 0, "x2": 1}
        assert sum(r1.solution[f"x{i}"] for i in range(3)) <= 1
        assert sum(r2.solution[f"x{i}"] for i in range(3)) <= 1

    def test_lexicographic_skips_empty_level(self):
        """A level without objective terms must not crash the freeze."""
        builder = ModelBuilder()
        picks = [builder.bool_var(f"p{i}") for i in range(3)]
        builder.exactly_one(picks, "one", "choose exactly one")
        level1 = Objective(terms=((1 - picks[2], 1.0),))
        empty = Objective()
        result = SolverEngine().solve_lexicographic(
            builder, [level1, empty], params=SolveParams(random_seed=0)
        )
        assert len(result.levels) == 2
        assert result.levels[0].objective_value == 0.0
        assert result.solution["p2"] == 1

    def test_weight_scale_mismatch_raises(self):
        """Weights that are not integral at the scale must fail loudly."""
        builder = ModelBuilder()
        x = builder.bool_var("x")
        objective = Objective(terms=((x, 1 / 3),))
        with pytest.raises(ValueError, match="integral"):
            objective.integer_expr(scale=100)
