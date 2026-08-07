"""Constraint abstraction.

A :class:`Constraint` is a named, documented, hard-or-soft rule. Hard
constraints must hold; soft constraints carry a weight and contribute a
penalty term to the objective. In *explanation mode* (``gate_hard=True``)
every hard constraint is additionally gated behind its own assumption
literal, so an infeasible model can be dissected into a conflicting subset
(see :mod:`app.optimization.core.explain`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Constraint:
    """One named rule in the model."""

    name: str
    description: str
    hard: bool = True
    weight: float = 0.0
    term: object | None = None
    gate: object | None = None

    @property
    def is_soft(self) -> bool:
        return not self.hard
