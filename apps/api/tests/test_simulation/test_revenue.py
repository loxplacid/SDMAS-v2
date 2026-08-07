"""Determinism-golden tests for the simulation revenue path.

These pin exact numeric outputs so any regression to reproducibility is caught
immediately: same snapshot + same scenario -> identical value, every time and
on any machine.
"""

from __future__ import annotations

import pytest

from app.simulation.coefficient.registry import Coefficients
from app.simulation.engine.dag import DependencyEngine, MetricResult, MetricSpec
from app.simulation.engine.default_graph import build_default_engine
from app.simulation.forecasts.revenue import revenue_spec
from app.simulation.model.lever import FeeMultiplier, ScholarshipDelta
from app.simulation.model.scenario import Scenario
from app.simulation.snapshot.snapshot import SimulationSnapshot, TeacherRecord

# ---------------------------------------------------------------------------
# Fixtures (the canonical fixture school — shared by the whole test suite)
# ---------------------------------------------------------------------------


def make_snapshot() -> SimulationSnapshot:
    return SimulationSnapshot(
        campus_id=1,
        academic_year="2026-27",
        fee_rate={1: 100_000, 2: 120_000},  # minor units
        enrollment={1: 50, 2: 40},
        scholarship_grants={1: 5_000},
        teachers=(
            TeacherRecord(teacher_id=1, grade=1, service_hours=20, tenure=5),
            TeacherRecord(teacher_id=2, grade=1, service_hours=20, tenure=2),
            TeacherRecord(teacher_id=3, grade=2, service_hours=20, tenure=4),
            TeacherRecord(teacher_id=4, grade=2, service_hours=20, tenure=1),
        ),
        section_sizes={1: 25, 2: 20},
        fleet_size=2,
        transport_demand=60,
        routes=3,
        rooms=12,
        base_attendance={1: 92.0, 2: 90.0},
        base_risk={1: 8.0, 2: 12.0},
        base_performance={1: 78.0, 2: 74.0},
    )


def run(scenario: Scenario) -> dict[str, MetricResult]:
    return build_default_engine().run(scenario.context(Coefficients()))


# ---------------------------------------------------------------------------
# Baseline & determinism
# ---------------------------------------------------------------------------


def test_baseline_revenue_is_deterministic() -> None:
    scenario = Scenario(id="base", campus_id=1, base_snapshot=make_snapshot())
    first = run(scenario)["revenue"].value
    second = run(scenario)["revenue"].value
    assert first == pytest.approx(8_325_750.0)
    assert second == pytest.approx(8_325_750.0)
    assert first == second  # exact equality, not just approx


def test_budget_uses_full_cost_lines() -> None:
    scenario = Scenario(id="base", campus_id=1, base_snapshot=make_snapshot())
    results = run(scenario)
    budget = results["budget"]
    co = Coefficients()
    assert budget.breakdown["expense_teachers"] == 4 * co.teacher_annual_cost_minor
    assert budget.breakdown["expense_fleet"] == 2 * co.bus_annual_cost_minor
    assert budget.breakdown["expense_rooms"] == 12 * co.room_annual_cost_minor
    assert budget.breakdown["expense_scholarships"] == 5_000
    assert budget.value == pytest.approx(
        results["revenue"].value
        - float(
            4 * co.teacher_annual_cost_minor
            + 2 * co.bus_annual_cost_minor
            + 12 * co.room_annual_cost_minor
            + 5_000
        )
    )


# ---------------------------------------------------------------------------
# Levers
# ---------------------------------------------------------------------------


def test_tuition_raise_increases_revenue() -> None:
    base = Scenario(id="base", campus_id=1, base_snapshot=make_snapshot())
    raised = Scenario(
        id="s",
        campus_id=1,
        base_snapshot=make_snapshot(),
        levers=(FeeMultiplier(factor=1.07),),
    )
    base_val = run(base)["revenue"].value
    s_val = run(raised)["revenue"].value
    assert s_val == pytest.approx(8_908_850.0)
    assert s_val > base_val


def test_scholarship_delta_reduces_revenue() -> None:
    scenario = Scenario(
        id="s",
        campus_id=1,
        base_snapshot=make_snapshot(),
        levers=(ScholarshipDelta(factor=2.0),),
    )
    base_revenue = run(Scenario(id="base", campus_id=1, base_snapshot=make_snapshot()))["revenue"]
    extra_grant = 5_000 * (2.0 - 1.0)
    assert run(scenario)["revenue"].value == pytest.approx(base_revenue.value - extra_grant * 0.85)


def test_assumption_override_changes_collection() -> None:
    scenario = Scenario(
        id="s",
        campus_id=1,
        base_snapshot=make_snapshot(),
        assumptions={"collection_recovery": 0.9},
    )
    result = run(scenario)["revenue"]
    assert result.value == pytest.approx(9_795_000.0 * 0.9)


def test_unknown_assumption_raises() -> None:
    scenario = Scenario(
        id="s",
        campus_id=1,
        base_snapshot=make_snapshot(),
        assumptions={"not_a_coefficient": 1.0},
    )
    with pytest.raises(ValueError, match="Unknown coefficient"):
        run(scenario)


# ---------------------------------------------------------------------------
# DAG integrity
# ---------------------------------------------------------------------------


def test_cycle_detection_rejected() -> None:
    def a(_ctx, _prior) -> MetricResult:  # noqa: ARG001
        return MetricResult(metric_id="a", value=0.0, unit="x")

    def b(_ctx, _prior) -> MetricResult:  # noqa: ARG001
        return MetricResult(metric_id="b", value=0.0, unit="x")

    with pytest.raises(ValueError, match="Cycle"):
        DependencyEngine(
            [
                MetricSpec(metric_id="a", compute=a, inputs=("b",)),
                MetricSpec(metric_id="b", compute=b, inputs=("a",)),
            ]
        )


def test_unknown_dependency_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        DependencyEngine(
            [MetricSpec(metric_id="a", compute=revenue_spec().compute, inputs=("nope",))]
        )
