"""End-to-end tests for the invigilation adapter (the working example).

Coverage:
- Feasible instance solves to OPTIMAL with a zero soft objective
- Hard-constraint audit: the interpreted solution is verified
  independently of the solver's self-report
- Warm starts: greedy hints seed the search; a changed problem is repaired
  from a previous solution
- Conflict explanation: known-infeasible instances name the expected
  constraints and suggest domain-language relaxations
"""

from __future__ import annotations

import pytest

from app.optimization.adapters.invigilation import (
    Exam,
    InvigilationAdapter,
    InvigilationProblem,
    Room,
    Teacher,
)
from app.optimization.core.engine import SolveParams, SolverEngine, SolveStatus
from app.optimization.core.explain import ConflictExplainer
from app.optimization.core.model import ModelBuilder


def make_problem(**overrides) -> InvigilationProblem:
    exams = (
        Exam("Math", 30, "math"),
        Exam("Physics", 45, "physics"),
        Exam("Chemistry", 25, "chemistry"),
        Exam("English", 40, "english"),
        Exam("History", 20, "history"),
        Exam("Biology", 35, "biology"),
    )
    rooms = (Room("Hall A", 60), Room("Hall B", 40), Room("Room 12", 30))
    slots = (0, 1, 2, 3)
    teachers = (
        Teacher("T1", "math"),
        Teacher("T2", "physics"),
        Teacher("T3", "english"),
        Teacher("T4", "science"),
    )
    defaults = {
        "exams": exams,
        "rooms": rooms,
        "slots": slots,
        "teachers": teachers,
    }
    defaults.update(overrides)
    return InvigilationProblem(**defaults)


def solve(problem: InvigilationProblem, *, hints=None, gate=False):
    builder = ModelBuilder(gate_hard=gate)
    objective = InvigilationAdapter(problem).build(builder)
    result = SolverEngine().solve(
        builder, objective, params=SolveParams(time_limit_seconds=30.0), hints=hints
    )
    return builder, result


def audit_hard_constraints(problem: InvigilationProblem, solution: dict[str, int]) -> None:
    """Independent hard-constraint audit (OPTIMIZATION_ENGINE.md §17)."""
    n_exams, n_rooms, n_slots, n_teachers = (
        len(problem.exams),
        len(problem.rooms),
        len(problem.slots),
        len(problem.teachers),
    )
    # exactly one teacher per exam
    for e in range(n_exams):
        chosen = [t for t in range(n_teachers) if solution[f"x_{e}_{t}"] == 1]
        assert len(chosen) == 1, f"exam {e} must have exactly one invigilator"
    # room capacity
    for e in range(n_exams):
        room = problem.rooms[solution[f"room_{e}"]]
        assert room.capacity >= problem.exams[e].students, f"exam {e} exceeds capacity"
    # room/slot exclusivity
    occupied = [(solution[f"slot_{e}"], solution[f"room_{e}"]) for e in range(n_exams)]
    assert len(set(occupied)) == n_exams, "two exams share a room in one slot"
    # teacher/slot exclusivity
    for t in range(n_teachers):
        slots_covered = [
            solution[f"slot_{e}"] for e in range(n_exams) if solution[f"x_{e}_{t}"] == 1
        ]
        assert len(slots_covered) == len(set(slots_covered)), f"teacher {t} is double-booked"
    # unavailability
    for e, t in problem.unavailable:
        assert solution[f"x_{e}_{t}"] == 0, f"unavailable pair ({e},{t}) assigned"
    # slot/room indices within range
    for e in range(n_exams):
        assert 0 <= solution[f"slot_{e}"] < n_slots
        assert 0 <= solution[f"room_{e}"] < n_rooms


