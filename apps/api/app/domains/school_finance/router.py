from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.school_finance.schemas import (
    FeeScheduleCreate,
    FeeSchedulePage,
    FeeScheduleResponse,
    FeeScheduleUpdate,
    FinanceReportGenerate,
    FinanceReportPage,
    FinanceReportResponse,
    OutstandingBalanceSummary,
    PaymentMethodCreate,
    PaymentMethodPage,
    PaymentMethodResponse,
    PaymentMethodUpdate,
    ReceiptDetailResponse,
    ReceiptGenerate,
    ReceiptPage,
    ReceiptResponse,
    ReconciliationCreate,
    ReconciliationPage,
    ReconciliationResponse,
    SchoolFinanceDashboard,
    TransactionLogPage,
    TransactionLogResponse,
)
from app.domains.school_finance.service import (
    FeeScheduleService,
    FinanceReportService,
    OutstandingBalanceService,
    PaymentMethodService,
    ReceiptService,
    ReconciliationService,
    SchoolFinanceDashboardService,
    TransactionLogService,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/school-finance", tags=["school-finance"])


async def get_pm_svc(session: AsyncSession = Depends(get_session)) -> PaymentMethodService:
    return PaymentMethodService(session)


async def get_fs_svc(session: AsyncSession = Depends(get_session)) -> FeeScheduleService:
    return FeeScheduleService(session)


async def get_tx_svc(session: AsyncSession = Depends(get_session)) -> TransactionLogService:
    return TransactionLogService(session)


async def get_rec_svc(session: AsyncSession = Depends(get_session)) -> ReconciliationService:
    return ReconciliationService(session)


async def get_receipt_svc(session: AsyncSession = Depends(get_session)) -> ReceiptService:
    return ReceiptService(session)


async def get_ob_svc(session: AsyncSession = Depends(get_session)) -> OutstandingBalanceService:
    return OutstandingBalanceService(session)


async def get_fr_svc(session: AsyncSession = Depends(get_session)) -> FinanceReportService:
    return FinanceReportService(session)


async def get_dash_svc(session: AsyncSession = Depends(get_session)) -> SchoolFinanceDashboardService:
    return SchoolFinanceDashboardService(session)


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════


@router.get("/dashboard", response_model=SchoolFinanceDashboard)
async def get_dashboard(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    svc: SchoolFinanceDashboardService = Depends(get_dash_svc),
) -> SchoolFinanceDashboard:
    return await svc.get_dashboard(campus_id=campus_id)


# ═══════════════════════════════════════════════════════════════════════
# PAYMENT METHODS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/payment-methods", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_method(
    data: PaymentMethodCreate,
    svc: PaymentMethodService = Depends(get_pm_svc),
) -> PaymentMethodResponse:
    return PaymentMethodResponse.model_validate(await svc.create(data))


@router.get("/payment-methods/{pm_id}", response_model=PaymentMethodResponse)
async def get_payment_method(
    pm_id: int,
    svc: PaymentMethodService = Depends(get_pm_svc),
) -> PaymentMethodResponse:
    return PaymentMethodResponse.model_validate(await svc.get(pm_id))


