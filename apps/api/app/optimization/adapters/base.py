"""Problem adapter protocol.

A problem adapter is the only domain-specific code the engine needs. It
declares variables and constraints on a :class:`ModelBuilder`, returns the
objective, converts a solution back into domain objects, and — optionally —
provides a greedy warm start and domain-language conflict explanations.

Adding a new scheduling domain is purely additive: write an adapter,
register it, ship benchmark instances. The engine, explainer, persistence,
tenancy and audit layers are untouched (see docs/OPTIMIZATION_ENGINE.md §14).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProblemAdapter(ABC):
    """One schedulable problem type (invigilation, timetable, bus routing…)."""

    problem_id: str = "problem"

    @abstractmethod
    def build(self, builder) -> "object | None":
        """Declare variables and constraints; return the objective.

        Must be a pure function of ``builder`` and the adapter's own frozen
        problem data — no DB reads, no randomness.
        """

    @abstractmethod
    def interpret(self, solution: dict[str, int], builder) -> dict:
        """Turn the raw name→value solution into domain-shaped output."""

    def validate(self) -> None:
        """Check problem invariants; raise ``ValueError`` with a clear reason.

        Pipeline step 1 (see OPTIMIZATION_ENGINE.md §7): called at the start
        of :meth:`build` and by the worker runner before solving, so an
        impossible problem fails fast instead of silently producing an
        infeasible or invalid model.
        """

    def hints(self, builder) -> dict[str, int]:
        """Optional warm start: a cheap greedy name→value start.

        The greedy solution never constrains correctness; it only seeds
        CP-SAT's search (see OPTIMIZATION_ENGINE.md §8).
        """
        return {}

    def suggest_relaxations(self, conflicting: tuple[str, ...]) -> tuple[str, ...]:
        """Map conflicting constraint names to human suggestions."""
        return ()
