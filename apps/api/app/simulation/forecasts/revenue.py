"""Revenue impact forecast (deterministic).

Gross tuition at the scenario-adjusted rates, minus scholarships already
granted, scaled by a collection-recovery coefficient. Pure function of the
frozen snapshot — identical inputs always yield identical output.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snapshot = context.snapshot
    gross: float = float(snapshot.gross_tuition())
    scholarships: float = float(snapshot.scholarships())
    billed: float = gross - scholarships
    recovery = context.coefficients.collection_recovery
    expected = billed * recovery
    return MetricResult(
        metric_id="revenue",
        value=round(expected, 2),
        unit="revenue_minor_units",
        breakdown={
            "gross": round(gross, 2),
            "scholarships": round(scholarships, 2),
            "expected_collection": round(expected, 2),
        },
    )


def revenue_spec() -> MetricSpec:
    """Return the revenue metric spec (a root: no dependencies)."""
    return MetricSpec(metric_id="revenue", inputs=(), compute=_compute)
