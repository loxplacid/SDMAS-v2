from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.models import MigrationRun
from app.domains.migration.repository import (
    MigrationLogRepository,
    MigrationMappingRepository,
    MigrationRunRepository,
)
from app.domains.migration.validators import ValidationEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global migrator registry
# ---------------------------------------------------------------------------

_registry: dict[str, BaseMigrator] = {}


def register_migrator(migrator: BaseMigrator) -> BaseMigrator:
    """Register a migrator in the global registry by entity type.

    Migrators are decorated as classes (``@register_migrator``), but the
    engine calls instance methods (``validate`` / ``migrate``).  A class is
    therefore instantiated at registration time so the registry always
    holds ready-to-use instances — callers must never receive a bare class.
    The decorator still returns the class itself so module-level symbols
    stay stable.
    """
    if isinstance(migrator, type):
        instance: BaseMigrator = migrator()
    else:
        instance = migrator
    if instance.entity_type in _registry:
        logger.warning(
            "Overwriting migrator for '%s' (was %s)",
            instance.entity_type, type(_registry[instance.entity_type]).__name__,
        )
    _registry[instance.entity_type] = instance
    return migrator


def get_migrator(entity_type: str) -> BaseMigrator | None:
    return _registry.get(entity_type)


def get_registered_entity_types() -> list[str]:
    return list(_registry.keys())


# ---------------------------------------------------------------------------
# MigrationEngine — orchestrates runs across entity types
# ---------------------------------------------------------------------------


