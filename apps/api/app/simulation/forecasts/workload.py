"""Teacher workload forecast (deterministic).

Sections are the unit of teaching demand: each section demands
``service_hours_norm × section_size`` student-hours per week, plus a fixed
admin allowance per teacher. Teachers are filled in deterministic priority
order (tenure descending, then teacher id), exactly the redistribution rule
for a removed teacher. If a grade's remaining teachers cannot cover its
sections, the model flags ``over_capacity_grade_<g>`` rather than inventing
a feasible number.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec


def _compute(context, prior) -> MetricResult:  # noqa: ARG001
    snap = context.snapshot
    co = context.coefficients
    admin = co.teacher_admin_fixed_hours
    capacity = co.teacher_capacity_student_hours
    norm = co.service_hours_norm

    per_teacher: dict[str, float] = {}
    total_load = 0.0
    demand_total = 0.0
    shortfall_total = 0.0
    flags: list[str] = []
    for grade in sorted(snap.enrollment):
        teachers = sorted(
            (t for t in snap.teachers if t.grade == grade),
            key=lambda t: (-t.tenure, t.teacher_id),
        )
        demand_per_section = norm * snap.section_size(grade)
        grade_demand = snap.sections_for(grade) * demand_per_section
        demand_total += grade_demand
        remaining = snap.sections_for(grade)
        for teacher in teachers:
            if demand_per_section > 0:
                cap_sections = int((capacity - admin) / demand_per_section)
            else:
                cap_sections = remaining
            take = min(remaining, max(cap_sections, 0))
            load = take * demand_per_section + admin
            per_teacher[str(teacher.teacher_id)] = round(load, 2)
            total_load += load
            remaining -= take
        if remaining > 0:
            flags.append(f"over_capacity_grade_{grade}")
            shortfall_total += remaining * demand_per_section

    utilization = total_load / (len(snap.teachers) * capacity) if snap.teachers else 0.0
    return MetricResult(
        metric_id="workload",
        value=round(utilization, 4),
        unit="utilization",
        breakdown={
            "utilization_avg": round(utilization, 4),
            "n_teachers": len(snap.teachers),
            # Demand is what the grade actually needs; the flag is actionable
            # because the shortfall (uncovered student-hours) is reported.
            "demand_student_hours": round(demand_total, 2),
            "shortfall_student_hours": round(shortfall_total, 2),
            "total_load_student_hours": round(total_load, 2),
            "per_teacher": per_teacher,
        },
        flags=tuple(flags),
    )


def workload_spec() -> MetricSpec:
    """Workload is a root metric: it reads only the frozen context."""
    return MetricSpec(metric_id="workload", inputs=(), compute=_compute)
