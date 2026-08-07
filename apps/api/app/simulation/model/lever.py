"""Scenario levers — the deterministic "what if…" input changes.

A :class:`Lever` is a frozen, validated mutation descriptor. Its
:meth:`Lever.apply` returns an *updated* snapshot copy (the source snapshot is
never mutated), which is what keeps the whole pipeline pure and reproducible.

Every lever in the product brief is implemented: ``FeeMultiplier`` (+7%
tuition), ``ScholarshipDelta`` (scholarships), ``RemoveTeacher``,
``AddBuses``, ``ChangeSchedule`` (school timing), ``ClassSizeChange``
(capacity cap + rebalancing) and ``MergeClasses``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from app.simulation.snapshot.snapshot import SimulationSnapshot


@dataclass(frozen=True)
class Lever:
    """Base class. Subclasses implement :meth:`validate` and :meth:`apply`."""

    def validate(self, snapshot: SimulationSnapshot) -> None:
        """Raise ``ValueError`` if this lever cannot apply to *snapshot*."""

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        """Return a new snapshot reflecting this lever's change. Pure."""
        raise NotImplementedError


def _scale_minor(amount: int, factor: float) -> int:
    """Scale a minor-unit (integer) amount by a float factor, rounded."""
    return round(amount * factor)


# ---------------------------------------------------------------------------
# Money levers (revenue-relevant).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeeMultiplier(Lever):
    """Scale every grade's tuition by ``factor`` (e.g. 1.07 = +7%)."""

    factor: Final[float]

    def validate(self, snapshot: SimulationSnapshot) -> None:  # noqa: ARG002
        if self.factor <= 0:
            raise ValueError("FeeMultiplier.factor must be > 0")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        return replace(
            snapshot,
            fee_rate={g: _scale_minor(v, self.factor) for g, v in snapshot.fee_rate.items()},
        )


@dataclass(frozen=True)
class ScholarshipDelta(Lever):
    """Scale existing scholarship grants by ``factor`` (e.g. 1.5 = +50%)."""

    factor: float = 1.0

    def validate(self, snapshot: SimulationSnapshot) -> None:  # noqa: ARG002
        if self.factor < 0:
            raise ValueError("ScholarshipDelta.factor must be >= 0")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        return replace(
            snapshot,
            scholarship_grants={
                g: _scale_minor(v, self.factor) for g, v in snapshot.scholarship_grants.items()
            },
        )


# ---------------------------------------------------------------------------
# Staffing levers.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemoveTeacher(Lever):
    """Remove one teacher; workload redistributes or flags over-capacity."""

    teacher_id: int

    def validate(self, snapshot: SimulationSnapshot) -> None:
        if not any(t.teacher_id == self.teacher_id for t in snapshot.teachers):
            raise ValueError(f"RemoveTeacher: teacher {self.teacher_id} not in snapshot")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        return replace(
            snapshot,
            teachers=tuple(t for t in snapshot.teachers if t.teacher_id != self.teacher_id),
        )


@dataclass(frozen=True)
class AddBuses(Lever):
    """Add ``count`` buses to the fleet. Affects transport/fleet costs."""

    count: int = 0

    def validate(self, snapshot: SimulationSnapshot) -> None:  # noqa: ARG002
        if self.count < 0:
            raise ValueError("AddBuses.count must be >= 0")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        return replace(snapshot, fleet_size=snapshot.fleet_size + self.count)


# ---------------------------------------------------------------------------
# Schedule lever.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeSchedule(Lever):
    """Change school timing; affects attendance, rooms, performance."""

    day_start: str | None = None
    periods_per_day: int | None = None
    period_minutes: int | None = None

    def validate(self, snapshot: SimulationSnapshot) -> None:  # noqa: ARG002
        if self.periods_per_day is not None and self.periods_per_day <= 0:
            raise ValueError("ChangeSchedule.periods_per_day must be > 0")
        if self.period_minutes is not None and self.period_minutes <= 0:
            raise ValueError("ChangeSchedule.period_minutes must be > 0")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        current = snapshot.schedule
        return replace(
            snapshot,
            schedule=replace(
                current,
                day_start=(self.day_start if self.day_start is not None else current.day_start),
                periods_per_day=(
                    self.periods_per_day
                    if self.periods_per_day is not None
                    else current.periods_per_day
                ),
                period_minutes=(
                    self.period_minutes
                    if self.period_minutes is not None
                    else current.period_minutes
                ),
            ),
        )


