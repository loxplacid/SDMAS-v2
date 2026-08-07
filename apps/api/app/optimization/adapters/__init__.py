"""Problem adapters: domain-specific code declaring problems on the core."""

from app.optimization.adapters.base import ProblemAdapter
from app.optimization.adapters.invigilation import (
    Exam,
    InvigilationAdapter,
    InvigilationProblem,
    Room,
    Teacher,
)

__all__ = [
    "Exam",
    "InvigilationAdapter",
    "InvigilationProblem",
    "ProblemAdapter",
    "Room",
    "Teacher",
]