@router.get("/payment-methods", response_model=PaymentMethodPage)
async def list_payment_methods(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(None, alias="is_active"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    svc: PaymentMethodService = Depends(get_pm_svc),
) -> PaymentMethodPage:
    items, total = await svc.list(
        is_active=is_active, campus_id=campus_id,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[PaymentMethodResponse.model_validate(p) for p in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/payment-methods/{pm_id}", response_model=PaymentMethodResponse)
async def update_payment_method(
    pm_id: int,
    data: PaymentMethodUpdate,
    svc: PaymentMethodService = Depends(get_pm_svc),
) -> PaymentMethodResponse:
    return PaymentMethodResponse.model_validate(await svc.update(pm_id, data))


@router.delete("/payment-methods/{pm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_method(
    pm_id: int,
    svc: PaymentMethodService = Depends(get_pm_svc),
) -> None:
    await svc.delete(pm_id)


# ═══════════════════════════════════════════════════════════════════════
# FEE SCHEDULES
# ═══════════════════════════════════════════════════════════════════════


@router.post("/fee-schedules", response_model=FeeScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_fee_schedule(
    data: FeeScheduleCreate,
    svc: FeeScheduleService = Depends(get_fs_svc),
) -> FeeScheduleResponse:
    return FeeScheduleResponse.model_validate(await svc.create(data))


@router.get("/fee-schedules/{schedule_id}", response_model=FeeScheduleResponse)
async def get_fee_schedule(
    schedule_id: int,
    svc: FeeScheduleService = Depends(get_fs_svc),
) -> FeeScheduleResponse:
    return FeeScheduleResponse.model_validate(await svc.get(schedule_id))


@router.get("/fee-schedules", response_model=FeeSchedulePage)
async def list_fee_schedules(
    pagination: PaginationParams = Depends(),
    fee_structure_id: Optional[int] = Query(None, alias="fee_structure_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    svc: FeeScheduleService = Depends(get_fs_svc),
) -> FeeSchedulePage:
    items, total = await svc.list(
        fee_structure_id=fee_structure_id, status_filter=status_filter,
        campus_id=campus_id, skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[FeeScheduleResponse.model_validate(s) for s in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/fee-schedules/{schedule_id}", response_model=FeeScheduleResponse)
async def update_fee_schedule(
    schedule_id: int,
    data: FeeScheduleUpdate,
    svc: FeeScheduleService = Depends(get_fs_svc),
) -> FeeScheduleResponse:
    return FeeScheduleResponse.model_validate(await svc.update(schedule_id, data))


@router.delete("/fee-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fee_schedule(
    schedule_id: int,
    svc: FeeScheduleService = Depends(get_fs_svc),
) -> None:
    await svc.delete(schedule_id)


@router.get("/fee-structures/{structure_id}/schedules", response_model=list[FeeScheduleResponse])
async def get_fee_structure_schedules(
    structure_id: int,
    svc: FeeScheduleService = Depends(get_fs_svc),
) -> list[FeeScheduleResponse]:
    items = await svc.get_by_fee_structure(structure_id)
    return [FeeScheduleResponse.model_validate(s) for s in items]


# ═══════════════════════════════════════════════════════════════════════
# TRANSACTION LOGS
# ═══════════════════════════════════════════════════════════════════════


@router.get("/transactions/{log_id}", response_model=TransactionLogResponse)
async def get_transaction(
    log_id: int,
    svc: TransactionLogService = Depends(get_tx_svc),
) -> TransactionLogResponse:
    return TransactionLogResponse.model_validate(await svc.get(log_id))


@router.get("/transactions", response_model=TransactionLogPage)
async def list_transactions(
    pagination: PaginationParams = Depends(),
    student_id: Optional[int] = Query(None, alias="student_id"),
    transaction_type: Optional[str] = Query(None, alias="transaction_type"),
    payment_id: Optional[int] = Query(None, alias="payment_id"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    svc: TransactionLogService = Depends(get_tx_svc),
) -> TransactionLogPage:
    items, total = await svc.list(
        student_id=student_id, transaction_type=transaction_type,
        payment_id=payment_id, campus_id=campus_id,
        from_date=from_date, to_date=to_date,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[TransactionLogResponse.model_validate(t) for t in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.get("/transactions/student/{student_id}/balance", response_model=dict)
async def get_student_balance(
    student_id: int,
    svc: TransactionLogService = Depends(get_tx_svc),
) -> dict:
    balance = await svc.get_student_balance(student_id)
    return {"student_id": student_id, "balance": balance}


# ═══════════════════════════════════════════════════════════════════════
# RECONCILIATIONS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/reconciliations", response_model=ReconciliationResponse, status_code=status.HTTP_201_CREATED)
async def create_reconciliation(
    data: ReconciliationCreate,
    svc: ReconciliationService = Depends(get_rec_svc),
) -> ReconciliationResponse:
    return ReconciliationResponse.model_validate(await svc.create(data, reconciled_by=0))


class StatusUpdateBody(BaseModel):
    status: str


@router.post("/reconciliations/{rec_id}/verify", response_model=ReconciliationResponse)
async def verify_reconciliation(
    rec_id: int,
    svc: ReconciliationService = Depends(get_rec_svc),
) -> ReconciliationResponse:
    return ReconciliationResponse.model_validate(await svc.verify(rec_id, reviewed_by=0))


@router.post("/reconciliations/{rec_id}/approve", response_model=ReconciliationResponse)
async def approve_reconciliation(
    rec_id: int,
    svc: ReconciliationService = Depends(get_rec_svc),
) -> ReconciliationResponse:
    return ReconciliationResponse.model_validate(await svc.approve(rec_id, reviewed_by=0))


@router.get("/reconciliations/{rec_id}", response_model=ReconciliationResponse)
async def get_reconciliation(
    rec_id: int,
    svc: ReconciliationService = Depends(get_rec_svc),
) -> ReconciliationResponse:
    return ReconciliationResponse.model_validate(await svc.get(rec_id))


@router.get("/reconciliations", response_model=ReconciliationPage)
async def list_reconciliations(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    svc: ReconciliationService = Depends(get_rec_svc),
) -> ReconciliationPage:
    items, total = await svc.list(
        status_filter=status_filter, campus_id=campus_id,
        from_date=from_date, to_date=to_date,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[ReconciliationResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


# ═══════════════════════════════════════════════════════════════════════
# RECEIPTS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/receipts/generate", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def generate_receipt(
    data: ReceiptGenerate,
    svc: ReceiptService = Depends(get_receipt_svc),
) -> ReceiptResponse:
    return ReceiptResponse.model_validate(await svc.generate(data, generated_by=0))


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetailResponse)
async def get_receipt(
    receipt_id: int,
    svc: ReceiptService = Depends(get_receipt_svc),
) -> ReceiptDetailResponse:
    return ReceiptDetailResponse.model_validate(await svc.get(receipt_id))


@router.get("/receipts/by-number/{receipt_number}", response_model=ReceiptDetailResponse)
async def get_receipt_by_number(
    receipt_number: str,
    svc: ReceiptService = Depends(get_receipt_svc),
) -> ReceiptDetailResponse:
    return ReceiptDetailResponse.model_validate(await svc.get_by_number(receipt_number))


@router.get("/receipts", response_model=ReceiptPage)
async def list_receipts(
    pagination: PaginationParams = Depends(),
    payment_id: Optional[int] = Query(None, alias="payment_id"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    svc: ReceiptService = Depends(get_receipt_svc),
) -> ReceiptPage:
    items, total = await svc.list(
        payment_id=payment_id, campus_id=campus_id,
        status_filter=status_filter, from_date=from_date, to_date=to_date,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[ReceiptResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.get("/receipts/{receipt_id}/print", response_class=HTMLResponse)
async def print_receipt(
    receipt_id: int,
    svc: ReceiptService = Depends(get_receipt_svc),
) -> str:
    await svc.increment_print_count(receipt_id)
    return await svc.generate_receipt_html(receipt_id)


@router.get("/receipts/{receipt_id}/detail", response_model=ReceiptDetailResponse)
async def get_receipt_detail(
    receipt_id: int,
    svc: ReceiptService = Depends(get_receipt_svc),
) -> ReceiptDetailResponse:
    return await svc.get_receipt_detail(receipt_id)


@router.get("/receipts/export/csv")
async def export_receipts_csv(
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    svc: ReceiptService = Depends(get_receipt_svc),
):
    csv_content = await svc.export_receipts_csv(
        campus_id=campus_id, from_date=from_date, to_date=to_date,
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts_export.csv"},
    )


# ═══════════════════════════════════════════════════════════════════════
# OUTSTANDING BALANCES
# ═══════════════════════════════════════════════════════════════════════


@router.get("/outstanding-balances", response_model=OutstandingBalanceSummary)
async def get_outstanding_balances(
    pagination: PaginationParams = Depends(),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    class_id: Optional[int] = Query(None, alias="class_id"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    svc: OutstandingBalanceService = Depends(get_ob_svc),
) -> OutstandingBalanceSummary:
    return await svc.get_outstanding(
        academic_year_id=academic_year_id, class_id=class_id,
        campus_id=campus_id, skip=pagination.offset, limit=pagination.limit,
    )


# ═══════════════════════════════════════════════════════════════════════
# FINANCE REPORTS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/reports/generate", response_model=FinanceReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_finance_report(
    data: FinanceReportGenerate,
    svc: FinanceReportService = Depends(get_fr_svc),
) -> FinanceReportResponse:
    return FinanceReportResponse.model_validate(await svc.generate_report(data, generated_by=0))


@router.get("/reports", response_model=FinanceReportPage)
async def list_finance_reports(
    pagination: PaginationParams = Depends(),
    report_type: Optional[str] = Query(None, alias="report_type"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    svc: FinanceReportService = Depends(get_fr_svc),
) -> FinanceReportPage:
    items, total = await svc.list_reports(
        report_type=report_type, campus_id=campus_id,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[FinanceReportResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.get("/reports/collection-summary/csv")
async def export_collection_summary_csv(
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    svc: FinanceReportService = Depends(get_fr_svc),
):
    csv_content = await svc.generate_collection_summary_csv(
        academic_year_id=academic_year_id, campus_id=campus_id,
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=collection_summary.csv"},
    )
