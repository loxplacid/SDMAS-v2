from __future__ import annotations

import datetime
import logging
from datetime import timezone
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.constants import (
    ACADEMIC,
    CREATE,
    FEE,
    PAYMENT,
    RECORD_PAYMENT,
    REFUND,
    UPDATE,
)
from app.domains.audit.service import AuditService
from app.domains.events.outbox import publish_durable
from app.domains.notifications.events import FeeDueCreatedEvent, PaymentReceivedEvent
from app.domains.school_finance.service import TransactionLogService

logger = logging.getLogger(__name__)
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    EnrollmentRepository,
)
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
    PaymentRepository,
)
from app.domains.fees.schemas import (
    VALID_FEE_DUE_STATUSES,
    VALID_FEE_STRUCTURE_STATUSES,
    VALID_FEE_TYPE_STATUSES,
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeTypeCreate,
    FeeTypeUpdate,
    PaymentCreate,
)
from app.domains.student.repository import StudentRepository

# ---------------------------------------------------------------------------
# FeeTypeService
# ---------------------------------------------------------------------------


class FeeTypeService:
    def __init__(self, repo: FeeTypeRepository) -> None:
        self.repo = repo

    async def create(self, data: FeeTypeCreate) -> FeeType:
        name = data.name.strip()
        existing = await self.repo.get_by_name(name)
        if existing is not None:
            raise ConflictError(f"Fee type '{name}' already exists")

        ft = FeeType(
            name=name,
            description=data.description,
            status="active",
        )
        return await self.repo.create(ft)

    async def get(self, type_id: int) -> FeeType:
        return await self.repo.get_by_id(type_id)

    async def update(self, type_id: int, data: FeeTypeUpdate) -> FeeType:
        ft = await self.repo.get_by_id(type_id)

        if data.name is not None:
            name = data.name.strip()
            if name != ft.name:
                existing = await self.repo.get_by_name(name)
                if existing is not None:
                    raise ConflictError(
                        f"Fee type '{name}' already exists"
                    )
            ft.name = name
        if data.description is not None:
            ft.description = data.description
        if data.status is not None:
            if data.status not in VALID_FEE_TYPE_STATUSES:
                raise ValidationError("Invalid fee type status")
            ft.status = data.status

        return await self.repo.update(ft)

    async def deactivate(self, type_id: int) -> FeeType:
        ft = await self.repo.get_by_id(type_id)
        ft.status = "inactive"
        return await self.repo.update(ft)

    async def list(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeType], int]:
        if status is not None and status not in VALID_FEE_TYPE_STATUSES:
            raise ValidationError("Invalid status filter for fee types")
        return await self.repo.list(status=status, campus_id=campus_id, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# FeeStructureService
# ---------------------------------------------------------------------------


class FeeStructureService:
    def __init__(
        self,
        repo: FeeStructureRepository,
        year_repo: AcademicYearRepository,
        class_repo: ClassRepository,
        fee_type_repo: FeeTypeRepository,
    ) -> None:
        self.repo = repo
        self.year_repo = year_repo
        self.class_repo = class_repo
        self.fee_type_repo = fee_type_repo

    async def create(self, data: FeeStructureCreate) -> FeeStructure:
        year = await self.year_repo.get_by_id(data.academic_year_id)
        if year.status != "active":
            raise ValidationError(
                "Cannot create fee structure for an inactive academic year"
            )

        cls = await self.class_repo.get_by_id(data.class_id)
        if cls.status != "active":
            raise ValidationError(
                "Cannot create fee structure for an inactive class"
            )

        ft = await self.fee_type_repo.get_by_id(data.fee_type_id)
        if ft.status != "active":
            raise ValidationError(
                "Cannot create fee structure for an inactive fee type"
            )

        existing = await self.repo.get_by_year_class_type(
            data.academic_year_id, data.class_id, data.fee_type_id
        )
        if existing is not None:
            raise ConflictError(
                "Fee structure already exists for this academic year, class, and fee type"
            )

        structure = FeeStructure(
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            fee_type_id=data.fee_type_id,
            amount=data.amount,
            frequency=data.frequency or "annual",
            status="active",
        )
        created = await self.repo.create(structure)

        # Audit: fee structure created
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                action=CREATE,
                resource_type=FEE,
                resource_id=str(created.id),
                details={
                    "academic_year_id": data.academic_year_id,
                    "class_id": data.class_id,
                    "fee_type_id": data.fee_type_id,
                    "amount": float(data.amount),
                    "frequency": data.frequency or "annual",
                },
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for fee structure creation (non-fatal)", exc_info=True)

        return created

    async def get(self, structure_id: int) -> FeeStructure:
        return await self.repo.get_by_id(structure_id)

    async def update(
        self, structure_id: int, data: FeeStructureUpdate
    ) -> FeeStructure:
        fs = await self.repo.get_by_id(structure_id)

        if data.academic_year_id is not None:
            year = await self.year_repo.get_by_id(data.academic_year_id)
            if year.status != "active":
                raise ValidationError(
                    "Cannot assign to an inactive academic year"
                )
            fs.academic_year_id = data.academic_year_id
        if data.class_id is not None:
            cls = await self.class_repo.get_by_id(data.class_id)
            if cls.status != "active":
                raise ValidationError(
                    "Cannot assign to an inactive class"
                )
            fs.class_id = data.class_id
        if data.fee_type_id is not None:
            ft = await self.fee_type_repo.get_by_id(data.fee_type_id)
            if ft.status != "active":
                raise ValidationError(
                    "Cannot assign to an inactive fee type"
                )
            fs.fee_type_id = data.fee_type_id
        if data.amount is not None:
            if data.amount <= 0:
                raise ValidationError(
                    "Fee amount must be a positive integer"
                )
            fs.amount = data.amount
        if data.frequency is not None:
            fs.frequency = data.frequency
        if data.status is not None:
            if data.status not in VALID_FEE_STRUCTURE_STATUSES:
                raise ValidationError("Invalid fee structure status")
            fs.status = data.status

        updated_fs = await self.repo.update(fs)

        # Audit: fee structure updated (only include actually-changed fields)
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                action=UPDATE,
                resource_type=FEE,
                resource_id=str(structure_id),
                details={k: v for k, v in {
                    "academic_year_id": data.academic_year_id,
                    "class_id": data.class_id,
                    "fee_type_id": data.fee_type_id,
                    "amount": float(data.amount) if data.amount is not None else None,
                    "frequency": data.frequency,
                    "status": data.status,
                }.items() if v is not None},
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for fee structure update (non-fatal)", exc_info=True)

        return updated_fs

    async def list(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        fee_type_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeStructure], int]:
        if status is not None and status not in VALID_FEE_STRUCTURE_STATUSES:
            raise ValidationError(
                "Invalid status filter for fee structures"
            )
        return await self.repo.list(
            academic_year_id=academic_year_id,
            class_id=class_id,
            fee_type_id=fee_type_id,
            status=status,
            campus_id=campus_id,
            skip=skip,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# FeeDueService
# ---------------------------------------------------------------------------


class FeeDueService:
    def __init__(
        self,
        repo: FeeDueRepository,
        student_repo: StudentRepository,
        year_repo: AcademicYearRepository,
        class_repo: ClassRepository,
        enrollment_repo: EnrollmentRepository,
        structure_repo: FeeStructureRepository,
        fee_type_repo: FeeTypeRepository,
    ) -> None:
        self.repo = repo
        self.student_repo = student_repo
        self.year_repo = year_repo
        self.class_repo = class_repo
        self.enrollment_repo = enrollment_repo
        self.structure_repo = structure_repo
        self.fee_type_repo = fee_type_repo

    async def create_dues(
        self, student_id: int, academic_year_id: int
    ) -> list[FeeDue]:
        student = await self.student_repo.get_by_id(student_id)
        if student.status != "active":
            raise ValidationError(
                "Cannot create fee dues for an inactive student"
            )

        year = await self.year_repo.get_by_id(academic_year_id)
        if year.status != "active":
            raise ValidationError(
                "Cannot create fee dues for an inactive academic year"
            )

        enrollment = await self.enrollment_repo.get_by_student_and_year(
            student_id, academic_year_id
        )
        if enrollment is None:
            raise ValidationError(
                f"Student {student_id} is not enrolled in academic year {academic_year_id}"
            )
        if enrollment.status != "active":
            raise ValidationError(
                "Cannot create fee dues for an inactive enrollment"
            )

        structures, _ = await self.structure_repo.list(
            academic_year_id=academic_year_id,
            class_id=enrollment.class_id,
            status="active",
            limit=10000,
        )

        if not structures:
            raise ValidationError(
                f"No active fee structures found for class {enrollment.class_id} in academic year {academic_year_id}"
            )

        structure_ids = [fs.id for fs in structures]

        existing_result = await self.repo.session.execute(
            select(FeeDue.fee_structure_id).where(
                FeeDue.student_id == student_id,
                FeeDue.fee_structure_id.in_(structure_ids),
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}
        for fs in structures:
            if fs.id in existing_ids:
                raise ConflictError(
                    f"Fee due already exists for student {student_id} and fee structure {fs.id}"
                )

        created_dues: list[FeeDue] = []
        now = datetime.datetime.now(timezone.utc)
        for fs in structures:
            due = FeeDue(
                student_id=student_id,
                academic_year_id=academic_year_id,
                fee_structure_id=fs.id,
                original_amount=fs.amount,
                amount_paid=0,
                due_date=None,
                status="unpaid",
                created_at=now,
                updated_at=now,
            )
            created = await self.repo.create(due)
            created_dues.append(created)

            # Fire event: fee dues created
        if created_dues:
            try:
                total_amount = sum(d.original_amount for d in created_dues)
                event = FeeDueCreatedEvent(
                    student_id=student_id,
                    academic_year_id=academic_year_id,
                    due_ids=[d.id for d in created_dues],
                    total_amount=float(total_amount),
                    due_count=len(created_dues),
                    tenant_id=getattr(created_dues[0], "campus_id", None),
                )
                # Durable event (transactional outbox): written atomically with
                # the fee-due insert, delivered by the worker process.
                await publish_durable(
                    event,
                    session=self.repo.session,
                    event_id=f"fee_due:{student_id}:{academic_year_id}",
                )
            except Exception:
                logger.warning("Failed to dispatch FeeDueCreatedEvent (non-fatal)", exc_info=True)

        return created_dues

    async def get(self, due_id: int) -> FeeDue:
        return await self.repo.get_by_id(due_id)

    async def list(
        self,
        student_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeDue], int]:
        return await self.repo.list(
            student_id=student_id,
            academic_year_id=academic_year_id,
            status=status,
            campus_id=campus_id,
            skip=skip,
            limit=limit,
        )

    async def get_student_dues(
        self,
        student_id: int,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Sequence[FeeDue]:
        return await self.repo.find_by_student(
            student_id,
            academic_year_id=academic_year_id,
            status=status,
        )

    async def get_student_fees(
        self, student_id: int, academic_year_id: int
    ) -> List[dict]:
        student = await self.student_repo.get_by_id(student_id)
        year = await self.year_repo.get_by_id(academic_year_id)

        enrollment = await self.enrollment_repo.get_by_student_and_year(
            student_id, academic_year_id
        )
        if enrollment is None:
            raise ValidationError(
                f"Student {student_id} is not enrolled in academic year {academic_year_id}"
            )

        structures, _ = await self.structure_repo.list(
            academic_year_id=academic_year_id,
            class_id=enrollment.class_id,
            status="active",
            limit=10000,
        )

        fee_type_ids = {fs.fee_type_id for fs in structures if fs.fee_type_id}
        fee_types = {}
        if fee_type_ids:
            ft_result = await self.repo.session.execute(
                select(FeeType).where(FeeType.id.in_(fee_type_ids))
            )
            fee_types = {ft.id: ft for ft in ft_result.scalars().all()}

        return [
            {
                "id": fs.id,
                "academic_year_id": fs.academic_year_id,
                "class_id": fs.class_id,
                "fee_type_id": fs.fee_type_id,
                "fee_type_name": fee_types[fs.fee_type_id].name if fs.fee_type_id in fee_types else "Unknown",
                "amount": fs.amount,
                "frequency": fs.frequency,
                "status": fs.status,
                "created_at": fs.created_at,
                "updated_at": fs.updated_at,
            }
            for fs in structures
        ]


# ---------------------------------------------------------------------------
# PaymentService
# ---------------------------------------------------------------------------


class PaymentService:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        fee_due_repo: FeeDueRepository,
        student_repo: StudentRepository,
    ) -> None:
        self.repo = payment_repo
        self.fee_due_repo = fee_due_repo
        self.student_repo = student_repo

    async def _payment_result(self, payment: Payment) -> dict:
        """Build the canonical ``PaymentResult``-shaped response for a payment."""
        fee_due = await self.fee_due_repo.get_by_id(payment.fee_due_id)
        return {
            "payment": payment,
            "fee_due": {
                "id": fee_due.id,
                "student_id": fee_due.student_id,
                "academic_year_id": fee_due.academic_year_id,
                "fee_structure_id": fee_due.fee_structure_id,
                "original_amount": fee_due.original_amount,
                "amount_paid": fee_due.amount_paid,
                "campus_id": fee_due.campus_id,
                "due_date": fee_due.due_date,
                "status": fee_due.status,
                "created_at": fee_due.created_at,
                "updated_at": fee_due.updated_at,
            },
        }

    async def record_payment(
        self,
        data: PaymentCreate,
        actor: Optional["AuditActor"] = None,
    ) -> dict:
        # ── Idempotency: a repeated request with the same logical key must
        # never create a second financial record.  The key is unique at the
        # DB layer, so even a concurrent duplicate cannot slip through.
        if data.idempotency_key:
            existing = await self.repo.get_by_idempotency_key(
                data.idempotency_key
            )
            if existing is not None:
                return await self._payment_result(existing)

        student = await self.student_repo.get_by_id(data.student_id)
        if student.status != "active":
            raise ValidationError(
                "Cannot record payment for an inactive student"
            )

        fee_due = await self.fee_due_repo.get_by_id_for_update(data.fee_due_id)
        if fee_due.student_id != data.student_id:
            raise ValidationError(
                "Fee due does not belong to the specified student"
            )
        if fee_due.status == "paid":
            raise ConflictError("Fee due is already fully paid")

        if data.receipt_number:
            existing = await self.repo.get_by_receipt_number(
                data.receipt_number
            )
            if existing is not None:
                raise ConflictError(
                    f"Payment with receipt number {data.receipt_number} already exists"
                )

        new_amount_paid = fee_due.amount_paid + data.amount
        if new_amount_paid > fee_due.original_amount:
            raise ValidationError(
                "Payment would exceed outstanding balance"
            )

        new_status = (
            "paid"
            if new_amount_paid >= fee_due.original_amount
            else "partially_paid"
        )
        now = datetime.datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%d")

        # ── Write path in a savepoint.  If a concurrent request commits the
        # same idempotency key (or same receipt number) first, the unique
        # constraint fires and we reconcile instead of double-booking.
        try:
            async with self.repo.session.begin_nested():
                payment = Payment(
                    student_id=data.student_id,
                    fee_due_id=data.fee_due_id,
                    campus_id=fee_due.campus_id,
                    amount=data.amount,
                    payment_date=data.payment_date or now_str,
                    payment_method=data.payment_method,
                    receipt_number=data.receipt_number,
                    idempotency_key=data.idempotency_key,
                    status="completed",
                    refunded_amount=0,
                    created_at=now,
                    updated_at=now,
                )
                saved = await self.repo.create(payment)

                fee_due.amount_paid = new_amount_paid
                fee_due.status = new_status
                fee_due.updated_at = now
                await self.fee_due_repo.update(fee_due)

                # Journal the payment in the immutable transaction ledger so
                # the running student balance stays consistent and auditable.
                recorded_by = self._actor_user_id(actor)
                tx_log_svc = TransactionLogService(self.repo.session)
                await tx_log_svc.record(
                    transaction_type="payment",
                    student_id=data.student_id,
                    amount=data.amount,
                    payment_id=saved.id,
                    fee_due_id=data.fee_due_id,
                    reference_number=data.receipt_number,
                    idempotency_key=f"payment:{saved.id}",
                    description=f"Fee payment recorded for fee due {data.fee_due_id}",
                    campus_id=fee_due.campus_id,
                    recorded_by=recorded_by,
                )

                # Audit: payment recorded (shares this transaction).
                audit_svc = AuditService(self.repo.session)
                await audit_svc.record(
                    action=RECORD_PAYMENT,
                    resource_type=PAYMENT,
                    resource_id=str(saved.id),
                    actor=actor,
                    details={
                        "student_id": data.student_id,
                        "fee_due_id": data.fee_due_id,
                        "amount": data.amount,
                        "payment_method": data.payment_method,
                        "receipt_number": data.receipt_number,
                        "idempotency_key": data.idempotency_key,
                        "fee_due_status_after": new_status,
                    },
                )

                # Fire event: payment received (durable, best-effort publish).
                try:
                    event = PaymentReceivedEvent(
                        student_id=data.student_id,
                        fee_due_id=data.fee_due_id,
                        payment_id=saved.id,
                        amount=float(data.amount),
                        payment_method=data.payment_method,
                        receipt_number=data.receipt_number,
                        new_due_status=new_status,
                        tenant_id=fee_due.campus_id,
                    )
                    await publish_durable(
                        event,
                        session=self.repo.session,
                        event_id=f"payment:{saved.id}",
                        school_id=fee_due.campus_id,
                    )
                except Exception:
                    logger.warning(
                        "Failed to dispatch PaymentReceivedEvent (non-fatal)", exc_info=True
                    )

                return await self._payment_result(saved)
        except IntegrityError as exc:
            # A concurrent duplicate won the race (unique idempotency key or
            # receipt number, or the fee-due amount-range constraint).  For an
            # idempotent caller the right answer is the already-created record;
            # otherwise the request cannot be honoured twice.
            if data.idempotency_key:
                existing = await self.repo.get_by_idempotency_key(
                    data.idempotency_key
                )
                if existing is not None:
                    return await self._payment_result(existing)
            raise ConflictError(
                "Payment could not be recorded - a conflicting payment was "
                "already processed for this request."
            ) from exc

    def _actor_user_id(self, actor: Optional["AuditActor"]) -> Optional[int]:
        """Return the underlying user id when ``actor`` is an authenticated
        human (USER/PLATFORM), else ``None``."""
        if actor is None:
            return None
        if actor.actor_type in (ActorType.USER, ActorType.PLATFORM):
            try:
                return int(actor.actor_id)
            except (TypeError, ValueError):
                return None
        return None

    async def record_refund(
        self,
        payment_id: int,
        amount: int,
        reason: Optional[str] = None,
        actor: Optional["AuditActor"] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Refund part or all of a recorded payment.

        The refund is an explicit state transition on the *payment*
        (``completed -> partially_refunded -> refunded``) and it reverses
        the paid balance on the originating fee due.  All mutations share a
        single database transaction (savepoint), so a refund can never
        partially apply.  The refund is journaled in the transaction ledger
        and audited with the acting user.

        ``idempotency_key`` (optional) makes the *request* idempotent: a
        retried or double-submitted refund for the same payment resolves to
        the first result instead of refunding a second time.  The key is
        recorded on the refund's ledger row (the ledger is the idempotency
        store, mirroring how payments journal ``payment:{id}``).
        """
        # Lock the payment row first: two concurrent refunds on the same
        # payment must serialize, and the refundable balance must be
        # re-read *after* the lock so a stale ``refunded_amount`` can never
        # let a refund apply twice.
        payment = await self.repo.get_by_id_for_update(payment_id)

        # The ledger is the refund idempotency store; one instance is shared
        # by the dedupe check, the journal write, and the race recovery below.
        tx_log_svc = TransactionLogService(self.repo.session)

        # Idempotent replay: an earlier refund carrying this key already
        # journaled the effect — return that result rather than refunding
        # again.  The key is scoped to the payment (a key minted for a
        # different payment is a conflict, not a replay).
        if idempotency_key:
            existing_tx = await tx_log_svc.find_by_idempotency_key(
                idempotency_key, campus_id=payment.campus_id
            )
            if existing_tx is not None:
                if existing_tx.payment_id != payment.id:
                    raise ConflictError(
                        f"Idempotency key {idempotency_key} was already used "
                        "for a different payment"
                    )
                return await self._payment_result(payment)

        if payment.status == "refunded":
            raise ConflictError(f"Payment {payment_id} is already fully refunded")

        refundable = payment.amount - payment.refunded_amount
        if amount > refundable:
            raise ValidationError(
                f"Refund amount {amount} exceeds the refundable balance {refundable}"
            )

        fee_due = await self.fee_due_repo.get_by_id_for_update(payment.fee_due_id)
        if fee_due.student_id != payment.student_id:
            raise ValidationError(
                "Payment's fee due does not belong to the payment's student"
            )

        now = datetime.datetime.now(timezone.utc)

        try:
            async with self.repo.session.begin_nested():
                new_refunded = payment.refunded_amount + amount
                payment.refunded_amount = new_refunded
                payment.status = (
                    "refunded" if new_refunded >= payment.amount else "partially_refunded"
                )
                payment.updated_at = now

                new_amount_paid = fee_due.amount_paid - amount
                if new_amount_paid < 0:
                    # Defensive: the payment lock serialises refunds, so a
                    # negative balance is impossible; fail loudly if the
                    # invariant is ever violated instead of silently
                    # clamping (which would hide an over-refund).
                    raise ConflictError(
                        f"Refund for payment {payment_id} would push the fee "
                        "due balance below zero."
                    )
                fee_due.amount_paid = new_amount_paid
                if fee_due.amount_paid == 0:
                    fee_due.status = "unpaid"
                elif fee_due.amount_paid >= fee_due.original_amount:
                    fee_due.status = "paid"
                else:
                    fee_due.status = "partially_paid"
                fee_due.updated_at = now

                # Journal the refund in the immutable transaction ledger.
                recorded_by = self._actor_user_id(actor)
                await tx_log_svc.record(
                    transaction_type="refund",
                    student_id=payment.student_id,
                    amount=amount,
                    payment_id=payment.id,
                    fee_due_id=payment.fee_due_id,
                    reference_number=payment.receipt_number,
                    # The client idempotency key is the retry signal; the
                    # default is a deterministic per-refund key.
                    idempotency_key=(
                        idempotency_key
                        or f"refund:{payment.id}:{new_refunded}"
                    ),
                    description=reason or f"Refund for payment {payment.id}",
                    campus_id=fee_due.campus_id,
                    recorded_by=recorded_by,
                )

                # Audit: refund recorded (shares this transaction).
                audit_svc = AuditService(self.repo.session)
                await audit_svc.record(
                    action=REFUND,
                    resource_type=PAYMENT,
                    resource_id=str(payment.id),
                    actor=actor,
                    details={
                        "amount": amount,
                        "reason": reason,
                        "payment_status_after": payment.status,
                        "refunded_amount_after": payment.refunded_amount,
                        "fee_due_status_after": fee_due.status,
                    },
                )

                return await self._payment_result(payment)
        except IntegrityError as exc:
            # A concurrent duplicate won the race on the ledger's unique
            # (campus_id, idempotency_key) constraint — for an idempotent
            # caller the answer is the already-journaled refund.  The
            # savepoint rollback restored this session's payment object to
            # its pre-winner-commit state, so refresh before reporting it.
            if idempotency_key:
                existing_tx = await tx_log_svc.find_by_idempotency_key(
                    idempotency_key, campus_id=payment.campus_id
                )
                if existing_tx is not None and existing_tx.payment_id == payment.id:
                    await self.repo.session.refresh(payment)
                    return await self._payment_result(payment)
            raise ConflictError(
                f"Refund for payment {payment_id} could not be applied."
            ) from exc

    async def get_payment(self, payment_id: int) -> Payment:
        return await self.repo.get_by_id(payment_id)

    async def get_student_payments(
        self, student_id: int
    ) -> Sequence[Payment]:
        return await self.repo.find_by_student(student_id)

    async def get_fee_due_payments(
        self, fee_due_id: int
    ) -> Sequence[Payment]:
        return await self.repo.find_by_fee_due(fee_due_id)

    async def get_payments_by_date_range(
        self,
        start_date: str,
        end_date: str,
        campus_id: Optional[int] = None,
    ) -> Sequence[Payment]:
        return await self.repo.find_by_date_range(
            start_date, end_date, campus_id=campus_id
        )

    async def get_payment_by_receipt_number(
        self, receipt_number: str
    ) -> Payment:
        payment = await self.repo.get_by_receipt_number(receipt_number)
        if payment is None:
            raise NotFoundError(
                f"Payment with receipt number {receipt_number} not found"
            )
        return payment


# ---------------------------------------------------------------------------
# SummaryService
# ---------------------------------------------------------------------------


class SummaryService:
    def __init__(
        self,
        fee_due_repo: FeeDueRepository,
        enrollment_repo: EnrollmentRepository,
    ) -> None:
        self.fee_due_repo = fee_due_repo
        self.enrollment_repo = enrollment_repo

    async def get_student_summary(
        self, student_id: int, academic_year_id: int
    ) -> dict:
        dues = await self.fee_due_repo.find_by_student(
            student_id, academic_year_id=academic_year_id
        )

        summary = {
            "student_id": student_id,
            "academic_year_id": academic_year_id,
            "total_fees_assigned": 0,
            "total_paid": 0,
            "total_outstanding": 0,
            "unpaid_count": 0,
            "partially_paid_count": 0,
            "paid_count": 0,
        }

        for due in dues:
            summary["total_fees_assigned"] += due.original_amount
            summary["total_paid"] += due.amount_paid
            if due.status == "unpaid":
                summary["unpaid_count"] += 1
            elif due.status == "partially_paid":
                summary["partially_paid_count"] += 1
            elif due.status == "paid":
                summary["paid_count"] += 1

        summary["total_outstanding"] = (
            summary["total_fees_assigned"] - summary["total_paid"]
        )

        return summary

    async def get_class_summary(
        self, class_id: int, academic_year_id: int
    ) -> dict:
        enrollments, _ = await self.enrollment_repo.list(
            academic_year_id=academic_year_id, limit=10000
        )
        class_enrollments = [e for e in enrollments if e.class_id == class_id]
        student_ids = {e.student_id for e in class_enrollments}

        all_dues = await self.fee_due_repo.find_by_academic_year(
            academic_year_id
        )
        class_dues = [
            d for d in all_dues if d.student_id in student_ids
        ]

        summary = {
            "class_id": class_id,
            "academic_year_id": academic_year_id,
            "total_students": len(student_ids),
            "total_fees_assigned": 0,
            "total_collected": 0,
            "total_outstanding": 0,
            "students_with_outstanding": 0,
        }

        outstanding_students: set[int] = set()
        for due in class_dues:
            summary["total_fees_assigned"] += due.original_amount
            summary["total_collected"] += due.amount_paid
            if due.amount_paid < due.original_amount:
                outstanding_students.add(due.student_id)

        summary["total_outstanding"] = (
            summary["total_fees_assigned"] - summary["total_collected"]
        )
        summary["students_with_outstanding"] = len(outstanding_students)

        return summary