class MigrationEngine:
    """Orchestrates the full migration lifecycle for one or more entities.

    Run order follows the topological order of dependencies.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = MigrationRunRepository(session)
        self.log_repo = MigrationLogRepository(session)
        self.mapping_repo = MigrationMappingRepository(session)
        self.validator = ValidationEngine()

    async def run(
        self,
        entity_type: str,
        records: list[dict[str, Any]],
        *,
        is_dry_run: bool = False,
        source: str = "unknown",
        campus_id: int | None = None,
    ) -> MigratorResult:
        migrator = get_migrator(entity_type)
        if migrator is None:
            raise ValueError(f"No migrator registered for '{entity_type}'")

        now = datetime.datetime.now(datetime.timezone.utc)
        run = MigrationRun(
            entity_type=entity_type,
            status="validating",
            source=source,
            total_records=len(records),
            is_dry_run=is_dry_run,
            campus_id=campus_id,
            started_at=now,
            created_at=now,
        )
        run = await self.run_repo.create(run)
        run_id = run.id

        start = time.monotonic()
        result = MigratorResult(entity_type=entity_type, total=len(records))

        try:
            validated = await migrator.validate(
                records, self.session, run_id, self.log_repo,
            )
            await self.run_repo.update_status(run_id, "running")
            result.skipped = len(records) - len(validated)
            result.warnings = sum(
                1 for r in records if r not in validated
            )

            if is_dry_run:
                await self.run_repo.update_status(
                    run_id, "completed",
                    total_records=len(records),
                    imported=0,
                    skipped=result.skipped,
                    errors=0,
                    warnings=result.warnings,
                    completed_at=datetime.datetime.now(datetime.timezone.utc),
                )
                result.duration_seconds = time.monotonic() - start
                return result

            if validated:
                migrate_result = await migrator.migrate(
                    validated, self.session, run_id,
                    self.mapping_repo, self.log_repo,
                )
                result.imported = migrate_result.imported
                result.errors = migrate_result.errors
                result.warnings += migrate_result.warnings
                result.summary = migrate_result.summary
                result.error_details = migrate_result.error_details

            elapsed = time.monotonic() - start
            result.duration_seconds = elapsed

            overall = "completed" if result.errors == 0 else "completed_with_errors"
            await self.run_repo.update_status(
                run_id, overall,
                total_records=len(records),
                imported=result.imported,
                skipped=result.skipped,
                errors=result.errors,
                warnings=result.warnings,
                summary={
                    "duration_seconds": elapsed,
                    "imported": result.imported,
                    "skipped": result.skipped,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "error_details": result.error_details[:100],
                },
                completed_at=datetime.datetime.now(datetime.timezone.utc),
            )

            logger.info(
                "Migration '%s' %s: %d imported, %d skipped, %d errors "
                "in %.1fs",
                entity_type, overall, result.imported, result.skipped,
                result.errors, elapsed,
            )
            await self._audit(
                entity_type=entity_type,
                run_id=run_id,
                result=result,
                dry_run=is_dry_run,
            )
            return result

        except Exception as exc:
            elapsed = time.monotonic() - start
            result.duration_seconds = elapsed
            result.errors += 1
            result.error_details.append({
                "entity_type": entity_type,
                "error": str(exc),
                "phase": "migration",
            })
            await self.run_repo.update_status(
                run_id, "failed",
                errors=result.errors,
                summary={"error": str(exc), "duration_seconds": elapsed},
                completed_at=datetime.datetime.now(datetime.timezone.utc),
            )
            logger.error("Migration '%s' failed: %s", entity_type, exc)
            await self._audit(
                entity_type=entity_type,
                run_id=run_id,
                result=result,
                dry_run=is_dry_run,
                failed=True,
                failure_reason=str(exc),
            )
            return result

    async def _audit(
        self,
        *,
        entity_type: str,
        run_id: int,
        result: MigratorResult,
        dry_run: bool,
        failed: bool = False,
        failure_reason: str | None = None,
    ) -> None:
        """Record a migration run with the SYSTEM actor (best-effort)."""
        try:
            from app.domains.audit.actors import AuditActor
            from app.domains.audit.service import AuditService

            audit_svc = AuditService(self.session)
            await audit_svc.record(
                action="MIGRATION_RUN",
                resource_type="migration",
                resource_id=str(run_id),
                actor=AuditActor.system(reason="migration"),
                details={
                    "entity_type": entity_type,
                    "run_id": run_id,
                    "dry_run": dry_run,
                    "imported": result.imported,
                    "skipped": result.skipped,
                    "errors": result.errors,
                    "warnings": result.warnings,
                },
                result="FAILURE" if failed else "SUCCESS",
                failure_reason=failure_reason,
            )
        except Exception:
            logger.warning(
                "Failed to write audit entry for migration run %d (non-fatal)",
                run_id, exc_info=True,
            )

    async def run_bulk(
        self,
        entity_types: list[str],
        source_data: dict[str, list[dict[str, Any]]],
        *,
        is_dry_run: bool = False,
        source: str = "unknown",
        campus_id: int | None = None,
    ) -> list[MigratorResult]:
        """Run migrations for multiple entity types in dependency order.

        ``source_data`` maps each entity type to its list of records.
        ``campus_id`` pins every created run to the calling tenant.
        """
        results: list[MigratorResult] = []
        for entity_type in entity_types:
            records = source_data.get(entity_type, [])
            if not records:
                logger.info("No records for '%s' — skipping", entity_type)
                result = MigratorResult(
                    entity_type=entity_type,
                    total=0,
                    summary={"skipped": "no records provided"},
                )
                results.append(result)
                continue
            result = await self.run(
                entity_type, records,
                is_dry_run=is_dry_run,
                source=source,
                campus_id=campus_id,
            )
            results.append(result)
        return results

    async def rollback(self, run_id: int, campus_id: int | None = None) -> int:
        """Roll back a completed migration run."""
        run = await self.run_repo.get_by_id(run_id, campus_id=campus_id)
        if run is None:
            raise ValueError(f"Migration run {run_id} not found")

        migrator = get_migrator(run.entity_type)
        if migrator is None:
            raise ValueError(f"No migrator for '{run.entity_type}'")

        now = datetime.datetime.now(datetime.timezone.utc)
        count = await migrator.rollback(
            run_id, self.session, self.mapping_repo,
        )
        await self.run_repo.update_status(run_id, "rolled_back")
        await self.mapping_repo.delete_by_run(run_id)
        logger.info("Rolled back run %d (%s): %d records", run_id, run.entity_type, count)
        return count
