from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.admission.models import AdmissionApplication
from app.domains.audit.actors import AuditActor
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import ADMISSIONS_APPROVE
from app.domains.admission.repository import (
    AdmissionApplicationRepository,
    AdmissionDocumentRepository,
    AdmissionInterviewRepository,
    AdmissionMeritEntryRepository,
    AdmissionSeatAllocationRepository,
)
from app.domains.admission.schemas import (
    AdmissionApplicationCreate,
    AdmissionApplicationResponse,
    AdmissionApplicationUpdate,
    AdmissionDocumentCreate,
    AdmissionDocumentResponse,
    AdmissionDocumentUpdate,
    AdmissionInterviewCreate,
    AdmissionInterviewResponse,
    AdmissionInterviewUpdate,
    AdmissionMeritEntryCreate,
    AdmissionMeritEntryResponse,
    AdmissionMeritEntryUpdate,
    AdmissionSeatAllocationCreate,
    AdmissionSeatAllocationResponse,
    AdmissionSeatAllocationUpdate,
    AdmissionStatusTransition,
)
from app.domains.admission.service import (
    AdmissionApplicationService,
    AdmissionDocumentService,
    AdmissionInterviewService,
    AdmissionMeritEntryService,
    AdmissionSeatAllocationService,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import (
    assert_tenant_scope,
    assert_tenant_scope_by_parent_id,
    effective_campus_id,
    inject_campus,
)
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/admissions", tags=["admissions"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


async def get_application_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionApplicationService:
    return AdmissionApplicationService(AdmissionApplicationRepository(session, tenant))


async def get_document_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionDocumentService:
    return AdmissionDocumentService(AdmissionDocumentRepository(session, tenant))


async def get_interview_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionInterviewService:
    return AdmissionInterviewService(AdmissionInterviewRepository(session, tenant))


async def get_merit_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionMeritEntryService:
    return AdmissionMeritEntryService(AdmissionMeritEntryRepository(session, tenant))


async def get_allocation_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionSeatAllocationService:
    return AdmissionSeatAllocationService(AdmissionSeatAllocationRepository(session, tenant))


# ---------------------------------------------------------------------------
# Applications — CRUD + Status Transition
# ---------------------------------------------------------------------------


@router.post(
    "/applications",
    response_model=AdmissionApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    data: AdmissionApplicationCreate,
    service: AdmissionApplicationService = Depends(get_application_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionApplicationResponse:
    app = await service.create(data)
    inject_campus(app, tenant)
    return AdmissionApplicationResponse.model_validate(app)


@router.get(
    "/applications/{application_id}",
    response_model=AdmissionApplicationResponse,
)
async def get_application(
    application_id: int,
    service: AdmissionApplicationService = Depends(get_application_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionApplicationResponse:
    app = await service.get(application_id)
    assert_tenant_scope(app, tenant, resource="admission application")
    return AdmissionApplicationResponse.model_validate(app)


@router.get("/applications", response_model=Page[AdmissionApplicationResponse])
async def list_applications(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by application status"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id", description="Filter by campus"
    ),
    program_id: Optional[int] = Query(
        default=None, alias="program_id", description="Filter by program"
    ),
    academic_year_id: Optional[int] = Query(
        default=None,
        alias="academic_year_id",
        description="Filter by academic year",
    ),
    search: Optional[str] = Query(
        default=None, description="Search by name, email, or phone"
    ),
    service: AdmissionApplicationService = Depends(get_application_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[AdmissionApplicationResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    apps, total = await service.list(
        status=status_filter,
        campus_id=effective_campus,
        program_id=program_id,
        academic_year_id=academic_year_id,
        search=search,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [AdmissionApplicationResponse.model_validate(a) for a in apps]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch(
    "/applications/{application_id}",
    response_model=AdmissionApplicationResponse,
)
async def update_application(
    application_id: int,
    data: AdmissionApplicationUpdate,
    service: AdmissionApplicationService = Depends(get_application_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionApplicationResponse:
    existing = await service.get(application_id)
    assert_tenant_scope(existing, tenant, resource="admission application")
    app = await service.update(application_id, data)
    return AdmissionApplicationResponse.model_validate(app)


@router.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_application(
    application_id: int,
    service: AdmissionApplicationService = Depends(get_application_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(application_id)
    assert_tenant_scope(existing, tenant, resource="admission application")
    await service.delete(application_id)


@router.post(
    "/applications/{application_id}/transition",
    response_model=AdmissionApplicationResponse,
)
async def transition_application_status(
    application_id: int,
    data: AdmissionStatusTransition,
    service: AdmissionApplicationService = Depends(get_application_service),
    session: AsyncSession = Depends(get_session),
    _actor: User = Depends(require_permission(ADMISSIONS_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionApplicationResponse:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, application_id, tenant,
        resource="admission application",
    )
    app = await service.transition_status(
        application_id, data.new_status, data.remarks
    )
    return AdmissionApplicationResponse.model_validate(app)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/documents",
    response_model=AdmissionDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    application_id: int,
    data: AdmissionDocumentCreate,
    service: AdmissionDocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionDocumentResponse:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, application_id, tenant,
        resource="admission application",
    )
    doc = await service.create(application_id, data)
    return AdmissionDocumentResponse.model_validate(doc)


@router.get(
    "/documents/{document_id}",
    response_model=AdmissionDocumentResponse,
)
async def get_document(
    document_id: int,
    service: AdmissionDocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionDocumentResponse:
    doc = await service.get(document_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, doc.application_id, tenant,
        resource="admission document",
    )
    return AdmissionDocumentResponse.model_validate(doc)


@router.get(
    "/applications/{application_id}/documents",
    response_model=list[AdmissionDocumentResponse],
)
async def list_application_documents(
    application_id: int,
    service: AdmissionDocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[AdmissionDocumentResponse]:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, application_id, tenant,
        resource="admission application",
    )
    docs = await service.list_by_application(application_id)
    return [AdmissionDocumentResponse.model_validate(d) for d in docs]


@router.patch(
    "/documents/{document_id}/verify",
    response_model=AdmissionDocumentResponse,
)
async def verify_document(
    document_id: int,
    data: AdmissionDocumentUpdate,
    service: AdmissionDocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_permission(ADMISSIONS_APPROVE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionDocumentResponse:
    existing = await service.get(document_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, existing.application_id, tenant,
        resource="admission document",
    )
    doc = await service.verify(
        document_id,
        verification_status=data.verification_status or "verified",
        verified_by=actor.id,
        remarks=data.remarks,
        actor=AuditActor.user(actor.id, actor.username),
    )
    return AdmissionDocumentResponse.model_validate(doc)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: int,
    service: AdmissionDocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(document_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, existing.application_id, tenant,
        resource="admission document",
    )
    await service.delete(document_id)


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------


@router.post(
    "/applications/{application_id}/interviews",
    response_model=AdmissionInterviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_interview(
    application_id: int,
    data: AdmissionInterviewCreate,
    service: AdmissionInterviewService = Depends(get_interview_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionInterviewResponse:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, application_id, tenant,
        resource="admission application",
    )
    interview = await service.create(application_id, data)
    return AdmissionInterviewResponse.model_validate(interview)


@router.get(
    "/interviews/{interview_id}",
    response_model=AdmissionInterviewResponse,
)
async def get_interview(
    interview_id: int,
    service: AdmissionInterviewService = Depends(get_interview_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionInterviewResponse:
    interview = await service.get(interview_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, interview.application_id, tenant,
        resource="admission interview",
    )
    return AdmissionInterviewResponse.model_validate(interview)


@router.get(
    "/applications/{application_id}/interviews",
    response_model=list[AdmissionInterviewResponse],
)
async def list_application_interviews(
    application_id: int,
    service: AdmissionInterviewService = Depends(get_interview_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[AdmissionInterviewResponse]:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, application_id, tenant,
        resource="admission application",
    )
    interviews = await service.list_by_application(application_id)
    return [AdmissionInterviewResponse.model_validate(i) for i in interviews]


@router.patch(
    "/interviews/{interview_id}",
    response_model=AdmissionInterviewResponse,
)
async def update_interview(
    interview_id: int,
    data: AdmissionInterviewUpdate,
    service: AdmissionInterviewService = Depends(get_interview_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionInterviewResponse:
    existing = await service.get(interview_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, existing.application_id, tenant,
        resource="admission interview",
    )
    interview = await service.update(interview_id, data)
    return AdmissionInterviewResponse.model_validate(interview)


# ---------------------------------------------------------------------------
# Merit Entries
# ---------------------------------------------------------------------------


@router.post(
    "/merit-entries",
    response_model=AdmissionMeritEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_merit_entry(
    data: AdmissionMeritEntryCreate,
    service: AdmissionMeritEntryService = Depends(get_merit_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionMeritEntryResponse:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, data.application_id, tenant,
        resource="admission application",
    )
    entry = await service.create(data)
    return AdmissionMeritEntryResponse.model_validate(entry)


@router.get(
    "/merit-entries/{entry_id}",
    response_model=AdmissionMeritEntryResponse,
)
async def get_merit_entry(
    entry_id: int,
    service: AdmissionMeritEntryService = Depends(get_merit_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionMeritEntryResponse:
    entry = await service.get(entry_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, entry.application_id, tenant,
        resource="admission merit entry",
    )
    return AdmissionMeritEntryResponse.model_validate(entry)


@router.get(
    "/merit-entries",
    response_model=Page[AdmissionMeritEntryResponse],
)
async def list_merit_entries(
    pagination: PaginationParams = Depends(),
    program_id: Optional[int] = Query(
        default=None, alias="program_id"
    ),
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status"
    ),
    campus_id: Optional[int] = Query(default=None, alias="campus_id"),
    service: AdmissionMeritEntryService = Depends(get_merit_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[AdmissionMeritEntryResponse]:
    # Merit entries inherit tenancy from their application, so pin the
    # list to the tenant's campus via a join.
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await service.list(
        program_id=program_id,
        academic_year_id=academic_year_id,
        status=status_filter,
        campus_id=effective_campus,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[AdmissionMeritEntryResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch(
    "/merit-entries/{entry_id}",
    response_model=AdmissionMeritEntryResponse,
)
async def update_merit_entry(
    entry_id: int,
    data: AdmissionMeritEntryUpdate,
    service: AdmissionMeritEntryService = Depends(get_merit_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionMeritEntryResponse:
    existing = await service.get(entry_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, existing.application_id, tenant,
        resource="admission merit entry",
    )
    entry = await service.update(entry_id, data)
    return AdmissionMeritEntryResponse.model_validate(entry)


# ---------------------------------------------------------------------------
# Seat Allocations
# ---------------------------------------------------------------------------


@router.post(
    "/seat-allocations",
    response_model=AdmissionSeatAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_seat_allocation(
    data: AdmissionSeatAllocationCreate,
    service: AdmissionSeatAllocationService = Depends(get_allocation_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionSeatAllocationResponse:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, data.application_id, tenant,
        resource="admission application",
    )
    allocation = await service.create(data)
    return AdmissionSeatAllocationResponse.model_validate(allocation)


@router.get(
    "/seat-allocations/{allocation_id}",
    response_model=AdmissionSeatAllocationResponse,
)
async def get_seat_allocation(
    allocation_id: int,
    service: AdmissionSeatAllocationService = Depends(get_allocation_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionSeatAllocationResponse:
    allocation = await service.get(allocation_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, allocation.application_id, tenant,
        resource="admission seat allocation",
    )
    return AdmissionSeatAllocationResponse.model_validate(allocation)


@router.get(
    "/applications/{application_id}/seat-allocations",
    response_model=list[AdmissionSeatAllocationResponse],
)
async def list_application_allocations(
    application_id: int,
    service: AdmissionSeatAllocationService = Depends(get_allocation_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[AdmissionSeatAllocationResponse]:
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, application_id, tenant,
        resource="admission application",
    )
    allocations = await service.list_by_application(application_id)
    return [AdmissionSeatAllocationResponse.model_validate(a) for a in allocations]


@router.patch(
    "/seat-allocations/{allocation_id}",
    response_model=AdmissionSeatAllocationResponse,
)
async def update_seat_allocation(
    allocation_id: int,
    data: AdmissionSeatAllocationUpdate,
    service: AdmissionSeatAllocationService = Depends(get_allocation_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> AdmissionSeatAllocationResponse:
    existing = await service.get(allocation_id)
    await assert_tenant_scope_by_parent_id(
        session, AdmissionApplication, existing.application_id, tenant,
        resource="admission seat allocation",
    )
    allocation = await service.update(allocation_id, data)
    return AdmissionSeatAllocationResponse.model_validate(allocation)
