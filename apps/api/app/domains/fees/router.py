from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    EnrollmentRepository,
)
from app.domains.audit.actors import AuditActor
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    FEES_CREATE,
    FEES_RECORD_PAYMENT,
    FEES_REFUND,
    FEES_UPDATE,
)
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
    PaymentRepository,
)
from app.domains.fees.schemas import (
    ClassFinancialSummary,
    FeeDueResponse,
    FeeStructureCreate,
    FeeStructureResponse,
    FeeStructureUpdate,
    FeeTypeCreate,
    FeeTypeResponse,
    FeeTypeUpdate,
    PaymentCreate,
    PaymentResponse,
    PaymentResult,
    RefundCreate,
    RefundResult,
    StudentFeeResponse,
    StudentFinancialSummary,
)
from app.domains.fees.service import (
    FeeDueService,
    FeeStructureService,
    FeeTypeService,
    PaymentService,
    SummaryService,
)
from app.domains.student.repository import StudentRepository
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import (
    assert_tenant_scope,
    effective_campus_id,
    inject_campus,
)
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/fees", tags=["fees"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


async def get_fee_type_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeTypeService:
    return FeeTypeService(FeeTypeRepository(session, tenant))


async def get_fee_structure_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeStructureService:
    return FeeStructureService(
        FeeStructureRepository(session, tenant),
        AcademicYearRepository(session, tenant),
        ClassRepository(session, tenant),
        FeeTypeRepository(session, tenant),
    )


async def get_fee_due_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeDueService:
    return FeeDueService(
        FeeDueRepository(session, tenant),
        StudentRepository(session, tenant),
        AcademicYearRepository(session, tenant),
        ClassRepository(session, tenant),
        EnrollmentRepository(session, tenant),
        FeeStructureRepository(session, tenant),
        FeeTypeRepository(session, tenant),
    )


async def get_payment_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PaymentService:
    return PaymentService(
        PaymentRepository(session, tenant),
        FeeDueRepository(session, tenant),
        StudentRepository(session, tenant),
    )


async def get_summary_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SummaryService:
    return SummaryService(
        FeeDueRepository(session, tenant),
        EnrollmentRepository(session, tenant),
    )


# ---------------------------------------------------------------------------
# Fee Types
# ---------------------------------------------------------------------------


