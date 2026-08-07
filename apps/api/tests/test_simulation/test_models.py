"""Golden determinism + structural tests for all nine forecast models.

Golden rule (see SIMULATION_ENGINE.md §13): same snapshot + same scenario ->
identical values on every run and every machine. Structural tests verify the
deterministic band logic and capacity flags.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.simulation.coefficient.registry import Coefficients
from app.simulation.engine.default_graph import build_default_engine
from app.simulation.model.lever import (
    AddBuses,
    ChangeSchedule,
    ClassSizeChange,
    RemoveTeacher,
    ScholarshipDelta,
)
from app.simulation.model.scenario import Scenario
from tests.test_simulation.test_revenue import make_snapshot

ALL_METRICS = {
    "revenue",
    "workload",
    "attendance",
    "dropout",
    "budget",
    "rooms",
    "transport",
    "performance",
    "resource",
}


def run(levers=(), assumptions=None) -> dict:
    scenario = Scenario(
        id="s",
        campus_id=1,
        base_snapshot=make_snapshot(),
        levers=levers,
        assumptions=assumptions or {},
    )
    return build_default_engine().run(scenario.context(Coefficients()))


class TestFullRun:
    def test_all_nine_metrics_computed(self) -> None:
        assert set(run()) == ALL_METRICS

    def test_full_run_is_deterministic(self) -> None:
        first = run()
        second = run()
        for metric_id in ALL_METRICS:
            assert first[metric_id].value == second[metric_id].value, metric_id

    def test_baseline_has_no_flags(self) -> None:
        for metric_id, result in run().items():
            assert result.flags == (), metric_id

    def test_budget_after_revenue_in_dag(self) -> None:
        results = run()
        # Budget's cost lines are pulled from upstream metric breakdowns.
        assert results["budget"].breakdown["revenue"] == results["revenue"].value


class TestBaselinePins:
    """Hand-derived exact pins for the canonical fixture school."""

    def test_revenue(self) -> None:
        assert run()["revenue"].value == pytest.approx(8_325_750.0)

    def test_workload(self) -> None:
        # Loads: grade1 504+504, grade2 404+404 = 1816 / (4 × 600) = 0.7567.
        result = run()["workload"]
        assert result.value == pytest.approx(0.7567, abs=1e-4)
        assert result.breakdown["n_teachers"] == 4
        assert result.breakdown["per_teacher"] == {
            "1": 504.0,
            "2": 504.0,
            "3": 404.0,
            "4": 404.0,
        }

    def test_attendance(self) -> None:
        # Grade1 standard (0), grade2 reduced (+0.8): (50×92 + 40×90.8)/90.
        assert run()["attendance"].value == pytest.approx(91.4667, abs=1e-3)

    def test_dropout_equals_base_risk(self) -> None:
        # No levers -> no fee pressure: (50×8 + 40×12)/90.
        assert run()["dropout"].value == pytest.approx(9.7778, abs=1e-3)

    def test_rooms(self) -> None:
        # 4 sections of 40 periods / 12 rooms × 40 periods.
        assert run()["rooms"].value == pytest.approx(0.3333, abs=1e-3)

    def test_transport(self) -> None:
        # 60 demand / (40 seats × 2 buses).
        assert run()["transport"].value == pytest.approx(0.75)
        assert run()["transport"].breakdown["midday_peak"] == 30

    def test_performance(self) -> None:
        # Grade1 standard (+0), grade2 reduced (+2.0): (50×78 + 40×76)/90.
        assert run()["performance"].value == pytest.approx(77.1111, abs=1e-3)

    def test_resource(self) -> None:
        # 0.3×teacher + 0.3×rooms + 0.2×fleet + 0.2×transport.
        assert run()["resource"].value == pytest.approx(0.6270, abs=1e-3)


class TestCapacityFlags:
    def test_remove_teacher_flags_over_capacity(self) -> None:
        results = run(levers=(RemoveTeacher(teacher_id=3),))
        workload = results["workload"]
        assert "over_capacity_grade_2" in workload.flags
        assert workload.breakdown["n_teachers"] == 3

    def test_insufficient_fleet_flags_transport_and_attendance(self) -> None:
        tight = replace(make_snapshot(), fleet_size=1)  # 40 seats < 60 demand
        scenario = Scenario(id="s", campus_id=1, base_snapshot=tight)
        results = build_default_engine().run(scenario.context(Coefficients()))
        assert "insufficient_fleet" in results["transport"].flags
        assert "transport_shortfall" in results["attendance"].flags

    def test_add_buses_restores_capacity(self) -> None:
        tight = replace(make_snapshot(), fleet_size=1)
        scenario = Scenario(id="s", campus_id=1, base_snapshot=tight, levers=(AddBuses(count=1),))
        results = build_default_engine().run(scenario.context(Coefficients()))
        assert results["transport"].flags == ()
        assert results["transport"].value == pytest.approx(0.75)


class TestLeverEffects:
    def test_longer_day_lowers_attendance_raises_performance(self) -> None:
        results = run(levers=(ChangeSchedule(periods_per_day=9),))
        attendance = results["attendance"]
        assert attendance.breakdown["timing_band"] == "extended_periods"
        # -1.5 band vs baseline 92/90.
        assert attendance.value == pytest.approx(91.4667 - 1.5, abs=1e-3)
        # +225 weekly minutes × 0.02 per minute.
        assert results["performance"].value == pytest.approx(77.1111 + 4.5, abs=1e-3)

    def test_class_size_cap_rebalances_sections(self) -> None:
        results = run(levers=(ClassSizeChange(cap=22),))
        # Both grades drop into the "reduced" band (+2.0 performance each):
        # (50×80 + 40×76)/90 = 78.2222. Sections 2+2 -> 3+2, pushing rooms up.
        assert results["rooms"].breakdown["sections"] == 5
        assert results["rooms"].value == pytest.approx(5 / 12, abs=1e-3)
        assert results["performance"].value == pytest.approx(78.2222, abs=1e-3)

    def test_early_start_band(self) -> None:
        results = run(levers=(ChangeSchedule(day_start="08:00"),))
        assert results["attendance"].breakdown["timing_band"] == "early_start"
        assert results["attendance"].value == pytest.approx(91.4667 - 0.5, abs=1e-3)

    def test_scholarship_boost_lowers_dropout(self) -> None:
        """Retention bonus: +100% scholarship on grade 1 removes 15 points;
        grade 2 (no grant) keeps its base risk."""
        results = run(levers=(ScholarshipDelta(factor=2.0),))
        per_grade = results["dropout"].breakdown["per_grade"]
        assert per_grade == {"1": 0.0, "2": 12.0}
        assert results["dropout"].value == pytest.approx(480 / 90, abs=1e-3)
        assert results["dropout"].value < run()["dropout"].value

    def test_insufficient_rooms_flag_and_capped_value(self) -> None:
        crowded = replace(make_snapshot(), rooms=2)  # 4 sections > 2 rooms
        scenario = Scenario(id="s", campus_id=1, base_snapshot=crowded)
        results = build_default_engine().run(scenario.context(Coefficients()))
        assert "insufficient_rooms" in results["rooms"].flags
        assert results["rooms"].value == 1.0  # utilization is 0-1
        assert results["rooms"].breakdown["raw_utilization"] == pytest.approx(2.0)

    def test_band_table_override_via_assumptions(self) -> None:
        results = run(
            assumptions={
                "attn_timing_bands": {
                    "standard": -3.0,
                    "early_start": 0.0,
                    "long_day": 0.0,
                    "extended_periods": 0.0,
                }
            }
        )
        assert results["attendance"].value == pytest.approx(91.4667 - 3.0, abs=1e-3)

    def test_workload_shortfall_is_actionable(self) -> None:
        results = run(levers=(RemoveTeacher(teacher_id=3),))
        workload = results["workload"]
        assert "over_capacity_grade_2" in workload.flags
        # Grade 2 needs 2 sections × 400; one teacher covers 1 -> 400 uncovered.
        assert workload.breakdown["shortfall_student_hours"] == pytest.approx(400.0)
