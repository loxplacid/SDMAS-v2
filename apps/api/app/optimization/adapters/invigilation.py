"""Invigilation scheduling adapter — the working example.

Proves the abstraction end-to-end: exams × rooms × slots × teachers with

- hard: exactly one invigilator per exam, room capacity, no two exams in
  one room at one slot, no teacher invigilating two exams at once, and
  per-teacher unavailability (``forbid_true``);
- soft: balanced teacher workload (``soft_excess``) and subject-preference
  matching (``soft_term``).

The same adapter builds the model for normal solves and (via
``ModelBuilder(gate_hard=True)``) for conflict explanation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.optimization.adapters.base import ProblemAdapter
from app.optimization.core.model import Domain, ModelBuilder
from app.optimization.core.objective import Objective


@dataclass(frozen=True)
class Exam:
    name: str
    students: int
    subject: str = ""


@dataclass(frozen=True)
class Room:
    name: str
    capacity: int


@dataclass(frozen=True)
class Teacher:
    name: str
    subject: str = ""


@dataclass(frozen=True)
class InvigilationProblem:
    """Frozen, JSON-serialisable problem definition."""

    exams: tuple[Exam, ...]
    rooms: tuple[Room, ...]
    slots: tuple[int, ...]
    teachers: tuple[Teacher, ...]
    unavailable: frozenset[tuple[int, int]] = frozenset()
    max_exams_per_teacher: int = 3
    balance_weight: float = 2.0
    subject_weight: float = 1.0


class InvigilationAdapter(ProblemAdapter):
    """Builds and interprets :class:`InvigilationProblem` instances."""

    problem_id = "invigilation"

    def __init__(self, problem: InvigilationProblem) -> None:
        self.problem = problem

    # ------------------------------------------------------------------
    # Validation (pipeline step 1: fail fast on impossible problems)
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Structural invariants only.

        Problems that are *modelable but infeasible* (no room fits an exam,
        the only teacher is unavailable) are deliberately left to the
        conflict explainer, which reports the exact conflicting constraint
        names — see the invigilation explanation tests.
        """
        problem = self.problem
        if not problem.exams:
            raise ValueError("Invigilation problem has no exams")
        if not problem.rooms:
            raise ValueError("Invigilation problem has no rooms")
        if not problem.slots:
            raise ValueError("Invigilation problem has no slots")
        if not problem.teachers:
            raise ValueError("Invigilation problem has no teachers")

    # ------------------------------------------------------------------
    # Model construction
    # ------------------------------------------------------------------

    def build(self, builder: ModelBuilder) -> Objective:
        self.validate()
        problem = self.problem
        n_exams, n_rooms, n_slots, n_teachers = (
            len(problem.exams),
            len(problem.rooms),
            len(problem.slots),
            len(problem.teachers),
        )
        slot_domain = Domain(0, max(n_slots - 1, 0))
        room_domain = Domain(0, max(n_rooms - 1, 0))

        slots: dict[int, object] = {}
        rooms: dict[int, object] = {}
        x: dict[tuple[int, int], object] = {}
        for e in range(n_exams):
            slots[e] = builder.int_var(f"slot_{e}", slot_domain)
            rooms[e] = builder.int_var(f"room_{e}", room_domain)
            for t in range(n_teachers):
                x[e, t] = builder.bool_var(f"x_{e}_{t}")

        for e in range(n_exams):
            builder.exactly_one(
                [x[e, t] for t in range(n_teachers)],
                f"teacher_exactly_one_{e}",
                f"Exam {problem.exams[e].name} needs exactly one invigilator",
            )
            allowed = [
                r for r in range(n_rooms) if problem.rooms[r].capacity >= problem.exams[e].students
            ]
            builder.allowed_assignments(
                rooms[e],
                allowed,
                f"room_capacity_{e}",
                f"Exam {problem.exams[e].name} fits its room capacity",
            )

        builder.all_different(
            [slots[e] * n_rooms + rooms[e] for e in range(n_exams)],
            "room_slot_conflicts",
            "No two exams occupy the same room in the same slot",
        )

        for t in range(n_teachers):
            for e1 in range(n_exams):
                for e2 in range(e1 + 1, n_exams):
                    builder.only_if(
                        slots[e1] != slots[e2],
                        [x[e1, t], x[e2, t]],
                        f"teacher_no_overlap_{t}_{e1}_{e2}",
                        f"Teacher {problem.teachers[t].name} cannot invigilate "
                        "two exams in one slot",
                    )

        for e, t in sorted(problem.unavailable):
            builder.forbid_true(
                x[e, t],
                f"unavailable_{e}_{t}",
                f"Teacher {problem.teachers[t].name} unavailable for exam {problem.exams[e].name}",
            )

        for t in range(n_teachers):
            builder.soft_excess(
                f"load_{t}",
                sum(x[e, t] for e in range(n_exams)),
                problem.max_exams_per_teacher,
                problem.balance_weight,
                f"Teacher {problem.teachers[t].name} keeps a balanced invigilation load",
                max_excess=n_exams,
            )

        for e in range(n_exams):
            preferred = next(
                (
                    t
                    for t in range(n_teachers)
                    if problem.teachers[t].subject
                    and problem.teachers[t].subject == problem.exams[e].subject
                ),
                None,
            )
            if preferred is not None:
                builder.soft_term(
                    f"subject_{e}",
                    1 - x[e, preferred],
                    problem.subject_weight,
                    f"Exam {problem.exams[e].name} is invigilated by a subject-matched teacher",
                )

        return Objective.from_builder(builder)

    # ------------------------------------------------------------------
    # Solution interpretation
    # ------------------------------------------------------------------

    def interpret(self, solution: dict[str, int], builder: ModelBuilder) -> dict:
        problem = self.problem
        assignments = []
        for e in range(len(problem.exams)):
            teacher = next(t for t in range(len(problem.teachers)) if solution[f"x_{e}_{t}"] == 1)
            assignments.append(
                {
                    "exam": problem.exams[e].name,
                    "slot": problem.slots[solution[f"slot_{e}"]],
                    "room": problem.rooms[solution[f"room_{e}"]].name,
                    "teacher": problem.teachers[teacher].name,
                }
            )
        return {"assignments": assignments}

    # ------------------------------------------------------------------
    # Greedy warm start (largest exam first, first free slot/room/teacher)
    # ------------------------------------------------------------------

    def hints(self, builder: ModelBuilder) -> dict[str, int]:
        problem = self.problem
        n_exams, n_rooms, n_slots, n_teachers = (
            len(problem.exams),
            len(problem.rooms),
            len(problem.slots),
            len(problem.teachers),
        )
        order = sorted(range(n_exams), key=lambda e: problem.exams[e].students, reverse=True)
        used_room_slot: set[tuple[int, int]] = set()
        teacher_slots: list[set[int]] = [set() for _ in range(n_teachers)]
        hints: dict[str, int] = {}
        for e in order:
            placed = False
            for s in range(n_slots):
                for r in range(n_rooms):
                    if problem.rooms[r].capacity < problem.exams[e].students:
                        continue
                    if (s, r) in used_room_slot:
                        continue
                    for t in range(n_teachers):
                        if (e, t) in problem.unavailable or s in teacher_slots[t]:
                            continue
                        hints[f"slot_{e}"] = s
                        hints[f"room_{e}"] = r
                        for t2 in range(n_teachers):
                            hints[f"x_{e}_{t2}"] = 1 if t2 == t else 0
                        used_room_slot.add((s, r))
                        teacher_slots[t].add(s)
                        placed = True
                        break
                    if placed:
                        break
                if placed:
                    break
        return hints

    # ------------------------------------------------------------------
    # Domain-language conflict explanations
    # ------------------------------------------------------------------

    def suggest_relaxations(self, conflicting: tuple[str, ...]) -> tuple[str, ...]:
        problem = self.problem
        suggestions: list[str] = []
        for name in conflicting:
            if name.startswith("unavailable_"):
                _, e_str, t_str = name.split("_")
                suggestions.append(
                    f"Allow teacher {problem.teachers[int(t_str)].name} to "
                    f"invigilate exam {problem.exams[int(e_str)].name}, or add "
                    "another invigilator"
                )
            elif name.startswith("teacher_no_overlap_"):
                suggestions.append("Add a slot, or another invigilator for the conflicting teacher")
            elif name == "room_slot_conflicts":
                suggestions.append(
                    "Add a room, or schedule the overlapping exams in different slots"
                )
            elif name.startswith("room_capacity_"):
                suggestions.append("Move an exam to a larger room, or split the cohort")
            elif name.startswith("teacher_exactly_one_"):
                suggestions.append("Make an additional teacher available for this exam")
        return tuple(suggestions)