@router.post(
    "/fee-types",
    response_model=FeeTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fee_type(
    data: FeeTypeCreate,
    service: FeeTypeService = Depends(get_fee_type_service),
    _actor: User = Depends(require_permission(FEES_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeTypeResponse:
    ft = await service.create(data)
    inject_campus(ft, tenant)
    return FeeTypeResponse.model_validate(ft)


@router.get("/fee-types/{type_id}", response_model=FeeTypeResponse)
async def get_fee_type(
    type_id: int,
    service: FeeTypeService = Depends(get_fee_type_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeTypeResponse:
    ft = await service.get(type_id)
    assert_tenant_scope(ft, tenant, resource="fee type")
    return FeeTypeResponse.model_validate(ft)


@router.get("/fee-types", response_model=Page[FeeTypeResponse])
async def list_fee_types(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id", description="Filter by campus"
    ),
    service: FeeTypeService = Depends(get_fee_type_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[FeeTypeResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await service.list(
        status=status_filter,
        campus_id=effective_campus,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[FeeTypeResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/fee-types/{type_id}", response_model=FeeTypeResponse)
async def update_fee_type(
    type_id: int,
    data: FeeTypeUpdate,
    service: FeeTypeService = Depends(get_fee_type_service),
    _actor: User = Depends(require_permission(FEES_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeTypeResponse:
    existing = await service.get(type_id)
    assert_tenant_scope(existing, tenant, resource="fee type")
    ft = await service.update(type_id, data)
    return FeeTypeResponse.model_validate(ft)


@router.post(
    "/fee-types/{type_id}/deactivate",
    response_model=FeeTypeResponse,
)
async def deactivate_fee_type(
    type_id: int,
    service: FeeTypeService = Depends(get_fee_type_service),
    _actor: User = Depends(require_permission(FEES_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeTypeResponse:
    existing = await service.get(type_id)
    assert_tenant_scope(existing, tenant, resource="fee type")
    ft = await service.deactivate(type_id)
    return FeeTypeResponse.model_validate(ft)


# ---------------------------------------------------------------------------
# Fee Structures
# ---------------------------------------------------------------------------


@router.post(
    "/structures",
    response_model=FeeStructureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fee_structure(
    data: FeeStructureCreate,
    service: FeeStructureService = Depends(get_fee_structure_service),
    _actor: User = Depends(require_permission(FEES_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeStructureResponse:
    fs = await service.create(data)
    inject_campus(fs, tenant)
    return FeeStructureResponse.model_validate(fs)


@router.get(
    "/structures/{structure_id}",
    response_model=FeeStructureResponse,
)
async def get_fee_structure(
    structure_id: int,
    service: FeeStructureService = Depends(get_fee_structure_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeStructureResponse:
    fs = await service.get(structure_id)
    assert_tenant_scope(fs, tenant, resource="fee structure")
    return FeeStructureResponse.model_validate(fs)


@router.get("/structures", response_model=Page[FeeStructureResponse])
async def list_fee_structures(
    pagination: PaginationParams = Depends(),
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    class_id: Optional[int] = Query(default=None, alias="class_id"),
    fee_type_id: Optional[int] = Query(
        default=None, alias="fee_type_id"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id"
    ),
    service: FeeStructureService = Depends(get_fee_structure_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[FeeStructureResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await service.list(
        academic_year_id=academic_year_id,
        class_id=class_id,
        fee_type_id=fee_type_id,
        status=status_filter,
        campus_id=effective_campus,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[FeeStructureResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch(
    "/structures/{structure_id}",
    response_model=FeeStructureResponse,
)
async def update_fee_structure(
    structure_id: int,
    data: FeeStructureUpdate,
    service: FeeStructureService = Depends(get_fee_structure_service),
    _actor: User = Depends(require_permission(FEES_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeStructureResponse:
    existing = await service.get(structure_id)
    assert_tenant_scope(existing, tenant, resource="fee structure")
    fs = await service.update(structure_id, data)
    return FeeStructureResponse.model_validate(fs)


# ---------------------------------------------------------------------------
# Student Fees (applicable structures)
# ---------------------------------------------------------------------------


@router.get("/students/{student_id}/fees", response_model=list[StudentFeeResponse])
async def get_student_fees(
    student_id: int,
    academic_year_id: int = Query(
        ..., alias="academic_year_id", description="Academic year ID"
    ),
    service: FeeDueService = Depends(get_fee_due_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[StudentFeeResponse]:
    student = await StudentRepository(session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    fees = await service.get_student_fees(student_id, academic_year_id)
    return [StudentFeeResponse(**f) for f in fees]


# ---------------------------------------------------------------------------
# Fee Dues
# ---------------------------------------------------------------------------


@router.post(
    "/dues",
    response_model=list[FeeDueResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_fee_dues(
    student_id: int = Query(..., alias="student_id"),
    academic_year_id: int = Query(..., alias="academic_year_id"),
    service: FeeDueService = Depends(get_fee_due_service),
    session: AsyncSession = Depends(get_session),
    _actor: User = Depends(require_permission(FEES_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[FeeDueResponse]:
    student = await StudentRepository(session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    dues = await service.create_dues(student_id, academic_year_id)
    for due in dues:
        inject_campus(due, tenant)
    return [FeeDueResponse.model_validate(d) for d in dues]


@router.get("/dues/{due_id}", response_model=FeeDueResponse)
async def get_fee_due(
    due_id: int,
    service: FeeDueService = Depends(get_fee_due_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> FeeDueResponse:
    due = await service.get(due_id)
    assert_tenant_scope(due, tenant, resource="fee due")
    return FeeDueResponse.model_validate(due)


@router.get("/dues", response_model=Page[FeeDueResponse])
async def list_fee_dues(
    pagination: PaginationParams = Depends(),
    student_id: Optional[int] = Query(
        default=None, alias="student_id"
    ),
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id"
    ),
    service: FeeDueService = Depends(get_fee_due_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[FeeDueResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await service.list(
        student_id=student_id,
        academic_year_id=academic_year_id,
        status=status_filter,
        campus_id=effective_campus,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[FeeDueResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/students/{student_id}/dues", response_model=list[FeeDueResponse])
async def get_student_dues(
    student_id: int,
    academic_year_id: Optional[int] = Query(
        default=None, alias="academic_year_id"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status"
    ),
    service: FeeDueService = Depends(get_fee_due_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[FeeDueResponse]:
    student = await StudentRepository(session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    dues = await service.get_student_dues(
        student_id,
        academic_year_id=academic_year_id,
        status=status_filter,
    )
    return [FeeDueResponse.model_validate(d) for d in dues]


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


@router.post(
    "/payments",
    response_model=PaymentResult,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    data: PaymentCreate,
    service: PaymentService = Depends(get_payment_service),
    session: AsyncSession = Depends(get_session),
    _actor: User = Depends(require_permission(FEES_RECORD_PAYMENT)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PaymentResult:
    student = await StudentRepository(session, tenant).get_by_id(data.student_id)
    assert_tenant_scope(student, tenant, resource="student")
    result = await service.record_payment(
        data,
        actor=AuditActor.user(_actor.id, _actor.username),
    )
    inject_campus(result["payment"], tenant)
    return PaymentResult(
        payment=PaymentResponse.model_validate(result["payment"]),
        fee_due=FeeDueResponse.model_validate(result["fee_due"]),
    )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    service: PaymentService = Depends(get_payment_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PaymentResponse:
    payment = await service.get_payment(payment_id)
    assert_tenant_scope(payment, tenant, resource="payment")
    return PaymentResponse.model_validate(payment)


@router.post(
    "/payments/{payment_id}/refund",
    response_model=RefundResult,
)
async def refund_payment(
    payment_id: int,
    data: RefundCreate,
    service: PaymentService = Depends(get_payment_service),
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_permission(FEES_REFUND)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RefundResult:
    payment = await service.get_payment(payment_id)
    assert_tenant_scope(payment, tenant, resource="payment")
    result = await service.record_refund(
        payment_id,
        amount=data.amount,
        reason=data.reason,
        actor=AuditActor.user(actor.id, actor.username),
    )
    return RefundResult(
        payment=PaymentResponse.model_validate(result["payment"]),
        fee_due=FeeDueResponse.model_validate(result["fee_due"]),
    )


@router.get("/payments", response_model=Page[PaymentResponse])
async def list_payments(
    pagination: PaginationParams = Depends(),
    student_id: Optional[int] = Query(
        default=None, alias="student_id"
    ),
    fee_due_id: Optional[int] = Query(
        default=None, alias="fee_due_id"
    ),
    campus_id: Optional[int] = Query(
        default=None, alias="campus_id"
    ),
    service: PaymentService = Depends(get_payment_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[PaymentResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    items, total = await service.repo.list(
        student_id=student_id,
        fee_due_id=fee_due_id,
        campus_id=effective_campus,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[PaymentResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/students/{student_id}/payments",
    response_model=list[PaymentResponse],
)
async def get_student_payments(
    student_id: int,
    service: PaymentService = Depends(get_payment_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[PaymentResponse]:
    student = await StudentRepository(session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    payments = await service.get_student_payments(student_id)
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get(
    "/dues/{fee_due_id}/payments",
    response_model=list[PaymentResponse],
)
async def get_fee_due_payments(
    fee_due_id: int,
    service: PaymentService = Depends(get_payment_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[PaymentResponse]:
    due = await FeeDueRepository(session, tenant).get_by_id(fee_due_id)
    assert_tenant_scope(due, tenant, resource="fee due")
    payments = await service.get_fee_due_payments(fee_due_id)
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get("/payments/by-date-range", response_model=list[PaymentResponse])
async def get_payments_by_date_range(
    start_date: str = Query(..., alias="start_date"),
    end_date: str = Query(..., alias="end_date"),
    campus_id: Optional[int] = Query(default=None, alias="campus_id"),
    service: PaymentService = Depends(get_payment_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> list[PaymentResponse]:
    effective_campus = effective_campus_id(tenant, campus_id)
    payments = await service.get_payments_by_date_range(
        start_date, end_date, campus_id=effective_campus
    )
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get(
    "/payments/by-receipt/{receipt_number}",
    response_model=PaymentResponse,
)
async def get_payment_by_receipt_number(
    receipt_number: str,
    service: PaymentService = Depends(get_payment_service),
    tenant: TenantContext = Depends(require_tenant_context),
) -> PaymentResponse:
    payment = await service.get_payment_by_receipt_number(receipt_number)
    assert_tenant_scope(payment, tenant, resource="payment")
    return PaymentResponse.model_validate(payment)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


@router.get(
    "/students/{student_id}/summary",
    response_model=StudentFinancialSummary,
)
async def get_student_financial_summary(
    student_id: int,
    academic_year_id: int = Query(
        ..., alias="academic_year_id"
    ),
    service: SummaryService = Depends(get_summary_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> StudentFinancialSummary:
    student = await StudentRepository(session, tenant).get_by_id(student_id)
    assert_tenant_scope(student, tenant, resource="student")
    summary = await service.get_student_summary(student_id, academic_year_id)
    return StudentFinancialSummary(**summary)


@router.get(
    "/classes/{class_id}/summary",
    response_model=ClassFinancialSummary,
)
async def get_class_financial_summary(
    class_id: int,
    academic_year_id: int = Query(
        ..., alias="academic_year_id"
    ),
    service: SummaryService = Depends(get_summary_service),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ClassFinancialSummary:
    cls = await ClassRepository(session, tenant).get_by_id(class_id)
    assert_tenant_scope(cls, tenant, resource="class")
    summary = await service.get_class_summary(class_id, academic_year_id)
    return ClassFinancialSummary(**summary)