"""Shared deterministic helpers for the forecast models.

Band classification is pure lookup: the same schedule/section-size always
maps to the same band, and the band tables live in the coefficient registry
(never trained, never random).
"""

from __future__ import annotations

from app.simulation.snapshot.snapshot import Schedule


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def timing_band(schedule: Schedule) -> str:
    """Classify a school timing into a band for the attendance model."""
    if schedule.periods_per_day > 8:
        return "extended_periods"
    if schedule.period_minutes > 45:
        return "long_day"
    if schedule.day_start < "08:30":
        return "early_start"
    return "standard"


def class_size_band(size: int) -> str:
    """Classify a section size into a band for attendance/performance."""
    if size < 25:
        return "reduced"
    if size > 35:
        return "increased"
    return "standard"


def enrollment_weighted(per_grade: dict[int, float], enrollment: dict[int, int]) -> float:
    """Enrollment-weighted average over grades, deterministic."""
    total = sum(enrollment.get(g, 0) for g in per_grade)
    if total == 0:
        return 0.0
    return sum(per_grade[g] * enrollment[g] for g in per_grade) / total
