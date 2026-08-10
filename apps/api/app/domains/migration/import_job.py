from __future__ import annotations

import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job
from app.domains.jobs.registry import BaseJob, register_job
from app.domains.migration.discovery import detect_entities, parse_source
from app.domains.migration.models import (
    MIGRATION_STATUS_FAILED,
    MIGRATION_STATUS_RECONCILING,
    MigrationRun,
)
from app.domains.migration.project_repository import MigrationProjectRepository
from app.domains.migration.project_service import IMPORT_CHUNK_SIZE
from app.domains.migration.repository import (
    MigrationLogRepository,
    MigrationMappingRepository,
    MigrationRunRepository,
)
from app.domains.migration.transforms import apply_mapping
from app.domains.migration.workspace_import import (
    ENTITY_ORDER,
    build_attendance_records,
    run_academic,
    run_fees,
    student_rows,
)
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)

MIGRATION_IMPORT_JOB_TYPE = "migration.import"


@register_job
class MigrationImportJob(BaseJob):
    """Executes a migration project's import in the background (D2.8).

    Guarantees
    ----------
    * **Chunked** — flat streams (students, attendance) are processed in
      ``IMPORT_CHUNK_SIZE`` batches; container streams (academic, fees) run
      level-by-level.
    * **Resumable** — every chunk commits its own transaction and advances
      ``project.records_processed``; a retry skips already-committed records
      (idempotent) and continues.
    * **Idempotent** — committed legacy ids are skipped; structure entities
      that already exist (same name + campus) are excluded up front; the
      migrators themselves dedupe by natural keys.
    * **Progress survives refresh** — counts live on the project row, never
      in the browser.
    * **Failure isolation** — a bad chunk fails the run (not the whole
      import); remaining chunks still process and errors are recorded.
    """

    job_type = MIGRATION_IMPORT_JOB_TYPE

    async def run(self, job: Job, session: AsyncSession) -> dict[str, Any]:
        project_id = (job.params or {}).get("project_id")
        if not project_id:
            raise ValueError(f"{MIGRATION_IMPORT_JOB_TYPE} job missing project_id")

        # The worker runs platform-scoped; the project itself pins us to the
        # correct campus (project.campus_id).  Never trust a job param to
        # select the campus.
        tenant = TenantContext(campus_id=job.campus_id, user_id=job.user_id)
        return await run_project_import(session, tenant, int(project_id), job_id=job.id)


