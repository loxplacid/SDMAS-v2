"""Resource utilization forecast (deterministic).

Composite, weighted aggregation over the teacher / room / fleet / transport
utilisations already computed upstream, grouped per resource category with
explicit, documented weights from the coefficient registry (normalised to
sum to one before use).
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec


def _compute(context, prior) -> MetricResult:
    co = context.coefficients
    weights = co.resource_weights
    denominator = sum(weights.values()) or 1.0

    teacher_util = float(prior["workload"].breakdown["utilization_avg"])
    rooms_util = prior["rooms"].value
    transport_util = prior["transport"].value
    fleet_util = transport_util  # fleet utilisation == transport utilisation

    value = (
        weights.get("teacher", 0.0) * teacher_util
        + weights.get("rooms", 0.0) * rooms_util
        + weights.get("fleet", 0.0) * fleet_util
        + weights.get("transport", 0.0) * transport_util
    ) / denominator

    return MetricResult(
        metric_id="resource",
        value=round(value, 4),
        unit="utilization",
        breakdown={
            "teacher": round(teacher_util, 4),
            "rooms": round(rooms_util, 4),
            "fleet": round(fleet_util, 4),
            "transport": round(transport_util, 4),
            "weights": {k: weights.get(k, 0.0) for k in ("teacher", "rooms", "fleet", "transport")},
        },
    )


def resource_spec() -> MetricSpec:
    return MetricSpec(
        metric_id="resource", inputs=("workload", "rooms", "transport"), compute=_compute
    )
