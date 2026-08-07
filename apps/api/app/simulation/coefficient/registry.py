"""Deterministic coefficient registry for simulation forecast models.

Every forecast model reads its numeric assumptions from a :class:`Coefficients`
value object, never from code constants or learned data. Coefficients are
seeded with school-wide defaults and can be overridden per scenario via
:meth:`Coefficients.merged`.

Band tables (``attn_timing_bands``, ``attn_class_size_bands``,
``perf_class_size_bands``) are keyed by deterministic band names — lookup
tables, never trained.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar

# Sentinel so ``merged`` can distinguish "absent" from an explicit override
# of ``None``.
_UNSET: ClassVar[Any] = object()


@dataclass(frozen=True)
class Coefficients:
    """Default coefficients shared by all deterministic models.

    Money coefficients are integer minor units.
    """

    # -- Revenue model (``forecasts/revenue.py``) -------------------------
    collection_recovery: float = 0.85
    """Fraction of billed tuition expected to be collected (0.0–1.0)."""

    # -- Workload model (``forecasts/workload.py``) -----------------------
    service_hours_norm: float = 20.0
    """Weekly hours a section demands (the "needed time" per section)."""

    teacher_admin_fixed_hours: float = 4.0
    """Fixed weekly admin hours added to every teacher's load."""

    teacher_capacity_student_hours: float = 600.0
    """Weekly student-hour capacity per teacher (load = hours × students)."""

    # -- Attendance model (``forecasts/attendance.py``) --------------------
    attn_timing_bands: dict[str, float] = field(
        default_factory=lambda: {
            "standard": 0.0,
            "early_start": -0.5,
            "long_day": -1.0,
            "extended_periods": -1.5,
        }
    )
    """Attendance % delta per school-timing band."""

    attn_class_size_bands: dict[str, float] = field(
        default_factory=lambda: {
            "reduced": 0.8,
            "standard": 0.0,
            "increased": -1.0,
        }
    )
    """Attendance % delta per class-size band."""

    attn_transport_penalty_per_student: float = 0.2
    """Attendance % points lost per student without a bus seat."""

    # -- Dropout model (``forecasts/dropout.py``) --------------------------
    dropout_fee_pressure_per_pct: float = 0.30
    """Dropout % points added per 1% tuition increase."""

    dropout_retention_bonus_per_pct: float = 0.15
    """Dropout % points removed per 1% scholarship increase."""

    # -- Budget model (``forecasts/budget.py``) ----------------------------
    teacher_annual_cost_minor: int = 360_000_00
    """Average annual teacher cost in minor units (₹3,60,000)."""

    bus_annual_cost_minor: int = 1_200_000_00
    """Average annual cost per bus in minor units (₹12,00,000)."""

    room_annual_cost_minor: int = 60_000_00
    """Average annual cost per room in minor units (₹6,00,000)."""

    # -- Transport model (``forecasts/transport.py``) ----------------------
    bus_seats: int = 40
    """Seats per bus."""

    # -- Performance model (``forecasts/performance.py``) ------------------
    perf_class_size_bands: dict[str, float] = field(
        default_factory=lambda: {
            "reduced": 2.0,
            "standard": 0.0,
            "increased": -3.0,
        }
    )
    """Performance score delta per class-size band."""

    perf_hours_effect_per_minute: float = 0.02
    """Performance score delta per weekly-minute of instruction change."""

    # -- Resource model (``forecasts/resource.py``) ------------------------
    resource_weights: dict[str, float] = field(
        default_factory=lambda: {
            "teacher": 0.3,
            "rooms": 0.3,
            "fleet": 0.2,
            "transport": 0.2,
        }
    )
    """Documented resource-utilisation weights (normalised before use)."""

    # -- Comparison (``engine/compare.py``) ---------------------------------
    comparison_weights: dict[str, float] = field(
        default_factory=lambda: {
            "revenue": 1.0,
            "budget": 1.0,
            "attendance": 1.0,
            "performance": 1.0,
            "workload": -1.0,
            "dropout": -1.0,
            "rooms": 0.5,
            "transport": -0.5,
            "resource": -0.5,
        }
    )
    """Signed composite-score weights: positive = rise is good, negative =
    rise is bad (dropout, workload utilisation, …)."""

    def merged(self, overrides: dict[str, Any]) -> Coefficients:
        """Return a copy with the given field-level overrides applied.

        Raises:
            ValueError: if an override names an unknown coefficient.
        """
        known = {f.name for f in fields(self)}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError(f"Unknown coefficient(s): {sorted(unknown)}")
        return self.__class__(
            **{f.name: overrides[f.name] for f in fields(self) if f.name in overrides}
        )
