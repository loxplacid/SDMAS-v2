"""Room utilization forecast (deterministic).

``avail_periods = rooms × periods_per_day × day_length``
``used = Σ class periods (every section occupies every period)``
``util = used / avail_periods``, with the concurrent peak reported alongside.

If a school needs more sections than it has rooms, the model flags
``insufficient_rooms`` instead of faking a utilisation.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snap = context.snapshot
    periods = snap.schedule.periods_per_day * snap.schedule.day_length_days
    n_sections = sum(snap.sections_for(g) for g in snap.enrollment)
    used = n_sections * periods
    avail = snap.rooms * periods

    utilization = used / avail if avail else 0.0
    peak = n_sections / snap.rooms if snap.rooms else 0.0

    return MetricResult(
        metric_id="rooms",
        value=round(min(utilization, 1.0), 4),
        unit="utilization",
        breakdown={
            "rooms": snap.rooms,
            "sections": n_sections,
            "used_periods": used,
            "avail_periods": avail,
            # Raw ratio may exceed 1.0 when over-subscribed; the capped value
            # keeps utilization a 0-1 number like the other util metrics and
            # the ``insufficient_rooms`` flag carries the breach.
            "raw_utilization": round(utilization, 4),
            "peak_concurrent": round(peak, 4),
        },
        flags=("insufficient_rooms",) if n_sections > snap.rooms else (),
    )


def rooms_spec() -> MetricSpec:
    return MetricSpec(metric_id="rooms", inputs=(), compute=_compute)
