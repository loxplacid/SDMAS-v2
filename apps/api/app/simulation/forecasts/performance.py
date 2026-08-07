"""Student performance forecast (deterministic).

``Δperf[class] = coeff[band_of_new_class_size] + hours_effect``
``perf[class] = base_perf[class] + Δperf (capped 0–100)``

The hours effect is the change in weekly instruction minutes versus the
baseline schedule times a fixed per-minute coefficient. Coefficients are
band lookup tables in the registry — copied, never learned.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec
from app.simulation.forecasts.common import clamp, class_size_band, enrollment_weighted


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snap = context.snapshot
    base = context.baseline
    co = context.coefficients

    hours_effect = 0.0
    if base is not None:
        hours_effect = (
            snap.schedule.weekly_minutes() - base.schedule.weekly_minutes()
        ) * co.perf_hours_effect_per_minute

    per_grade: dict[int, float] = {}
    for grade in sorted(snap.enrollment):
        band = class_size_band(snap.section_size(grade))
        size_effect = co.perf_class_size_bands.get(band, 0.0)
        per_grade[grade] = round(
            clamp(
                snap.base_performance.get(grade, 0.0) + size_effect + hours_effect,
                0.0,
                100.0,
            ),
            2,
        )

    return MetricResult(
        metric_id="performance",
        value=round(enrollment_weighted(per_grade, snap.enrollment), 4),
        unit="score",
        breakdown={
            "hours_effect": round(hours_effect, 4),
            "per_grade": {str(g): v for g, v in per_grade.items()},
        },
    )


def performance_spec() -> MetricSpec:
    return MetricSpec(metric_id="performance", inputs=(), compute=_compute)
