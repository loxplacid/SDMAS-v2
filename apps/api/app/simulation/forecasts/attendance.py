"""Attendance prediction forecast (deterministic).

``expected_attn[class] = base_attn[class]
                      + Δ_timing(schedule band)
                      + Δ_transport(bus seats vs demand)
                      + Δ_class_size(class-size band)``

All three Δ terms are coefficient-registry lookup tables keyed by
deterministic bands — no sampling, no learned weights.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec
from app.simulation.forecasts.common import (
    clamp,
    class_size_band,
    enrollment_weighted,
    timing_band,
)


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snap = context.snapshot
    co = context.coefficients

    band = timing_band(snap.schedule)
    timing_delta = co.attn_timing_bands.get(band, 0.0)

    seat_capacity = co.bus_seats * snap.fleet_size
    shortfall = max(0, snap.transport_demand - seat_capacity)
    transport_delta = -shortfall * co.attn_transport_penalty_per_student

    per_grade: dict[int, float] = {}
    for grade in sorted(snap.enrollment):
        size_band = class_size_band(snap.section_size(grade))
        size_delta = co.attn_class_size_bands.get(size_band, 0.0)
        base = snap.base_attendance.get(grade, 0.0)
        per_grade[grade] = round(
            clamp(base + timing_delta + size_delta + transport_delta, 0.0, 100.0), 2
        )

    return MetricResult(
        metric_id="attendance",
        value=round(enrollment_weighted(per_grade, snap.enrollment), 4),
        unit="percent",
        breakdown={
            "timing_band": band,
            "timing_delta": timing_delta,
            "transport_shortfall": shortfall,
            "per_grade": {str(g): v for g, v in per_grade.items()},
        },
        flags=("transport_shortfall",) if shortfall > 0 else (),
    )


def attendance_spec() -> MetricSpec:
    return MetricSpec(metric_id="attendance", inputs=(), compute=_compute)
