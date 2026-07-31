from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.migration.engine import (
    MigrationEngine,
    get_registered_entity_types,
)
from app.domains.migration.readers import LegacyJSONReader
from app.domains.migration.reporting import build_summary, format_error_report, format_report_text
from app.domains.migration.repository import (
    MigrationLogRepository,
    MigrationRunRepository,
)
from app.domains.migration.rollback import RollbackService
from app.domains.migration.schemas import (
    BulkMigrationRequest,
    BulkMigrationResponse,
    MigrationLogResponse,
    MigrationRunCreate,
    MigrationRunResponse,
    MigrationSummary,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/migration", tags=["migration"])


# ── Helpers ────────────────────────────────────────────────────────────


async def _get_engine(session: AsyncSession = Depends(get_session)) -> MigrationEngine:
    return MigrationEngine(session)


async def _get_run_repo(session: AsyncSession = Depends(get_session)) -> MigrationRunRepository:
    return MigrationRunRepository(session)


async def _get_log_repo(session: AsyncSession = Depends(get_session)) -> MigrationLogRepository:
    return MigrationLogRepository(session)


# ── Info ───────────────────────────────────────────────────────────────


@router.get("/entities")
async def list_entities(
    _: User = Depends(require_role("admin")),
) -> dict[str, list[str]]:
    return {"entities": get_registered_entity_types()}


# ── Import from legacy data source ─────────────────────────────────────


@router.post("/import", response_model=list[MigrationRunResponse])
async def import_from_source(
    data: BulkMigrationRequest,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> list[MigrationRunResponse]:
    reader = LegacyJSONReader(data.source)

    source_issues = await reader.validate_source()
    if source_issues:
        raise ValueError(f"Source validation failed: {'; '.join(source_issues)}")

    all_data = await reader.read_all()

    engine = MigrationEngine(session)
    results = await engine.run_bulk(
        data.entities,
        all_data,
        is_dry_run=data.is_dry_run,
        source=data.source,
    )

    run_repo = MigrationRunRepository(session)
    runs, _ = await run_repo.list_runs(limit=len(results))
    return [MigrationRunResponse.model_validate(r) for r in runs[:len(results)]]


@router.post("/run", response_model=MigrationRunResponse)
async def run_migration(
    data: MigrationRunCreate,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> MigrationRunResponse:
    reader = LegacyJSONReader(data.source)
    records = await reader.read_entity(data.entity_type)

    engine = MigrationEngine(session)
    result = await engine.run(
        data.entity_type,
        records,
        is_dry_run=data.is_dry_run,
        source=data.source,
    )

    run_repo = MigrationRunRepository(session)
    run = await run_repo.get_by_id(1)
    return MigrationRunResponse.model_validate(run)


# ── Migration runs ─────────────────────────────────────────────────────


@router.get("/runs", response_model=list[MigrationRunResponse])
async def list_runs(
    entity_type: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require_role("admin")),
    run_repo: MigrationRunRepository = Depends(_get_run_repo),
) -> list[MigrationRunResponse]:
    items, _ = await run_repo.list_runs(
        entity_type=entity_type, status=status, skip=skip, limit=limit,
    )
    return [MigrationRunResponse.model_validate(r) for r in items]


@router.get("/runs/{run_id}", response_model=MigrationRunResponse)
async def get_run(
    run_id: int,
    _: User = Depends(require_role("admin")),
    run_repo: MigrationRunRepository = Depends(_get_run_repo),
) -> MigrationRunResponse:
    run = await run_repo.get_by_id(run_id)
    if run is None:
        raise NotFoundError(f"Migration run {run_id} not found")
    return MigrationRunResponse.model_validate(run)


# ── Logs ───────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/logs", response_model=list[MigrationLogResponse])
async def get_run_logs(
    run_id: int,
    level: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    _: User = Depends(require_role("admin")),
    log_repo: MigrationLogRepository = Depends(_get_log_repo),
) -> list[MigrationLogResponse]:
    items, _ = await log_repo.list_by_run(
        run_id, level=level, skip=skip, limit=limit,
    )
    return [MigrationLogResponse.model_validate(r) for r in items]


@router.get("/runs/{run_id}/report", response_model=MigrationSummary)
async def get_run_report(
    run_id: int,
    _: User = Depends(require_role("admin")),
    run_repo: MigrationRunRepository = Depends(_get_run_repo),
) -> MigrationSummary:
    run = await run_repo.get_by_id(run_id)
    if run is None:
        raise NotFoundError(f"Migration run {run_id} not found")
    return MigrationSummary(
        entity_type=run.entity_type,
        total=run.total_records,
        imported=run.imported,
        skipped=run.skipped,
        errors=run.errors,
        warnings=run.warnings,
        is_dry_run=run.is_dry_run,
        status=run.status,
    )


@router.get("/runs/{run_id}/report/text")
async def get_run_report_text(
    run_id: int,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> str:
    run_repo = MigrationRunRepository(session)
    log_repo = MigrationLogRepository(session)

    run = await run_repo.get_by_id(run_id)
    if run is None:
        raise NotFoundError(f"Migration run {run_id} not found")

    errors_log, _ = await log_repo.list_by_run(run_id, level="error", limit=1000)
    error_details = []
    for entry in errors_log:
        error_details.append({
            "legacy_id": entry.legacy_id,
            "subtype": entry.entity_subtype,
            "error": entry.message,
        })

    summary = MigrationSummary(
        entity_type=run.entity_type,
        total=run.total_records,
        imported=run.imported,
        skipped=run.skipped,
        errors=run.errors,
        warnings=run.warnings,
        is_dry_run=run.is_dry_run,
        status=run.status,
        error_details=error_details,
    )
    return format_report_text([summary])


# ── Rollback ───────────────────────────────────────────────────────────


@router.post("/runs/{run_id}/rollback/plan")
async def plan_rollback(
    run_id: int,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = RollbackService(session)
    plan = await svc.plan_rollback(run_id)
    return {
        "run_id": plan.run_id,
        "entity_type": plan.entity_type,
        "records_to_remove": plan.records_to_remove,
        "tables_affected": plan.tables_affected,
        "warnings": plan.warnings,
    }


@router.post("/runs/{run_id}/rollback")
async def execute_rollback(
    run_id: int,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    svc = RollbackService(session)
    count = await svc.execute_rollback(run_id)
    return {"run_id": run_id, "records_removed": count}
