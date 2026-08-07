"""SDMAS optimization engine.

A generic constraint solver built on Google OR-Tools CP-SAT. Problem
adapters (invigilation, timetables, exam scheduling, bus routing, …)
declare variables, constraints and objectives against the core; the engine
solves, warm-starts, and explains conflicts. See
``docs/OPTIMIZATION_ENGINE.md``.
"""

from app.optimization.core.constraints import Constraint
from app.optimization.core.engine import (
    LexSolveResult,
    SolveParams,
    SolverEngine,
    SolveResult,
    SolveStatus,
)
from app.optimization.core.explain import ConflictExplainer, ConflictReport
from app.optimization.core.model import Domain, ModelBuilder
from app.optimization.core.objective import Objective

__all__ = [
    "Constraint",
    "ConflictExplainer",
    "ConflictReport",
    "Domain",
    "LexSolveResult",
    "ModelBuilder",
    "Objective",
    "SolveParams",
    "SolveResult",
    "SolveStatus",
    "SolverEngine",
]
