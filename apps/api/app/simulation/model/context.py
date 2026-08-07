"""Resolved input the forecast models actually read.

A :class:`SimulationContext` is the frozen result of applying a scenario's
levers to its baseline snapshot plus the scenario's coefficient overrides.
Models read only this object — they never touch live school data.

``baseline`` keeps the *original* snapshot alongside the adjusted one so
change-sensitive models (dropout fee pressure, performance hours effect)
can compute deterministic deltas.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.simulation.coefficient.registry import Coefficients
from app.simulation.snapshot.snapshot import SimulationSnapshot


@dataclass(frozen=True)
class SimulationContext:
    """Immutable model input: adjusted snapshot + resolved coefficients."""

    snapshot: SimulationSnapshot
    coefficients: Coefficients
    baseline: SimulationSnapshot | None = None
