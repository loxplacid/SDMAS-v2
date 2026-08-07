"""Scenario — a validated bundle of levers applied to a baseline snapshot.

A :class:`Scenario` is JSON-serialisable input; the engine never mutates it.
Building the :class:`SimulationContext` is a pure fold over the levers, which
keeps results byte-identical across runs and machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from app.simulation.coefficient.registry import Coefficients
from app.simulation.model.context import SimulationContext
from app.simulation.model.lever import LeverSet
from app.simulation.snapshot.snapshot import SimulationSnapshot

Horizon: Final = str  # "term" | "semester" | "academic_year"


@dataclass(frozen=True)
class Scenario:
    """``id``/``campus_id``/``base_snapshot`` + the list of levers."""

    id: str
    campus_id: int
    base_snapshot: SimulationSnapshot
    levers: LeverSet = ()
    assumptions: dict[str, Any] = field(default_factory=dict)
    horizon: Horizon = "term"

    def validate(self) -> None:
        """Validate every lever against the baseline snapshot.

        Raises:
            ValueError: if a lever cannot apply (e.g. non-positive factor).
        """
        for lever in self.levers:
            lever.validate(self.base_snapshot)

    def context(self, defaults: Coefficients) -> SimulationContext:
        """Fold the levers over the snapshot and resolve coefficients.

        Deterministic and side-effect free: called many times it returns equal
        (independent) context values.
        """
        self.validate()
        snapshot = self.base_snapshot
        for lever in self.levers:
            snapshot = lever.apply(snapshot)
        coefficients = defaults.merged(self.assumptions)
        return SimulationContext(
            snapshot=snapshot,
            coefficients=coefficients,
            baseline=self.base_snapshot,
        )
