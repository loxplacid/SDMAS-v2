from __future__ import annotations

import abc
import datetime
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job

logger = logging.getLogger(__name__)


class BaseJob(abc.ABC):
    """Abstract base class for all job types.

    Subclasses must set ``job_type`` and implement ``run``.
    Registration is automatic via ``JobRegistry.register``.
    """

    job_type: str

    async def before_run(self, job: Job, session: AsyncSession) -> None:
        """Hook called before ``run``. Override for setup logic."""

    async def after_run(
        self, job: Job, session: AsyncSession, result: Any
    ) -> None:
        """Hook called after successful ``run``. Override for cleanup."""

    async def on_failure(
        self, job: Job, session: AsyncSession, error: Exception
    ) -> None:
        """Hook called when ``run`` raises. Override for custom error handling."""

    @abc.abstractmethod
    async def run(
        self, job: Job, session: AsyncSession
    ) -> Any:
        """Execute the job. Return a JSON-serializable result."""


# ---------------------------------------------------------------------------
# Registry: maps job_type string -> BaseJob subclass
# ---------------------------------------------------------------------------

_registry: dict[str, type[BaseJob]] = {}


def register_job(job_cls: type[BaseJob]) -> type[BaseJob]:
    """Decorator that registers a job class in the global registry."""
    if not hasattr(job_cls, "job_type") or not job_cls.job_type:
        raise ValueError(
            f"{job_cls.__name__} must define a non-empty 'job_type' class attribute"
        )
    if job_cls.job_type in _registry:
        logger.warning(
            "Overwriting existing job type '%s' (was %s, now %s)",
            job_cls.job_type,
            _registry[job_cls.job_type].__name__,
            job_cls.__name__,
        )
    _registry[job_cls.job_type] = job_cls
    logger.debug("Registered job type '%s' -> %s", job_cls.job_type, job_cls.__name__)
    return job_cls


def get_job_class(job_type: str) -> type[BaseJob] | None:
    return _registry.get(job_type)


def get_registered_types() -> list[str]:
    return list(_registry.keys())


def clear_registry() -> None:
    _registry.clear()
