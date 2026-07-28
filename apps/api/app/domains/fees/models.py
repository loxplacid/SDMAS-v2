from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class FeeType(Base):
    __tablename__ = "fee_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<FeeType id={self.id} name={self.name}>"


class FeeStructure(Base):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint(
            "academic_year_id", "class_id", "fee_type_id",
            name="uq_fee_structure_per_year_class_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    fee_type_id: Mapped[int] = mapped_column(
        ForeignKey("fee_types.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(nullable=False)
    frequency: Mapped[str] = mapped_column(
        String(50), nullable=False, default="annual"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<FeeStructure id={self.id} "
            f"year_id={self.academic_year_id} "
            f"class_id={self.class_id} "
            f"amount={self.amount}>"
        )


class FeeDue(Base):
    __tablename__ = "fee_dues"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "fee_structure_id",
            name="uq_fee_due_per_student_structure",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    fee_structure_id: Mapped[int] = mapped_column(
        ForeignKey("fee_structures.id"), nullable=False
    )
    original_amount: Mapped[int] = mapped_column(nullable=False)
    amount_paid: Mapped[int] = mapped_column(nullable=False, default=0)
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unpaid"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<FeeDue id={self.id} "
            f"student_id={self.student_id} "
            f"amount={self.original_amount} "
            f"paid={self.amount_paid}>"
        )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    fee_due_id: Mapped[int] = mapped_column(
        ForeignKey("fee_dues.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(nullable=False)
    payment_date: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    payment_method: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    receipt_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} "
            f"student_id={self.student_id} "
            f"amount={self.amount}>"
        )