from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page

# ── Constants ──────────────────────────────────────────────────────────

VALID_TRANSACTION_TYPES = {
    "payment", "refund", "reversal", "adjustment", "waiver", "fine", "discount",
}
VALID_RECONCILIATION_STATUSES = {"draft", "submitted", "verified", "approved"}
VALID_RECONCILIATION_ITEM_STATUSES = {"matched", "unmatched", "discrepancy"}
VALID_REPORT_TYPES = {
    "collection_summary", "outstanding_balance", "daily_collection",
    "fee_type_collection", "class_collection", "payment_method_analysis",
    "revenue_report",
}
VALID_RECEIPT_STATUSES = {"active", "cancelled", "void"}

# ── Payment Methods ────────────────────────────────────────────────────


class PaymentMethodCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True
    requires_reference: bool = False
    gateway_config: Optional[dict] = None
    campus_id: Optional[int] = None


class PaymentMethodUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    requires_reference: Optional[bool] = None
    gateway_config: Optional[dict] = None


class PaymentMethodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    requires_reference: bool
    gateway_config: Optional[dict] = None
    campus_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


PaymentMethodPage = Page[PaymentMethodResponse]


# ── Fee Schedules ──────────────────────────────────────────────────────


class FeeScheduleCreate(BaseModel):
    fee_structure_id: int
    name: str
    installment_number: int
    due_date: str
    amount: int
    penalty_amount: int = 0
    discount_amount: int = 0
    campus_id: Optional[int] = None
    status: str = "active"

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Amount must be positive (in cents)")
        return v

    @field_validator("penalty_amount", "discount_amount")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

    @field_validator("installment_number")
    @classmethod
    def installment_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Installment number must be >= 1")
        return v


class FeeScheduleUpdate(BaseModel):
    name: Optional[str] = None
    due_date: Optional[str] = None
    amount: Optional[int] = None
    penalty_amount: Optional[int] = None
    discount_amount: Optional[int] = None
    status: Optional[str] = None


class FeeScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fee_structure_id: int
    name: str
    installment_number: int
    due_date: str
    amount: int
    penalty_amount: int
    discount_amount: int
    campus_id: Optional[int] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


FeeSchedulePage = Page[FeeScheduleResponse]


# ── Transaction Logs ────────────────────────────────────────────────────


class TransactionLogCreate(BaseModel):
    transaction_type: str
    payment_id: Optional[int] = None
    fee_due_id: Optional[int] = None
    student_id: int
    amount: int
    balance_before: int = 0
    balance_after: int = 0
    reference_number: Optional[str] = None
    idempotency_key: Optional[str] = None
    description: Optional[str] = None
    campus_id: Optional[int] = None
    recorded_by: Optional[int] = None

    @field_validator("transaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"Invalid type. Must be one of: {', '.join(sorted(VALID_TRANSACTION_TYPES))}"
            )
        return v


class TransactionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_type: str
    payment_id: Optional[int] = None
    fee_due_id: Optional[int] = None
    student_id: int
    amount: int
    balance_before: int
    balance_after: int
    reference_number: Optional[str] = None
    idempotency_key: Optional[str] = None
    description: Optional[str] = None
    campus_id: Optional[int] = None
    recorded_by: Optional[int] = None
    created_at: datetime.datetime


TransactionLogPage = Page[TransactionLogResponse]


# ── Payment Reconciliations ─────────────────────────────────────────────


class ReconciliationItemCreate(BaseModel):
    payment_id: int
    expected_amount: int
    actual_amount: int
    notes: Optional[str] = None


class ReconciliationCreate(BaseModel):
    # ``date`` matches the DB column type — ISO strings ("2026-08-01")
    # are parsed automatically, so the wire format is unchanged.
    reconciliation_date: datetime.date
    total_amount: int = 0
    total_count: int = 0
    notes: Optional[str] = None
    campus_id: Optional[int] = None
    items: list[ReconciliationItemCreate] = []


class ReconciliationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reconciliation_id: int
    payment_id: int
    expected_amount: int
    actual_amount: int
    difference: int
    status: str
    notes: Optional[str] = None
    created_at: datetime.datetime


class ReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reconciliation_date: datetime.date
    total_amount: int
    total_count: int
    status: str
    notes: Optional[str] = None
    reconciled_by: Optional[int] = None
    campus_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    items: list[ReconciliationItemResponse] = []


ReconciliationPage = Page[ReconciliationResponse]


# ── Receipts ──────────────────────────────────────────────────────────────


class ReceiptGenerate(BaseModel):
    payment_id: int
    notes: Optional[str] = None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: int
    receipt_number: str
    receipt_date: str
    amount: int
    payment_method_name: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    status: str
    printed_count: int
    generated_by: Optional[int] = None
    campus_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


ReceiptPage = Page[ReceiptResponse]


class ReceiptDetailResponse(ReceiptResponse):
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    fee_type_name: Optional[str] = None
    academic_year_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None


# ── Finance Reports ─────────────────────────────────────────────────────


class FinanceReportGenerate(BaseModel):
    report_type: str
    title: str
    parameters: Optional[dict] = None
    file_format: str = "csv"
    campus_id: Optional[int] = None

    @field_validator("report_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_REPORT_TYPES:
            raise ValueError(
                f"Invalid report type. Must be one of: {', '.join(sorted(VALID_REPORT_TYPES))}"
            )
        return v


class FinanceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_type: str
    title: str
    parameters: Optional[dict] = None
    file_format: str
    status: str
    campus_id: Optional[int] = None
    generated_by: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None


FinanceReportPage = Page[FinanceReportResponse]


# ── Financial Exceptions (P13) ──────────────────────────────────────────


class LinkedCaseInfo(BaseModel):
    """The operational case already opened for this exception (P11 reuse)."""

    id: int
    case_number: str
    status: str


class FinancialExceptionOut(BaseModel):
    """A deterministic financial anomaly computed from real records.

    Computed on read — never stored. ``key`` is stable per category+entity
    so an operator can promote the exception into an operational case
    (``source_type=financial_exception``, ``source_id`` = the entity id).
    """

    key: str
    category: str
    severity: str
    title: str
    description: str
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    payment_id: Optional[int] = None
    amount: Optional[int] = None
    reconciliation_item_id: Optional[int] = None
    reconciliation_status: Optional[str] = None
    evidence: dict = {}
    created_at: Optional[datetime.datetime] = None
    linked_case: Optional[LinkedCaseInfo] = None


class FinancialExceptionSummary(BaseModel):
    total: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
    items: list[FinancialExceptionOut]


# ── Outstanding Balances ────────────────────────────────────────────────


class OutstandingBalanceItem(BaseModel):
    student_id: int
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    total_assigned: int
    total_paid: int
    outstanding: int
    due_count: int
    overdue_count: int
    status: str


class OutstandingBalanceSummary(BaseModel):
    total_students: int
    total_assigned: int
    total_paid: int
    total_outstanding: int
    total_overdue: int
    items: list[OutstandingBalanceItem]


# ── Dashboard ──────────────────────────────────────────────────────────────


class SchoolFinanceDashboard(BaseModel):
    total_collected: int
    total_outstanding: int
    total_overdue: int
    payment_count: int
    reconciled_count: int
    pending_reconciliation: int
    collection_rate: float
    today_collection: int
    today_count: int
    recent_transactions: list[TransactionLogResponse] = []
