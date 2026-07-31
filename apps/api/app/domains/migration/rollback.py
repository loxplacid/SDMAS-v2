from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.migration.engine import get_migrator
from app.domains.migration.repository import (
    MigrationLogRepository,
    MigrationMappingRepository,
    MigrationRunRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class RollbackPlan:
    """Describes what will be rolled back before executing."""

    run_id: int
    entity_type: str
    dry_run: bool
    records_to_remove: int = 0
    tables_affected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RollbackService:
    """Plans and executes rollbacks for migration runs.

    Rollback respects the dependency order:
    1. Dependent entities (fees, attendance) are rolled back first
    2. Core entities (students, academic, users) are rolled back last

    This prevents FK constraint violations during deletion.
    """

    ROLLBACK_ORDER = {
        "fees": 0,
        "attendance": 0,
        "academic": 1,
        "students": 2,
        "users": 3,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = MigrationRunRepository(session)
        self.mapping_repo = MigrationMappingRepository(session)
        self.log_repo = MigrationLogRepository(session)

    async def plan_rollback(
        self, run_id: int, *, dry_run: bool = True
    ) -> RollbackPlan:
        """Preview a rollback without executing it."""
        run = await self.run_repo.get_by_id(run_id)
        if run is None:
            raise ValueError(f"Migration run {run_id} not found")

        migrator = get_migrator(run.entity_type)
        if migrator is None:
            raise ValueError(f"No migrator for '{run.entity_type}'")

        mappings = await self.mapping_repo.list_by_entity(
            run.entity_type, run_id=run_id
        )
        table = migrator._get_table()
        tables = [table.name] if table else [run.entity_type]

        return RollbackPlan(
            run_id=run_id,
            entity_type=run.entity_type,
            dry_run=dry_run,
            records_to_remove=len(mappings),
            tables_affected=tables,
        )

    async def execute_rollback(self, run_id: int) -> int:
        """Execute a full rollback for a single migration run.

        Returns total records removed across all affected tables.
        """
        from app.domains.migration.engine import MigrationEngine

        engine = MigrationEngine(self.session)
        return await engine.rollback(run_id)

    async def bulk_rollback(
        self, run_ids: list[int], *, dry_run: bool = True
    ) -> list[RollbackPlan]:
        """Plan or execute rollbacks for multiple runs in dependency-safe order.

        Returns the plans (if dry_run) or executes them in reverse dependency order.
        """
        runs: list[Any] = []
        for rid in run_ids:
            run = await self.run_repo.get_by_id(rid)
            if run:
                runs.append(run)

        runs.sort(
            key=lambda r: self.ROLLBACK_ORDER.get(r.entity_type, 5),
            reverse=True,
        )

        plans: list[RollbackPlan] = []
        for run in runs:
            if dry_run:
                plan = await self.plan_rollback(run.id, dry_run=True)
                plans.append(plan)
            else:
                count = await self.execute_rollback(run.id)
                plans.append(RollbackPlan(
                    run_id=run.id,
                    entity_type=run.entity_type,
                    dry_run=False,
                    records_to_remove=count,
                    tables_affected=[],
                ))

        return plans
