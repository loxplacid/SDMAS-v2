from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class MigratorResult:
    """Result produced by a single migrator run."""

    entity_type: str
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    warnings: int = 0
    duration_seconds: float = 0.0
    error_details: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class BaseMigrator(abc.ABC):
    """Abstract base class for all entity migrators.

    Each subclass handles migration for one entity type (or a group of
    tightly coupled entities in dependency order).  The framework
    guarantees that migrators run in registration order so that FK
    mappings from earlier migrators are available to later ones.
    """

    entity_type: str
    """Unique name for this migration stream (e.g. ``students``)."""

    table_name: str | None = None
    """Exact target table this migrator writes (e.g. ``attendance_records``).

    Used by the base ``rollback`` to delete exactly the rows this run
    created.  Must be set whenever the base rollback is used: the legacy
    ``_get_table`` scan matches *substrings* and returns the first mapper,
    which is import-order dependent — with the full app loaded,
    ``attendance`` resolves to ``attendance_thresholds`` and rollback
    silently deletes from the wrong table.
    """

    dependencies: list[str] = []
    """Entity types that must be migrated before this one."""

    @abc.abstractmethod
    async def validate(
        self,
        records: list[dict[str, Any]],
        session: AsyncSession,
        run_id: int,
        log_repo: Any,
    ) -> list[dict[str, Any]]:
        """Validate incoming records before migration.

        Returns the subset of records that passed validation.
        Every rejected record must be logged via ``log_repo.log``
        with level ``"error"`` or ``"skipped"``.
        """

    @abc.abstractmethod
    async def migrate(
        self,
        records: list[dict[str, Any]],
        session: AsyncSession,
        run_id: int,
        mapping_repo: Any,
        log_repo: Any,
    ) -> MigratorResult:
        """Perform the actual migration.

        * Insert or update records in the target database.
        * Record all legacy→SDMAS ID mappings via ``mapping_repo``.
        * Log every record (success, skip, or error) via ``log_repo``.
        * Return a ``MigratorResult`` with accurate counts.
        """

    async def rollback(
        self,
        run_id: int,
        session: AsyncSession,
        mapping_repo: Any,
    ) -> int:
        """Reverse the migration for this entity type.

        Deletes all SDMAS records that were created during this run,
        based on the stored ID mappings.  Returns the number of records
        removed.

        Override this method if a simple ID-based deletion is not
        appropriate (e.g. for cascading deletes or soft-delete).
        """
        mappings = await mapping_repo.list_by_entity(self.entity_type, run_id=run_id)
        if not mappings:
            return 0

        sdmas_ids = [m.sdmas_id for m in mappings]
        table = self._get_table()
        if table is None:
            logger.warning("No table found for entity '%s' — skipping rollback", self.entity_type)
            return 0

        from sqlalchemy import delete as sa_delete

        result = await session.execute(sa_delete(table).where(table.c.id.in_(sdmas_ids)))
        await session.flush()
        count = result.rowcount
        logger.info("Rolled back %d records for '%s'", count, self.entity_type)
        return count

    def _get_table(self) -> Any:
        """Return the SQLAlchemy table for this entity type.

        Prefers an exact match on ``table_name`` (deterministic regardless
        of import order).  Falls back to the legacy substring scan only
        for migrators that never declared a table — but every migrator
        that relies on the base rollback must set ``table_name``.
        """
        from app.infrastructure.database import Base

        if self.table_name:
            for mapper in Base.registry.mappers:
                cls = mapper.class_
                if getattr(cls, "__tablename__", None) == self.table_name:
                    return cls.__table__
            return None

        # Legacy fallback: first mapper whose tablename contains the
        # entity type.  Import-order dependent — avoid for new migrators.
        for mapper in Base.registry.mappers:
            cls = mapper.class_
            if hasattr(cls, "__tablename__"):
                tab = cls.__tablename__
                if tab and self.entity_type in tab:
                    return cls.__table__
        return None