async def run_project_import(
    session: AsyncSession,
    tenant: TenantContext,
    project_id: int,
    *,
    job_id: int | None = None,
) -> dict[str, Any]:
    """Execute (or resume) a migration project import.  Returns a summary.

    Detected entities run in dependency order (students → academic →
    attendance → fees) so later streams can resolve references created by
    earlier ones through the run's mapping table.  Idempotent by
    construction: committed records are skipped, so calling this twice
    never duplicates data.
    """
    repo = MigrationProjectRepository(session, tenant)
    project = await repo.get_by_id(project_id)

    mapping = project.mapping or {}
    entities = detect_entities(mapping)
    if not entities:
        entities = ["students"]
    entities = [e for e in ENTITY_ORDER if e in entities]

    run_repo = MigrationRunRepository(session)
    log_repo = MigrationLogRepository(session)
    mapping_repo = MigrationMappingRepository(session)

    # ── Load + transform source ─────────────────────────────────────────
    from app.domains.migration.project_service import migration_storage

    storage = migration_storage()
    file_data = await storage.download(project.file_key)
    records = parse_source(file_data, project.original_filename or "")
    transformed = apply_mapping(records, mapping)
    # Tenant pinning (D2.15): the import target campus is ALWAYS the
    # project's campus — never a value from the uploaded file.
    for record in transformed:
        record["campus_id"] = project.campus_id
    total = len(transformed)

    totals = {"imported": 0, "updated": 0, "skipped": 0, "errors": 0, "warnings": 0}
    processed = 0
    entity_results: dict[str, dict[str, int]] = {}

    try:
        for entity in entities:
            # Resume boundary: a run that already reached a terminal
            # ``completed*`` state means the whole entity stream committed —
            # re-running it would re-log the same entries (migration_logs
            # allows exactly one entry per record).  Skipping the completed
            # stream keeps re-runs a true no-op.
            existing_run = await _get_or_create_run(session, run_repo, project, entity)
            if existing_run.status.startswith("completed"):
                logger.info(
                    "Migration import project=%s entity=%s already completed — skipping",
                    project_id,
                    entity,
                )
                continue

            result: Any
            if entity == "students":
                result, run = await _import_flat_entity(
                    session,
                    tenant,
                    project,
                    "students",
                    student_rows(transformed),
                    run_repo,
                    log_repo,
                    mapping_repo,
                    job_id=job_id,
                    totals=totals,
                    processed=processed,
                )
            elif entity == "academic":
                from app.domains.migration.engine import get_migrator

                run = existing_run
                result = await run_academic(
                    session,
                    get_migrator("academic"),
                    mapping_repo,
                    log_repo,
                    run.id,
                    transformed,
                    campus_id=project.campus_id,
                )
            elif entity == "attendance":
                attendance_records, skipped_refs = await build_attendance_records(
                    session, mapping_repo, transformed, campus_id=project.campus_id
                )
                result, run = await _import_flat_entity(
                    session,
                    tenant,
                    project,
                    "attendance",
                    attendance_records,
                    run_repo,
                    log_repo,
                    mapping_repo,
                    job_id=job_id,
                    totals=totals,
                    processed=processed,
                )
                # Every unresolvable reference is an explicit, logged error.
                # Log-once: a resumed stream regenerates the same unresolved
                # refs (they are never committed to the mapping table), so
                # re-logging would violate migration_logs' one-entry-per-
                # record constraint (same guard as the fees path).
                for legacy_id, reason in skipped_refs:
                    result.errors += 1
                    if not await log_repo.entry_exists(run.id, legacy_id, "attendance"):
                        await log_repo.log(
                            run_id=run.id,
                            level="error",
                            entity_type="attendance",
                            legacy_id=legacy_id,
                            entity_subtype="attendance",
                            message=f"Reference resolution failed: {reason}",
                        )
            elif entity == "fees":
                from app.domains.migration.engine import get_migrator

                run = existing_run
                result = await run_fees(
                    session,
                    get_migrator("fees"),
                    mapping_repo,
                    log_repo,
                    run.id,
                    transformed,
                    campus_id=project.campus_id,
                )
            else:
                logger.warning("Unknown migration entity '%s' — skipped", entity)
                continue

            # ── Finalise this entity's run + fold into project counts. ──
            totals["imported"] += result.imported
            totals["skipped"] += result.skipped
            totals["errors"] += result.errors
            totals["warnings"] += result.warnings
            processed += result.total
            entity_results[entity] = {
                "total": result.total,
                "imported": result.imported,
                "skipped": result.skipped,
                "errors": result.errors,
                "warnings": result.warnings,
            }

            now = datetime.datetime.now(datetime.timezone.utc)
            overall = "completed" if result.errors == 0 else "completed_with_errors"
            await run_repo.update_status(
                run.id,
                overall,
                total_records=result.total,
                imported=result.imported,
                skipped=result.skipped,
                errors=result.errors,
                warnings=result.warnings,
                completed_at=now,
                summary={
                    "imported": result.imported,
                    "skipped": result.skipped,
                    "errors": result.errors,
                    "project_id": project.id,
                },
            )
            await repo.touch(
                project.id,
                records_processed=processed,
                records_imported=totals["imported"],
                records_updated=totals["updated"],
                records_skipped=totals["skipped"],
                records_rejected=totals["errors"],
                warnings=totals["warnings"],
                last_activity_at=now,
            )
            await _update_job_progress(session, job_id, total, processed)
            # Per-entity commit: the resumability boundary.
            await session.commit()
            logger.info(
                "Migration import project=%s entity=%s: +%d imported, %d errors",
                project_id,
                entity,
                result.imported,
                result.errors,
            )

        # ── Finalise project ────────────────────────────────────────────
        now = datetime.datetime.now(datetime.timezone.utc)
        await repo.touch(
            project.id,
            status=MIGRATION_STATUS_RECONCILING,
            completed_at=now,
            last_activity_at=now,
        )
        await _audit_import(
            session,
            project.id,
            project.run_id,
            totals["imported"],
            totals["skipped"],
            totals["errors"],
            entities=entity_results,
        )
        return {
            "project_id": project.id,
            "run_id": project.run_id,
            "imported": totals["imported"],
            "skipped": totals["skipped"],
            "errors": totals["errors"],
            "entities": entity_results,
        }
    except Exception as exc:
        logger.exception("Migration import failed for project=%s", project_id)
        await repo.touch(project.id, status=MIGRATION_STATUS_FAILED)
        if project.run_id:
            await run_repo.update_status(project.run_id, "failed", summary={"error": str(exc)})
        await _audit_import(
            session,
            project.id,
            project.run_id,
            totals["imported"],
            totals["skipped"],
            totals["errors"],
            failed=True,
            reason=str(exc),
        )
        raise


async def _get_or_create_run(
    session: AsyncSession,
    run_repo: MigrationRunRepository,
    project: Any,
    entity: str,
) -> MigrationRun:
    """Reuse the existing run for (project, entity) or create one."""
    existing = await session.execute(
        select(MigrationRun)
        .where(
            MigrationRun.project_id == project.id,
            MigrationRun.entity_type == entity,
        )
        .order_by(MigrationRun.created_at.desc())
        .limit(1)
    )
    run = existing.scalar_one_or_none()
    if run is not None:
        return run

    now = datetime.datetime.now(datetime.timezone.utc)
    run = MigrationRun(
        entity_type=entity,
        status="validating",
        source=f"migration project #{project.id} ({project.source_system})",
        total_records=0,
        project_id=project.id,
        campus_id=project.campus_id,
        started_at=now,
        created_at=now,
    )
    run = await run_repo.create(run)
    if project.run_id is None:
        await MigrationProjectRepository(session, None).touch(project.id, run_id=run.id)
    return run


