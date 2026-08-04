from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.jobs.schemas import (
    JobCreate,
    JobListResponse,
    JobResponse,
    JobUpdate,
)
from app.domains.jobs.service import JobService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import (
    assert_tenant_scope_or_owner,
    effective_campus_id,
    inject_campus,
)
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def get_job_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobService:
    return JobService(session, tenant)


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreate,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobResponse:
    if data.user_id is None:
        data.user_id = current_user.id
    job = await service.create_job(data)
    inject_campus(job, tenant)
    return JobResponse.model_validate(job)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobListResponse:
    items, total = await service.list_jobs(
        status=status,
        job_type=job_type,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return JobListResponse(
        items=[JobResponse.model_validate(j) for j in items],
        total=total,
    )


@router.get("/all", response_model=JobListResponse)
async def list_all_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    campus_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require_role("admin")),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobListResponse:
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await service.list_jobs(
        status=status,
        job_type=job_type,
        campus_id=effective_campus,
        skip=skip,
        limit=limit,
    )
    return JobListResponse(
        items=[JobResponse.model_validate(j) for j in items],
        total=total,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobResponse:
    job = await service.get_job(job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    assert_tenant_scope_or_owner(
        job, tenant, current_user.id, resource="job"
    )
    return JobResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: int,
    data: JobUpdate,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobResponse:
    job = await service.get_job(job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    assert_tenant_scope_or_owner(
        job, tenant, current_user.id, resource="job"
    )
    updated = await service.update_job(job_id, data)
    return JobResponse.model_validate(updated)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobResponse:
    existing = await service.get_job(job_id)
    if existing is None:
        raise NotFoundError(f"Job {job_id} not found")
    assert_tenant_scope_or_owner(
        existing, tenant, current_user.id, resource="job"
    )
    job = await service.cancel_job(job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return JobResponse.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> JobResponse:
    existing = await service.get_job(job_id)
    if existing is None:
        raise NotFoundError(f"Job {job_id} not found")
    assert_tenant_scope_or_owner(
        existing, tenant, current_user.id, resource="job"
    )
    job = await service.retry_job(job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return JobResponse.model_validate(job)


@router.get("/stats/queue", response_model=dict)
async def queue_stats(
    service: JobService = Depends(get_job_service),
    _: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> dict:
    pending = await service.repo.count_pending()
    return {"pending": pending}
