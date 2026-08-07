"""Scenario-vs-baseline comparison.

Any scenario can be compared to its baseline (or another scenario over the
same baseline snapshot). A :class:`ComparisonReport` holds per-metric
deltas (absolute + relative), a direction (up / down / neutral), flag
propagation from any capacity-breach flags, and a single documented
composite score: the signed, clamped, weight-scaled sum of relative deltas
(weights from the coefficient registry — a rise in dropout lowers the score).

Comparison is a pure function of two already-computed result dicts; it can be
re-rendered any number of times without recomputing the metrics.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.simulation.engine.dag import MetricResult

_EPSILON = 1e-9


@dataclass(frozen=True)
class MetricDelta:
    """One metric's baseline → scenario movement."""

    metric_id: str
    base_value: float
    scenario_value: float
    absolute_delta: float
    relative_delta: float | None  # None when base value is zero
    direction: str  # "up" | "down" | "neutral"
    flagged: bool  # capacity-breach flag carried by the scenario run


@dataclass(frozen=True)
class ComparisonReport:
    """Immutable comparison; safe to store and re-render."""

    scenario_id: str
    composite_score: float
    deltas: tuple[MetricDelta, ...]

    def delta(self, metric_id: str) -> MetricDelta | None:
        for entry in self.deltas:
            if entry.metric_id == metric_id:
                return entry
        return None

    def flagged_metrics(self) -> tuple[str, ...]:
        return tuple(d.metric_id for d in self.deltas if d.flagged)


def compare_runs(
    scenario_id: str,
    base: dict[str, MetricResult],
    scenario: dict[str, MetricResult],
    weights: dict[str, float] | None = None,
) -> ComparisonReport:
    """Compute deltas and the composite score for one scenario vs baseline.

    ``weights`` are signed importance weights keyed by metric id (defaults:
    the registry's ``comparison_weights``; callers pass the resolved
    scenario coefficients). Relative deltas use ``abs(base)`` as the
    denominator so the sign always reflects the direction of change — even
    for metrics whose baseline is negative (e.g. a deficit budget that
    improves). Relative deltas are clamped to ±1 before the weighted sum so
    no single metric dominates.
    """
    weights = weights or {}
    deltas: list[MetricDelta] = []
    composite = 0.0
    for metric_id, base_result in sorted(base.items()):
        scenario_result = scenario.get(metric_id)
        if scenario_result is None:
            continue
        base_value = base_result.value
        scenario_value = scenario_result.value
        absolute = scenario_value - base_value
        relative = (absolute / abs(base_value)) if base_value else None
        direction = "up" if absolute > _EPSILON else ("down" if absolute < -_EPSILON else "neutral")
        # Flag only the scenario side: a run that *repairs* a baseline breach
        # must not keep the breach flag on the comparison.
        flagged = bool(scenario_result.flags)
        deltas.append(
            MetricDelta(
                metric_id=metric_id,
                base_value=base_value,
                scenario_value=scenario_value,
                absolute_delta=round(absolute, 6),
                relative_delta=round(relative, 6) if relative is not None else None,
                direction=direction,
                flagged=flagged,
            )
        )
        if relative is not None and metric_id in weights:
            composite += weights[metric_id] * max(min(relative, 1.0), -1.0)

    return ComparisonReport(
        scenario_id=scenario_id,
        composite_score=round(composite, 6),
        deltas=tuple(deltas),
    )