# ---------------------------------------------------------------------------
# Class-size lever (capacity cap + deterministic rebalancing).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassSizeChange(Lever):
    """Cap section size at ``cap``; oversized sections split into more,
    smaller sections (deterministic rebalancing). Affects teacher load,
    rooms and class-size effects."""

    cap: int | None = None

    def validate(self, snapshot: SimulationSnapshot) -> None:  # noqa: ARG002
        if self.cap is not None and self.cap <= 0:
            raise ValueError("ClassSizeChange.cap must be > 0")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        if self.cap is None:
            return snapshot
        return replace(
            snapshot,
            section_sizes={
                g: min(size, self.cap)
                for g, size in snapshot.section_sizes.items()
                if g in snapshot.enrollment
            },
        )


# ---------------------------------------------------------------------------
# Merge-classes lever (fold one grade into another, rebalancing baselines).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MergeClasses(Lever):
    """Merge ``source_grade`` into ``target_grade``.

    Enrollment, scholarships and section sizes move to the target; fee rate
    follows the target; attendance/risk/performance baselines merge as
    enrollment-weighted averages; teachers of the source grade are
    re-assigned to the target grade. Deterministic by construction.
    """

    source_grade: int
    target_grade: int = 1

    def validate(self, snapshot: SimulationSnapshot) -> None:
        if self.source_grade == self.target_grade:
            raise ValueError("MergeClasses: source and target must differ")
        if self.source_grade not in snapshot.enrollment:
            raise ValueError(f"MergeClasses: source grade {self.source_grade} not enrolled")

    def apply(self, snapshot: SimulationSnapshot) -> SimulationSnapshot:
        src, tgt = self.source_grade, self.target_grade
        src_n = snapshot.enrollment.get(src, 0)
        tgt_n = snapshot.enrollment.get(tgt, 0)
        total = src_n + tgt_n

        def merge_value(table: dict[int, float], default: float = 0.0) -> float:
            if total == 0:
                return default
            src_v = table.get(src, default)
            tgt_v = table.get(tgt, default)
            return (src_v * src_n + tgt_v * tgt_n) / total

        enrollment = {g: n for g, n in snapshot.enrollment.items() if g != src}
        enrollment[tgt] = total

        fee_rate = {g: r for g, r in snapshot.fee_rate.items() if g != src}
        if tgt in snapshot.fee_rate:  # target rate wins
            fee_rate[tgt] = snapshot.fee_rate[tgt]
        elif src in snapshot.fee_rate:
            fee_rate[tgt] = snapshot.fee_rate[src]

        scholarships = {g: v for g, v in snapshot.scholarship_grants.items() if g != src}
        scholarships[tgt] = snapshot.scholarship_grants.get(
            tgt, 0
        ) + snapshot.scholarship_grants.get(src, 0)

        section_sizes = {g: s for g, s in snapshot.section_sizes.items() if g != src}
        if tgt not in section_sizes and src in snapshot.section_sizes:
            section_sizes[tgt] = snapshot.section_sizes[src]

        teachers = tuple(replace(t, grade=tgt) if t.grade == src else t for t in snapshot.teachers)

        return replace(
            snapshot,
            enrollment=enrollment,
            fee_rate=fee_rate,
            scholarship_grants=scholarships,
            section_sizes=section_sizes,
            teachers=teachers,
            base_attendance={
                **{g: v for g, v in snapshot.base_attendance.items() if g != src},
                tgt: merge_value(snapshot.base_attendance, 0.0),
            },
            base_risk={
                **{g: v for g, v in snapshot.base_risk.items() if g != src},
                tgt: merge_value(snapshot.base_risk, 0.0),
            },
            base_performance={
                **{g: v for g, v in snapshot.base_performance.items() if g != src},
                tgt: merge_value(snapshot.base_performance, 0.0),
            },
        )


# Convenience alias for type annotation sites.
LeverSet: Final = tuple[Lever, ...]
