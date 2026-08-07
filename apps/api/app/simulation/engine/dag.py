"""The dependency DAG that drives forecast execution.

A :class:`MetricSpec` metadata-declares one consequence metric plus the
metric ids it depends on. The :class:`DependencyEngine` topologically sorts
the specs, rejects cycles at define-time, and evaluates each metric exactly
once with its dependencies already memoised — so adding a model never requires
touching the runner (the DAG is pure metadata).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.simulation.model.context import SimulationContext

# A forecast compute function: reads a frozen context + the already-computed
# results of its declared inputs, and returns a metric result.
ComputeFn = Callable[["SimulationContext", dict[str, "MetricResult"]], "MetricResult"]


@dataclass(frozen=True)
class MetricResult:
    """Immutable output of one forecast model."""

    metric_id: str
    value: float
    unit: str
    breakdown: dict[str, object] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    # ^ constraint-style flags (e.g. "insufficient_fleet",
    #   "over_capacity_grade_2") — the engine never fakes a number when
    #   capacity is breached; it flags instead (see SIMULATION_ENGINE.md).


@dataclass(frozen=True)
class MetricSpec:
    """Declaration of one consequence metric and its dependency inputs."""

    metric_id: str
    compute: ComputeFn
    inputs: tuple[str, ...] = ()


class DependencyEngine:
    """Executes a fixed set of registered metric specs in dependency order."""

    def __init__(self, specs: list[MetricSpec]) -> None:
        self._specs: dict[str, MetricSpec] = {}
        for spec in specs:
            if spec.metric_id in self._specs:
                raise ValueError(f"Duplicate metric registered: {spec.metric_id}")
            self._specs[spec.metric_id] = spec
        self._order = self._topological_order()

    def _topological_order(self) -> list[str]:
        # Kahn's algorithm; reject any remaining edge as a cycle.
        indegree = {mid: 0 for mid in self._specs}
        for spec in self._specs.values():
            for dep in spec.inputs:
                if dep not in self._specs:
                    raise ValueError(f"Metric {spec.metric_id} depends on unknown {dep!r}")
                indegree[spec.metric_id] += 1
        ready = [mid for mid in self._specs if indegree[mid] == 0]
        order: list[str] = []
        while ready:
            mid = ready.pop()
            order.append(mid)
            for other, spec in self._specs.items():
                if mid in spec.inputs:
                    indegree[other] -= 1
                    if indegree[other] == 0:
                        ready.append(other)
        if len(order) != len(self._specs):
            cyclic = [mid for mid in self._specs if mid not in order]
            raise ValueError(f"Cycle detected among metrics: {sorted(cyclic)}")
        return order

    def run(self, context: SimulationContext) -> dict[str, MetricResult]:
        """Evaluate every metric once, in dependency order, and memoise."""
        results: dict[str, MetricResult] = {}
        for mid in self._order:
            spec = self._specs[mid]
            prior = {dep: results[dep] for dep in spec.inputs}
            results[mid] = spec.compute(context, prior)
        return results
