from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class FeeType(Base):
    __tablename__ = "fee_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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
        # A fee due can never owe more than it was assigned or hold a
        # negative paid balance.  Enforced at the DB layer so a concurrent
        # double-payment can never push the balance out of range.
        CheckConstraint(
            "amount_paid >= 0 AND amount_paid <= original_amount",
            name="ck_fee_due_amount_paid_range",
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
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
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
    """A recorded student fee payment.

    ``amount`` is stored in **minor currency units** (paise for INR) as an
    integer — floating-point is never used for monetary math.

    Lifecycle (explicit states)::

        completed ──> partially_refunded ──> refunded
          └────────────────────▲

    ``idempotency_key`` makes payment recording idempotent: a retried or
    duplicated request carrying the same key resolves to the original
    payment instead of creating a second financial record.  The key is
    UNIQUE at the DB layer, so even a concurrent duplicate cannot slip
    through the application-level pre-check.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        CheckConstraint(
            "refunded_amount >= 0 AND refunded_amount <= amount",
            name="ck_payment_refunded_amount_range",
        ),
        # Idempotency keys are unique *per campus* — two independent tenants
        # may legitimately use the same client-supplied key.  (NULL keys are
        # distinct in PostgreSQL, so legacy rows without a key are unaffected.)
        UniqueConstraint(
            "campus_id", "idempotency_key",
            name="uq_payment_idempotency_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    fee_due_id: Mapped[int] = mapped_column(
        ForeignKey("fee_dues.id"), nullable=False
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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
    #: Client/gateway-supplied idempotency key for duplicate request handling.
    #: Unique per campus (see ``uq_payment_idempotency_key`` in table args).
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    #: Explicit payment state (completed / partially_refunded / refunded).
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed"
    )
    #: Cumulative amount refunded against this payment (minor units).
    refunded_amount: Mapped[int] = mapped_column(nullable=False, default=0)
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
            f"<Payment id={self.id} "
            f"student_id={self.student_id} "
            f"amount={self.amount}>"
        )