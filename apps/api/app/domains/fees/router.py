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

router = APIRouter(prefix="/api/fees", tags=["fees"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


async def get_fee_type_service(
    session: AsyncSession = Depends(get_session),
) -> FeeTypeService:
    return FeeTypeService(FeeTypeRepository(session))


async def get_fee_structure_service(
    session: AsyncSession = Depends(get_session),
) -> FeeStructureService:
    return FeeStructureService(
        FeeStructureRepository(session),
        AcademicYearRepository(session),
        ClassRepository(session),
        FeeTypeRepository(session),
    )


async def get_fee_due_service(
    session: AsyncSession = Depends(get_session),
) -> FeeDueService:
    return FeeDueService(
        FeeDueRepository(session),
        StudentRepository(session),
        AcademicYearRepository(session),
        ClassRepository(session),
        EnrollmentRepository(session),
        FeeStructureRepository(session),
        FeeTypeRepository(session),
    )


async def get_payment_service(
    session: AsyncSession = Depends(get_session),
) -> PaymentService:
    return PaymentService(
        PaymentRepository(session),
        FeeDueRepository(session),
        StudentRepository(session),
    )


async def get_summary_service(
    session: AsyncSession = Depends(get_session),
) -> SummaryService:
    return SummaryService(
        FeeDueRepository(session),
        EnrollmentRepository(session),
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
) -> FeeTypeResponse:
    ft = await service.create(data)
    return FeeTypeResponse.model_validate(ft)


@router.get("/fee-types/{type_id}", response_model=FeeTypeResponse)
async def get_fee_type(
    type_id: int,
    service: FeeTypeService = Depends(get_fee_type_service),
) -> FeeTypeResponse:
    ft = await service.get(type_id)
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
) -> Page[FeeTypeResponse]:
    items, total = await service.list(
        status=status_filter,
        campus_id=campus_id,
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
) -> FeeTypeResponse:
    ft = await service.update(type_id, data)
    return FeeTypeResponse.model_validate(ft)


@router.post(
    "/fee-types/{type_id}/deactivate",
    response_model=FeeTypeResponse,
)
async def deactivate_fee_type(
    type_id: int,
    service: FeeTypeService = Depends(get_fee_type_service),
) -> FeeTypeResponse:
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
) -> FeeStructureResponse:
    fs = await service.create(data)
    return FeeStructureResponse.model_validate(fs)


@router.get(
    "/structures/{structure_id}",
    response_model=FeeStructureResponse,
)
async def get_fee_structure(
    structure_id: int,
    service: FeeStructureService = Depends(get_fee_structure_service),
) -> FeeStructureResponse:
    fs = await service.get(structure_id)
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
) -> Page[FeeStructureResponse]:
    items, total = await service.list(
        academic_year_id=academic_year_id,
        class_id=class_id,
        fee_type_id=fee_type_id,
        status=status_filter,
        campus_id=campus_id,
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
) -> FeeStructureResponse:
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
) -> list[StudentFeeResponse]:
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
) -> list[FeeDueResponse]:
    dues = await service.create_dues(student_id, academic_year_id)
    return [FeeDueResponse.model_validate(d) for d in dues]


@router.get("/dues/{due_id}", response_model=FeeDueResponse)
async def get_fee_due(
    due_id: int,
    service: FeeDueService = Depends(get_fee_due_service),
) -> FeeDueResponse:
    due = await service.get(due_id)
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
) -> Page[FeeDueResponse]:
    items, total = await service.list(
        student_id=student_id,
        academic_year_id=academic_year_id,
        status=status_filter,
        campus_id=campus_id,
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
) -> list[FeeDueResponse]:
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
) -> PaymentResult:
    result = await service.record_payment(data)
    return PaymentResult(
        payment=PaymentResponse.model_validate(result["payment"]),
        fee_due=FeeDueResponse.model_validate(result["fee_due"]),
    )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await service.get_payment(payment_id)
    return PaymentResponse.model_validate(payment)


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
) -> Page[PaymentResponse]:
    items, total = await service.repo.list(
        student_id=student_id,
        fee_due_id=fee_due_id,
        campus_id=campus_id,
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
) -> list[PaymentResponse]:
    payments = await service.get_student_payments(student_id)
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get(
    "/dues/{fee_due_id}/payments",
    response_model=list[PaymentResponse],
)
async def get_fee_due_payments(
    fee_due_id: int,
    service: PaymentService = Depends(get_payment_service),
) -> list[PaymentResponse]:
    payments = await service.get_fee_due_payments(fee_due_id)
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get("/payments/by-date-range", response_model=list[PaymentResponse])
async def get_payments_by_date_range(
    start_date: str = Query(..., alias="start_date"),
    end_date: str = Query(..., alias="end_date"),
    service: PaymentService = Depends(get_payment_service),
) -> list[PaymentResponse]:
    payments = await service.get_payments_by_date_range(start_date, end_date)
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get(
    "/payments/by-receipt/{receipt_number}",
    response_model=PaymentResponse,
)
async def get_payment_by_receipt_number(
    receipt_number: str,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await service.get_payment_by_receipt_number(receipt_number)
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
) -> StudentFinancialSummary:
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
) -> ClassFinancialSummary:
    summary = await service.get_class_summary(class_id, academic_year_id)
    return ClassFinancialSummary(**summary)