async def _import_flat_entity(
    session: AsyncSession,
    tenant: TenantContext,
    project: Any,
    entity: str,
    entity_records: list[dict[str, Any]],
    run_repo: MigrationRunRepository,
    log_repo: MigrationLogRepository,
    mapping_repo: MigrationMappingRepository,
    *,
    job_id: int | None,
    totals: dict[str, int],
    processed: int,
) -> tuple[Any, MigrationRun]:
    """Chunked, resumable, idempotent import for a flat-record stream.

    ``processed`` is the number of rows already consumed by earlier
    entities — used only for job progress math.  ``totals`` is reserved for
    the caller; this function never mutates it (the outer loop folds the
    returned result into project-level counters exactly once).
    """
    from app.domains.migration.engine import get_migrator

    migrator = get_migrator(entity)
    if migrator is None:
        raise ValueError(f"No migrator registered for '{entity}'")

    total = len(entity_records)
    run = await _get_or_create_run(session, run_repo, project, entity)
    committed: set[str] = {
        str(m.legacy_id) for m in await mapping_repo.list_by_entity(entity, run_id=run.id)
    }

    imported = skipped = errors = warnings = 0
    for start in range(0, total, IMPORT_CHUNK_SIZE):
        chunk = entity_records[start : start + IMPORT_CHUNK_SIZE]

        # Filter to records not already committed (resume checkpoint).
        fresh = [
            (i + start, rec)
            for i, rec in enumerate(chunk)
            if not str(rec.get("legacy_id", "")) or str(rec.get("legacy_id", "")) not in committed
        ]
        if not fresh:
            await _progress(session, tenant, project, job_id, processed, start + len(chunk))
            await session.commit()
            continue

        valid_records = await migrator.validate(
            [rec for _, rec in fresh],
            session,
            run.id,
            log_repo,
        )
        validated_ids = {str(r.get("legacy_id", "")) for r in valid_records}
        rejected = sum(1 for _, rec in fresh if str(rec.get("legacy_id", "")) not in validated_ids)

        result = await migrator.migrate(
            valid_records,
            session,
            run.id,
            mapping_repo,
            log_repo,
        )
        imported += result.imported
        skipped += result.skipped
        errors += result.errors + rejected
        warnings += result.warnings

        await _progress(session, tenant, project, job_id, processed, start + len(chunk))
        # Per-chunk commit: the resumability boundary.
        await session.commit()

    return (
        _FlatResult(
            total=total, imported=imported, skipped=skipped, errors=errors, warnings=warnings
        ),
        run,
    )


async def _progress(
    session: AsyncSession,
    tenant: TenantContext,
    project: Any,
    job_id: int | None,
    base: int,
    within: int,
) -> None:
    processed = base + within
    await MigrationProjectRepository(session, tenant).touch(project.id, records_processed=processed)
    await _update_job_progress(session, job_id, project.row_count, processed)


class _FlatResult:
    """Minimal MigratorResult-shaped summary for flat streams."""

    def __init__(
        self, *, total: int, imported: int, skipped: int, errors: int, warnings: int
    ) -> None:
        self.total = total
        self.imported = imported
        self.skipped = skipped
        self.errors = errors
        self.warnings = warnings


async def _update_job_progress(
    session: AsyncSession,
    job_id: int | None,
    total: int,
    processed: int,
) -> None:
    if job_id is None or total <= 0:
        return
    from app.domains.jobs.repository import JobRepository
    from app.multi_tenant.models import platform_context

    repo = JobRepository(session, platform_context())
    await repo.update_progress(job_id, round(min(processed / total * 100.0, 100.0), 1))


async def _audit_import(
    session: AsyncSession,
    project_id: int,
    run_id: int | None,
    imported: int,
    skipped: int,
    errors: int,
    *,
    failed: bool = False,
    reason: str | None = None,
    entities: dict[str, dict[str, int]] | None = None,
) -> None:
    try:
        from app.domains.audit.actors import AuditActor
        from app.domains.audit.service import AuditService

        await AuditService(session).record(
            action="MIGRATION_PROJECT_IMPORT_COMPLETED",
            resource_type="migration_project",
            resource_id=str(project_id),
            actor=AuditActor.worker(),
            details={
                "run_id": run_id,
                "imported": imported,
                "skipped": skipped,
                "errors": errors,
                "entities": entities,
            },
            result="FAILURE" if failed else "SUCCESS",
            failure_reason=reason,
        )
    except Exception:
        logger.warning("Failed to write audit for migration import (non-fatal)", exc_info=True)
