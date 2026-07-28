from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.pagination import Page

VALID_FEE_TYPE_STATUSES = {"active", "inactive"}
VALID_FEE_STRUCTURE_STATUSES = {"active", "inactive"}
VALID_FEE_DUE_STATUSES = {"unpaid", "partially_paid", "paid"}
VALID_PAYMENT_METHODS = {"cash", "bank_transfer", "cheque", "card", "mobile_money", "other"}


# ---------------------------------------------------------------------------
# FeeType
# ---------------------------------------------------------------------------


class FeeTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Fee type name is required")
        return stripped


class FeeTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Fee type name cannot be empty")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_FEE_TYPE_STATUSES:
            raise ValueError("Invalid fee type status")
        return v


class FeeTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# FeeStructure
# ---------------------------------------------------------------------------


class FeeStructureCreate(BaseModel):
    academic_year_id: int
    class_id: int
    fee_type_id: int
    amount: int
    frequency: str = "annual"

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Fee amount must be a positive integer")
        return v


class FeeStructureUpdate(BaseModel):
    academic_year_id: Optional[int] = None
    class_id: Optional[int] = None
    fee_type_id: Optional[int] = None
    amount: Optional[int] = None
    frequency: Optional[str] = None
    status: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Fee amount must be a positive integer")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_FEE_STRUCTURE_STATUSES:
            raise ValueError("Invalid fee structure status")
        return v


class FeeStructureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    academic_year_id: int
    class_id: int
    fee_type_id: int
    amount: int
    frequency: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Student Fee (view — fee structures applicable to a student)
# ---------------------------------------------------------------------------


class StudentFeeResponse(BaseModel):
    id: int
    academic_year_id: int
    class_id: int
    fee_type_id: int
    fee_type_name: str
    amount: int
    frequency: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# FeeDue
# ---------------------------------------------------------------------------


class FeeDueCreate(BaseModel):
    student_id: int
    academic_year_id: int


class FeeDueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    academic_year_id: int
    fee_structure_id: int
    original_amount: int
    amount_paid: int
    due_date: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------


class PaymentCreate(BaseModel):
    student_id: int
    fee_due_id: int
    amount: int
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Payment amount must be a positive integer")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_method(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_PAYMENT_METHODS:
            raise ValueError(f"Invalid payment method. Must be one of: {', '.join(sorted(VALID_PAYMENT_METHODS))}")
        return v


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    fee_due_id: int
    amount: int
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    created_at: datetime.datetime


class PaymentResult(BaseModel):
    payment: PaymentResponse
    fee_due: FeeDueResponse


# ---------------------------------------------------------------------------
# Summary schemas
# ---------------------------------------------------------------------------


class StudentFinancialSummary(BaseModel):
    student_id: int
    academic_year_id: int
    total_fees_assigned: int
    total_paid: int
    total_outstanding: int
    unpaid_count: int
    partially_paid_count: int
    paid_count: int


class ClassFinancialSummary(BaseModel):
    class_id: int
    academic_year_id: int
    total_students: int
    total_fees_assigned: int
    total_collected: int
    total_outstanding: int
    students_with_outstanding: int


# ---------------------------------------------------------------------------
# Paginated responses
# ---------------------------------------------------------------------------

FeeTypePage = Page[FeeTypeResponse]
FeeStructurePage = Page[FeeStructureResponse]
FeeDuePage = Page[FeeDueResponse]
PaymentPage = Page[PaymentResponse]