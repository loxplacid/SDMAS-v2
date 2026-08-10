from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.auth.dependencies import require_role
from app.domains.auth.models import User
from app.domains.migration.engine import (
    MigrationEngine,
    get_registered_entity_types,
)
from app.domains.migration.project_service import MigrationProjectService
from app.domains.migration.readers import LegacyJSONReader
from app.domains.migration.reporting import format_report_text
from app.domains.migration.repository import (
    MigrationLogRepository,
    MigrationRunRepository,
)
from app.domains.migration.rollback import RollbackService
from app.domains.migration.schemas import (
    BulkMigrationRequest,
    ImportProgress,
    MappingUpdate,
    MigrationLogResponse,
    MigrationProjectPage,
    MigrationProjectResponse,
    MigrationRunCreate,
    MigrationRunResponse,
    MigrationSummary,
    PreviewResult,
    ReconcileResult,
    ValidationResult,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_school_context
from app.multi_tenant.models import TenantContext

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
    return [MigrationRunResponse.model_validate(r) for r in runs[: len(results)]]


@router.post("/run", response_model=MigrationRunResponse)
async def run_migration(
    data: MigrationRunCreate,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> MigrationRunResponse:
    reader = LegacyJSONReader(data.source)
    records = await reader.read_entity(data.entity_type)

    engine = MigrationEngine(session)
    await engine.run(
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
        entity_type=entity_type,
        status=status,
        skip=skip,
        limit=limit,
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
        run_id,
        level=level,
        skip=skip,
        limit=limit,
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
        error_details.append(
            {
                "legacy_id": entry.legacy_id,
                "subtype": entry.entity_subtype,
                "error": entry.message,
            }
        )

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


# ───────────────────────────────────────────────────────────────────────────
# D2 — Migration Project workspace (upload → discover → map → validate →
# preview → import → reconcile → report).  All project endpoints are
# admin-only AND tenant-scoped: the project is resolved through a repo that
# pins to the caller's campus, so one campus can never read or mutate
# another campus's migration workspace.
# ───────────────────────────────────────────────────────────────────────────


def _project_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_school_context),
    user: User = Depends(require_role("admin")),
) -> MigrationProjectService:
    return MigrationProjectService(
        session,
        tenant,
        user_id=user.id,
        username=user.username,
    )


@router.get("/projects", response_model=MigrationProjectPage)
async def list_projects(
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: MigrationProjectService = Depends(_project_service),
) -> MigrationProjectPage:
    items, total = await service.repo.list_projects(status=status, skip=skip, limit=limit)
    pages = (total + limit - 1) // limit if limit else 0
    return MigrationProjectPage(
        items=[MigrationProjectResponse.model_validate(p) for p in items],
        total=total,
        page=(skip // limit) + 1 if limit else 1,
        size=limit,
        pages=pages,
    )


@router.post("/projects", response_model=MigrationProjectResponse, status_code=201)
async def create_project(
    name: str = Form(...),
    source_system: str = Form("Generic CSV"),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    service: MigrationProjectService = Depends(_project_service),
) -> MigrationProjectResponse:
    file_data = await file.read()
    project = await service.create_project(
        name=name,
        source_system=source_system,
        description=description,
        filename=file.filename or "source.csv",
        file_data=file_data,
        mime_type=file.content_type,
    )
    return MigrationProjectResponse.model_validate(project)


@router.get("/projects/{project_id}", response_model=MigrationProjectResponse)
async def get_project(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> MigrationProjectResponse:
    project = await service.repo.get_by_id(project_id)
    return MigrationProjectResponse.model_validate(project)


@router.put("/projects/{project_id}/mapping", response_model=MigrationProjectResponse)
async def save_project_mapping(
    project_id: int,
    data: MappingUpdate,
    service: MigrationProjectService = Depends(_project_service),
) -> MigrationProjectResponse:
    project = await service.save_mapping(project_id, data.mapping)
    return MigrationProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/validate", response_model=ValidationResult)
async def validate_project(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> ValidationResult:
    return ValidationResult(**await service.run_validation(project_id))


@router.get("/projects/{project_id}/preview", response_model=PreviewResult)
async def preview_project(
    project_id: int,
    limit: int = Query(10, ge=1, le=50),
    service: MigrationProjectService = Depends(_project_service),
) -> PreviewResult:
    return PreviewResult(**await service.preview(project_id, limit=limit))


@router.post("/projects/{project_id}/import", response_model=MigrationProjectResponse)
async def start_project_import(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> MigrationProjectResponse:
    project = await service.start_import(project_id)
    return MigrationProjectResponse.model_validate(project)


@router.get("/projects/{project_id}/progress", response_model=ImportProgress)
async def project_progress(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> ImportProgress:
    return ImportProgress(**await service.get_progress(project_id))


@router.get("/projects/{project_id}/reconcile", response_model=ReconcileResult)
async def reconcile_project(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> ReconcileResult:
    return ReconcileResult(**await service.reconcile(project_id))


@router.get("/projects/{project_id}/report")
async def project_report(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> str:
    return await service.generate_report(project_id)


@router.get("/projects/{project_id}/report.csv")
async def project_report_csv(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> Response:
    """Download the migration report as flat CSV (sheets-friendly)."""
    body = await service.generate_report_csv(project_id)
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="migration-{project_id}-report.csv"'
        },
    )


@router.get("/projects/{project_id}/report.json")
async def project_report_json(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> Response:
    """Download the migration report as structured JSON."""
    body = await service.generate_report_json(project_id)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="migration-{project_id}-report.json"'
        },
    )


@router.post("/projects/{project_id}/cancel", response_model=MigrationProjectResponse)
async def cancel_project(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> MigrationProjectResponse:
    project = await service.cancel(project_id)
    return MigrationProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/rollback")
async def rollback_project(
    project_id: int,
    service: MigrationProjectService = Depends(_project_service),
) -> dict:
    return await service.rollback(project_id)
