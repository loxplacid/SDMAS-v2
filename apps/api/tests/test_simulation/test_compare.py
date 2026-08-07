"""Comparison tests: deltas, direction, composite score, flags.

The comparison is a pure function of two result dicts — re-rendering it
never recomputes metrics, and it is deterministic by construction.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.simulation.coefficient.registry import Coefficients
from app.simulation.engine.compare import compare_runs
from app.simulation.engine.default_graph import build_default_engine
from app.simulation.model.lever import FeeMultiplier
from app.simulation.model.scenario import Scenario
from tests.test_simulation.test_revenue import make_snapshot


def run(levers=(), snapshot=None) -> dict:
    scenario = Scenario(
        id="s",
        campus_id=1,
        base_snapshot=snapshot or make_snapshot(),
        levers=levers,
    )
    return build_default_engine().run(scenario.context(Coefficients()))


BASE = run()
WEIGHTS = Coefficients().comparison_weights


class TestDeltas:
    def test_tuition_raise_deltas(self) -> None:
        report = compare_runs("s", BASE, run(levers=(FeeMultiplier(1.07),)), WEIGHTS)
        revenue = report.delta("revenue")
        assert revenue is not None
        assert revenue.direction == "up"
        assert revenue.absolute_delta == pytest.approx(583_100.0)
        assert revenue.relative_delta == pytest.approx(583_100 / 8_325_750, abs=1e-6)

        dropout = report.delta("dropout")
        assert dropout is not None
        assert dropout.direction == "up"  # fee pressure raises dropout
        assert dropout.relative_delta == pytest.approx(2.1 / 9.7778, abs=1e-3)

        attendance = report.delta("attendance")
        assert attendance.direction == "neutral"  # money levers don't move it

    def test_composite_score(self) -> None:
        report = compare_runs("s", BASE, run(levers=(FeeMultiplier(1.07),)), WEIGHTS)
        # +0.0700×revenue + 0.0013×budget − 0.2148×dropout (weights signed).
        assert report.composite_score == pytest.approx(-0.1434, abs=1e-3)

    def test_revenue_is_net_positive_for_composite(self) -> None:
        """The same scenario scored with only the revenue weight is positive,
        proving the composite is a documented signed sum, not a hidden vote."""
        weights = {"revenue": 1.0}
        report = compare_runs("s", BASE, run(levers=(FeeMultiplier(1.07),)), weights)
        assert report.composite_score == pytest.approx(583_100 / 8_325_750, abs=1e-6)


class TestFlags:
    def test_flagged_metrics_propagate(self) -> None:
        tight = replace(make_snapshot(), fleet_size=1)  # insufficient fleet
        report = compare_runs("s", BASE, run(snapshot=tight), WEIGHTS)
        transport = report.delta("transport")
        assert transport is not None
        assert transport.flagged is True
        assert "transport" in report.flagged_metrics()
        assert "attendance" in report.flagged_metrics()  # transport_shortfall

    def test_unflagged_baseline(self) -> None:
        report = compare_runs("s", BASE, run(), WEIGHTS)
        assert report.flagged_metrics() == ()


class TestDeterminism:
    def test_comparison_is_deterministic(self) -> None:
        a = compare_runs("s", BASE, run(levers=(FeeMultiplier(1.07),)), WEIGHTS)
        b = compare_runs("s", BASE, run(levers=(FeeMultiplier(1.07),)), WEIGHTS)
        assert a.composite_score == b.composite_score
        assert [d.relative_delta for d in a.deltas] == [d.relative_delta for d in b.deltas]

    def test_unknown_metric_lookup_returns_none(self) -> None:
        report = compare_runs("s", BASE, run(), WEIGHTS)
        assert report.delta("not_a_metric") is None
