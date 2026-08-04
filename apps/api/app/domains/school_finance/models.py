from __future__ import annotations

import datetime
from datetime import timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_reference: Mapped[bool] = mapped_column(Boolean, default=False)
    gateway_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PaymentMethod id={self.id} code={self.code} name={self.name}>"


class FeeSchedule(Base):
    __tablename__ = "fee_schedules"
    __table_args__ = (
        UniqueConstraint(
            "fee_structure_id", "installment_number",
            name="uq_fee_schedule_installment",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fee_structure_id: Mapped[int] = mapped_column(
        ForeignKey("fee_structures.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    penalty_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    discount_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<FeeSchedule id={self.id} "
            f"structure={self.fee_structure_id} "
            f"installment={self.installment_number}>"
        )


class TransactionLog(Base):
    __tablename__ = "transaction_logs"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_transaction_idempotency"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id"), nullable=True, index=True
    )
    fee_due_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fee_dues.id"), nullable=True, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    balance_after: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    recorded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<TransactionLog id={self.id} "
            f"type={self.transaction_type} "
            f"amount={self.amount}>"
        )


class PaymentReconciliation(Base):
    __tablename__ = "payment_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False
    )
    total_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reconciled_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    verified_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    items: Mapped[List["ReconciliationItem"]] = relationship(
        back_populates="reconciliation", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentReconciliation id={self.id} "
            f"date={self.reconciliation_date} "
            f"total={self.total_amount}>"
        )


class ReconciliationItem(Base):
    __tablename__ = "reconciliation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(
        ForeignKey("payment_reconciliations.id"), nullable=False
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False
    )
    expected_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    difference: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="matched"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    reconciliation: Mapped[PaymentReconciliation] = relationship(
        back_populates="items"
    )

    def __repr__(self) -> str:
        return (
            f"<ReconciliationItem id={self.id} "
            f"payment={self.payment_id} "
            f"status={self.status}>"
        )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, unique=True
    )
    receipt_number: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )
    receipt_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    printed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    generated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Receipt id={self.id} "
            f"number={self.receipt_number} "
            f"amount={self.amount}>"
        )


class FinanceReport(Base):
    __tablename__ = "finance_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="csv"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    generated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<FinanceReport id={self.id} "
            f"type={self.report_type} status={self.status}>"
        )