class TestFeasibleSolve:
    def test_optimal_with_zero_soft_objective(self):
        problem = make_problem()
        builder, result = solve(problem)
        assert result.status is SolveStatus.OPTIMAL
        assert result.objective_value == 0.0
        assert result.solution is not None
        audit_hard_constraints(problem, result.solution)

    def test_interpretation_is_domain_shaped(self):
        problem = make_problem()
        builder = ModelBuilder()
        objective = InvigilationAdapter(problem).build(builder)
        result = SolverEngine().solve(builder, objective, params=SolveParams())
        plan = InvigilationAdapter(problem).interpret(result.solution, builder)
        assert len(plan["assignments"]) == len(problem.exams)
        exams_covered = {a["exam"] for a in plan["assignments"]}
        assert exams_covered == {e.name for e in problem.exams}
        assert all(a["teacher"] for a in plan["assignments"])
        assert all(a["room"] for a in plan["assignments"])


class TestWarmStarts:
    def test_greedy_hints_seed_the_search(self):
        problem = make_problem()
        builder = ModelBuilder()
        objective = InvigilationAdapter(problem).build(builder)
        hints = InvigilationAdapter(problem).hints(builder)
        assert hints, "greedy hints should place at least one exam"
        result = SolverEngine().solve(builder, objective, params=SolveParams(), hints=hints)
        assert result.solved
        assert result.hints_used is True
        assert result.objective_value == 0.0
        audit_hard_constraints(problem, result.solution)

    def test_incremental_repair_from_previous_solution(self):
        """Adding an unavailability that invalidates the previous solution;
        re-solving from it (hints) must restore feasibility and honour the
        new rule."""
        problem = make_problem()
        builder, base = solve(problem)
        assert base.solved
        plan = InvigilationAdapter(problem).interpret(base.solution, builder)
        e_idx, t_idx = 0, 0
        for assignment in plan["assignments"]:
            if assignment["exam"] == problem.exams[0].name:
                t_idx = next(
                    i for i, t in enumerate(problem.teachers) if t.name == assignment["teacher"]
                )
                break
        updated = make_problem(unavailable=problem.unavailable | {(e_idx, t_idx)})
        builder2, result = solve(updated, hints=base.solution)
        assert result.solved, "repair from a previous solution must stay feasible"
        assert result.solution[f"x_{e_idx}_{t_idx}"] == 0
        audit_hard_constraints(updated, result.solution)


class TestValidation:
    """Structural invariants fail fast; *constraint* conflicts (no room
    fits, only teacher unavailable) belong to the conflict explainer and are
    covered by the explanation tests below."""

    def test_empty_collections_fail_fast(self):
        for field, value in (
            ("exams", ()),
            ("rooms", ()),
            ("slots", ()),
            ("teachers", ()),
        ):
            problem = make_problem(**{field: value})
            with pytest.raises(ValueError, match=field):
                InvigilationAdapter(problem).build(ModelBuilder())


class TestConflictExplanation:
    def test_room_clash_is_named(self):
        """Two exams, one slot, one room: only room_slot_conflicts can break."""
        problem = InvigilationProblem(
            exams=(Exam("A", 10), Exam("B", 10)),
            rooms=(Room("Only Hall", 100),),
            slots=(0,),
            teachers=(Teacher("T1"), Teacher("T2")),
        )
        builder, result = solve(problem, gate=True)
        assert result.status is SolveStatus.INFEASIBLE
        report = ConflictExplainer().explain(InvigilationAdapter(problem))
        assert report.feasible is False
        assert "room_slot_conflicts" in report.conflicting_constraints
        assert any("Add a room" in r for r in report.relaxations)
        assert "room_slot_conflicts" in report.render()

    def test_unavailability_clash_is_named(self):
        """One exam, one teacher who is unavailable: exactly_one + the
        unavailability rule both belong to the conflicting core."""
        problem = InvigilationProblem(
            exams=(Exam("A", 10),),
            rooms=(Room("Hall", 100),),
            slots=(0,),
            teachers=(Teacher("OnlyTeacher"),),
            unavailable=frozenset({(0, 0)}),
        )
        report = ConflictExplainer().explain(InvigilationAdapter(problem))
        assert report.feasible is False
        names = set(report.conflicting_constraints)
        assert "teacher_exactly_one_0" in names
        assert "unavailable_0_0" in names

    def test_feasible_problem_reports_clean(self):
        report = ConflictExplainer().explain(InvigilationAdapter(make_problem()))
        assert report.feasible is True
        assert report.conflicting_constraints == ()
