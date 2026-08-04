from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
import app.domains.report_builder.builders  # noqa: F401 - registers builders with ReportRegistry
from app.domains.report_builder.base import BaseReportBuilder
from app.domains.report_builder.exporters import export_csv, export_excel, export_pdf
from app.domains.report_builder.models import ReportDefinition
from app.domains.report_builder.registry import ReportRegistry
from app.domains.report_builder.schemas import (
    ExportJobCreate,
    ExportJobPage,
    ExportJobResponse,
    ReportColumnSchema,
    ReportDefinitionResponse,
    ReportExecuteRequest,
    ReportExecuteResponse,
    SavedReportCreate,
    SavedReportResponse,
    SavedReportUpdate,
)
from app.domains.report_builder.service import (
    ExportJobService,
    ReportDefinitionService,
    SavedReportService,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/report-builder", tags=["report-builder"])


async def get_def_svc(session: AsyncSession = Depends(get_session)) -> ReportDefinitionService:
    return ReportDefinitionService(session)


async def get_saved_svc(session: AsyncSession = Depends(get_session)) -> SavedReportService:
    return SavedReportService(session)


async def get_export_svc(session: AsyncSession = Depends(get_session)) -> ExportJobService:
    return ExportJobService(session)


# ── Report Definitions ──


@router.get("/definitions", response_model=list[dict])
async def list_report_definitions(
    category: Optional[str] = Query(None),
    svc: ReportDefinitionService = Depends(get_def_svc),
    _user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
) -> list[dict]:
    if category:
        defs = await svc.get_by_category(category)
    else:
        defs, _ = await svc.get_all(limit=1000)
    result = []
    for d in defs:
        meta = {"code": d.code, "name": d.name, "description": d.description, "category": d.category,
                "allowed_roles": d.allowed_roles, "config": d.config}
        if d.config:
            meta["filters"] = d.config.get("filters", [])
            meta["columns"] = d.config.get("columns", [])
        meta["id"] = d.id
        result.append(meta)

    registry_meta = ReportRegistry.list_meta()
    registry_map = {m["code"]: m for m in registry_meta}
    for item in result:
        reg = registry_map.get(item["code"])
        if reg:
            if not item.get("filters"):
                item["filters"] = reg.get("filters", [])
            if not item.get("columns"):
                item["columns"] = reg.get("columns", [])
            item["default_params"] = reg.get("default_params", {})
    return result


@router.get("/definitions/{code}", response_model=dict)
async def get_report_definition(
    code: str,
    _user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
) -> dict:
    builder_cls = ReportRegistry.get(code)
    if not builder_cls:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Report definition not found: {code}")
    meta = builder_cls.meta()
    return {
        "code": meta.code,
        "name": meta.name,
        "description": meta.description,
        "category": meta.category,
        "allowed_roles": meta.allowed_roles,
        "filters": [f.__dict__ for f in meta.filters],
        "columns": [c.__dict__ for c in meta.columns],
        "default_params": meta.default_params,
    }


# ── Report Execution ──


@router.post("/execute", response_model=ReportExecuteResponse)
async def execute_report(
    data: ReportExecuteRequest,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    session: AsyncSession = Depends(get_session),
) -> ReportExecuteResponse:
    def_query = await session.get(ReportDefinition, data.report_definition_id)
    if not def_query:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Report definition not found")

    builder_cls = ReportRegistry.get(def_query.code)
    if not builder_cls:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Report builder not found: {def_query.code}")

    errors = builder_cls.validate_params(data.params)
    if errors:
        from app.core.exceptions import ValidationError
        raise ValidationError("; ".join(f"{k}: {v}" for k, v in errors.items()))

    campus_id = getattr(current_user, "campus_id", None)
    builder = builder_cls()
    raw_data = await builder.fetch_data(data.params, current_user.id, campus_id, session)
    rows = builder.build_rows(raw_data)
    summary = builder.build_summary(raw_data)
    meta = builder_cls.meta()

    return ReportExecuteResponse(
        columns=[ReportColumnSchema(**c.__dict__) for c in meta.columns],
        rows=rows,
        summary=summary,
        total_rows=len(rows),
    )


# ── Saved Reports ──


@router.post("/saved", response_model=SavedReportResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_report(
    data: SavedReportCreate,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: SavedReportService = Depends(get_saved_svc),
) -> SavedReportResponse:
    return SavedReportResponse.model_validate(await svc.create(current_user.id, data))


@router.get("/saved", response_model=Page[SavedReportResponse])
async def list_saved_reports(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: SavedReportService = Depends(get_saved_svc),
) -> Page[SavedReportResponse]:
    items, total = await svc.list(current_user.id, skip=pagination.offset, limit=pagination.limit)
    return Page.create(
        items=[SavedReportResponse.model_validate(s) for s in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.get("/saved/by-definition/{definition_id}", response_model=list[SavedReportResponse])
async def list_saved_reports_by_definition(
    definition_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: SavedReportService = Depends(get_saved_svc),
) -> list[SavedReportResponse]:
    items = await svc.list_by_definition(definition_id, current_user.id)
    return [SavedReportResponse.model_validate(s) for s in items]


@router.get("/saved/{report_id}", response_model=SavedReportResponse)
async def get_saved_report(
    report_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: SavedReportService = Depends(get_saved_svc),
) -> SavedReportResponse:
    return SavedReportResponse.model_validate(await svc.get(report_id, current_user.id))


@router.patch("/saved/{report_id}", response_model=SavedReportResponse)
async def update_saved_report(
    report_id: int,
    data: SavedReportUpdate,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: SavedReportService = Depends(get_saved_svc),
) -> SavedReportResponse:
    return SavedReportResponse.model_validate(await svc.update(report_id, current_user.id, data))


@router.delete("/saved/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_report(
    report_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: SavedReportService = Depends(get_saved_svc),
) -> None:
    await svc.delete(report_id, current_user.id)


# ── Export Jobs ──


@router.post("/exports", response_model=ExportJobResponse, status_code=status.HTTP_201_CREATED)
async def create_export_job(
    data: ExportJobCreate,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: ExportJobService = Depends(get_export_svc),
) -> ExportJobResponse:
    job = await svc.create_job(current_user.id, data, campus_id=current_user.campus_id)
    return ExportJobResponse.model_validate(job)


@router.get("/exports", response_model=ExportJobPage)
async def list_export_jobs(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: ExportJobService = Depends(get_export_svc),
) -> ExportJobPage:
    items, total = await svc.list_jobs(
        current_user.id, skip=pagination.offset, limit=pagination.limit, status_filter=status_filter,
    )
    return ExportJobPage(
        items=[ExportJobResponse.model_validate(j) for j in items],
        total=total, page=pagination.page, size=pagination.size, pages=(total + pagination.size - 1) // pagination.size if pagination.size > 0 else 0,
    )


@router.get("/exports/{job_id}", response_model=ExportJobResponse)
async def get_export_job(
    job_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: ExportJobService = Depends(get_export_svc),
) -> ExportJobResponse:
    return ExportJobResponse.model_validate(await svc.get_job(job_id, current_user.id))


@router.get("/exports/{job_id}/download")
async def download_export(
    job_id: int,
    current_user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    svc: ExportJobService = Depends(get_export_svc),
) -> Response:
    result_data, filename, file_format = await svc.get_result_data(job_id, current_user.id)
    if file_format == "csv":
        content = result_data.encode("utf-8-sig")
        media_type = "text/csv"
    elif file_format == "excel":
        content = bytes.fromhex(result_data)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_format == "pdf":
        content = bytes.fromhex(result_data)
        media_type = "application/pdf"
    else:
        content = result_data.encode("utf-8")
        media_type = "application/octet-stream"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/categories", response_model=list[str])
async def list_report_categories(
    _user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
) -> list[str]:
    categories: set[str] = set()
    for builder_cls in ReportRegistry.get_all():
        categories.add(builder_cls.meta().category)
    return sorted(categories)


@router.get("/registry", response_model=list[dict])
async def list_registry(
    _user: User = Depends(require_role("admin", "staff", "teacher", "accountant", "principal")),
    category: Optional[str] = Query(None),
) -> list[dict]:
    meta_list = ReportRegistry.list_meta()
    if category:
        meta_list = [m for m in meta_list if m["category"] == category]
    return meta_list
