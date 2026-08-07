"""Transport load forecast (deterministic).

``util = assigned / (seats × buses)`` where ``assigned = min(demand, capacity)``.
``midday_peak = max load on any single bus``.

When ``demand > capacity`` the model flags ``insufficient_fleet`` — it never
fakes a load number (same rule as the rest of the engine).
"""

from __future__ import annotations

import math

from app.simulation.engine.dag import MetricResult, MetricSpec


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snap = context.snapshot
    co = context.coefficients
    capacity = co.bus_seats * snap.fleet_size
    assigned = min(snap.transport_demand, capacity)
    utilization = assigned / capacity if capacity else 0.0
    peak = (
        min(co.bus_seats, math.ceil(snap.transport_demand / snap.fleet_size))
        if snap.fleet_size
        else 0
    )

    return MetricResult(
        metric_id="transport",
        value=round(utilization, 4),
        unit="utilization",
        breakdown={
            "fleet_size": snap.fleet_size,
            "bus_seats": co.bus_seats,
            "seat_capacity": capacity,
            "demand": snap.transport_demand,
            "assigned": assigned,
            "midday_peak": peak,
        },
        flags=("insufficient_fleet",) if snap.transport_demand > capacity else (),
    )


def transport_spec() -> MetricSpec:
    return MetricSpec(metric_id="transport", inputs=(), compute=_compute)
