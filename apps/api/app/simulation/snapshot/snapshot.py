"""Frozen baseline snapshot the simulation models run against.

A snapshot is immutable and captures only the fields the deterministic
forecast models read. It is built once from batched school SQL and shared by
every run so all scenarios compare against the same base.

Money amounts are integer minor units (paise / cents), matching the domain
convention documented in ``ARCHITECTURE.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TeacherRecord:
    """One teacher's deterministic baseline assignment."""

    teacher_id: int
    grade: int
    service_hours: int = 20  # weekly hours taught per section
    tenure: int = 0  # years of service — deterministic reprioritisation


@dataclass(frozen=True)
class Schedule:
    """School timing model (mutated by the ``ChangeSchedule`` lever)."""

    day_start: str = "08:30"
    periods_per_day: int = 8
    period_minutes: int = 45
    day_length_days: int = 5

    def weekly_minutes(self) -> int:
        return self.periods_per_day * self.period_minutes * self.day_length_days


@dataclass(frozen=True)
class SimulationSnapshot:
    """Baseline school state.

    Attributes:
        campus_id: Scoping campus. Plain data here; tenancy enforcement is
            applied by the persistence layer on top of this model.
        academic_year: Year label this baseline was captured for.
        fee_rate: Grade -> tuition per student (minor units).
        enrollment: Grade -> number of enrolled students.
        scholarship_grants: Grade -> total scholarship already granted (minor).
        teachers: Baseline teaching staff (drives workload / budget).
        section_sizes: Grade -> students per section (drives class-size
            effects and room utilisation).
        fleet_size: Number of buses (drives transport / budget).
        transport_demand: Students who need a bus seat (drives transport).
        routes: Number of bus routes.
        rooms: Number of teaching rooms (drives room utilisation).
        base_attendance: Grade -> baseline attendance % (drives attendance).
        base_risk: Grade -> baseline deterministic risk score % (drives
            dropout, linking to the school's own ``domains/risk`` numbers).
        base_performance: Grade -> baseline performance score 0-100.
        schedule: School timing model.
    """

    campus_id: int
    academic_year: str
    fee_rate: dict[int, int]
    enrollment: dict[int, int]
    scholarship_grants: dict[int, int] = field(default_factory=dict)
    teachers: tuple[TeacherRecord, ...] = ()
    section_sizes: dict[int, int] = field(default_factory=dict)
    fleet_size: int = 0
    transport_demand: int = 0
    routes: int = 0
    rooms: int = 0
    base_attendance: dict[int, float] = field(default_factory=dict)
    base_risk: dict[int, float] = field(default_factory=dict)
    base_performance: dict[int, float] = field(default_factory=dict)
    schedule: Schedule = field(default_factory=Schedule)

    def gross_tuition(self) -> int:
        """Total tuition at current rates before adjustments (minor units)."""
        return sum(rate * self.enrollment[grade] for grade, rate in self.fee_rate.items())

    def scholarships(self) -> int:
        """Total scholarships already granted (minor units)."""
        return sum(self.scholarship_grants.values())

    def section_size(self, grade: int) -> int:
        """Students per section for a grade (defaults to 1)."""
        return self.section_sizes.get(grade, 1)

    def sections_for(self, grade: int) -> int:
        """Deterministic section count: sections fill up before splitting."""
        size = self.section_size(grade)
        return math.ceil(self.enrollment.get(grade, 0) / size) if size > 0 else 0

    def teacher_count(self) -> int:
        return len(self.teachers)
