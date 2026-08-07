"""Budget impact model — the full cost lines via DAG dependency reuse.

``budget_Δ = revenue − cost(teachers) − cost(fleet) − cost(rooms)
             − scholarships``

Every cost line is a pure function of already-computed upstream metrics
(workload carries the teacher count, transport carries the fleet size, rooms
carries the room count) times registry coefficients — demonstrating the
dependency DAG end to end.
"""

from __future__ import annotations

from app.simulation.engine.dag import MetricResult, MetricSpec


def _compute(context, prior) -> MetricResult:
    snap = context.snapshot
    co = context.coefficients

    revenue = prior["revenue"].value
    teacher_cost = int(prior["workload"].breakdown["n_teachers"]) * co.teacher_annual_cost_minor
    fleet_cost = int(prior["transport"].breakdown["fleet_size"]) * co.bus_annual_cost_minor
    room_cost = int(prior["rooms"].breakdown["rooms"]) * co.room_annual_cost_minor
    scholarships = float(snap.scholarships())

    budget = revenue - teacher_cost - fleet_cost - room_cost - scholarships
    return MetricResult(
        metric_id="budget",
        value=round(budget, 2),
        unit="revenue_minor_units",
        breakdown={
            "revenue": revenue,
            "expense_teachers": float(teacher_cost),
            "expense_fleet": float(fleet_cost),
            "expense_rooms": float(room_cost),
            "expense_scholarships": scholarships,
        },
    )


def budget_spec() -> MetricSpec:
    """Budget depends on revenue, workload, transport and rooms."""
    return MetricSpec(
        metric_id="budget",
        inputs=("revenue", "workload", "transport", "rooms"),
        compute=_compute,
    )
