"""Dropout (retention) forecast (deterministic).

Links to the school's own persisted deterministic risk score — no new model
is invented:

``dropout_prob = clamp(base_risk_pct
                     + fee_pressure (tuition/scholarship lever effects)
                     − retention_bonus (from scholarship increase), 0, 100)``

Pressure is a pure function of the *delta* between the baseline snapshot and
the scenario-adjusted snapshot held in ``context.baseline``.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec
from app.simulation.forecasts.common import clamp, enrollment_weighted


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snap = context.snapshot
    base = context.baseline
    co = context.coefficients

    per_grade: dict[int, float] = {}
    for grade in sorted(snap.enrollment):
        fee_pressure = 0.0
        retention = 0.0
        if base is not None:
            base_rate = base.fee_rate.get(grade, 0)
            if base_rate > 0:
                fee_pct = (snap.fee_rate[grade] - base_rate) / base_rate * 100.0
                fee_pressure = fee_pct * co.dropout_fee_pressure_per_pct
            base_grant = base.scholarship_grants.get(grade, 0)
            if base_grant > 0:
                grant_pct = (
                    (snap.scholarship_grants.get(grade, 0) - base_grant) / base_grant * 100.0
                )
                retention = grant_pct * co.dropout_retention_bonus_per_pct
        per_grade[grade] = round(
            clamp(
                snap.base_risk.get(grade, 0.0) + fee_pressure - retention,
                0.0,
                100.0,
            ),
            2,
        )

    return MetricResult(
        metric_id="dropout",
        value=round(enrollment_weighted(per_grade, snap.enrollment), 4),
        unit="percent",
        breakdown={"per_grade": {str(g): v for g, v in per_grade.items()}},
    )


def dropout_spec() -> MetricSpec:
    return MetricSpec(metric_id="dropout", inputs=(), compute=_compute)
