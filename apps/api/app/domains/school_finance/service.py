from __future__ import annotations

import csv
import datetime
import html
import io
import logging
import uuid
from collections import defaultdict
from datetime import date, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import Integer, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.school_finance.models import (
    FeeSchedule,
    FinanceReport,
    PaymentMethod,
    PaymentReconciliation,
    Receipt,
    ReconciliationItem,
    TransactionLog,
)
from app.domains.school_finance.schemas import (
    FeeScheduleCreate,
    FeeScheduleUpdate,
    FinanceReportGenerate,
    PaymentMethodCreate,
    PaymentMethodUpdate,
    ReconciliationCreate,
    ReceiptGenerate,
    VALID_TRANSACTION_TYPES,
)

logger = logging.getLogger(__name__)

# ── Ledger classification (single source of truth) ──────────────────────
# The running balance chain (``record``) and the recomputed balance
# (``get_student_balance``) MUST agree on the sign of every transaction
# type.  A type counted by one but not the other silently drifts the
# ledger apart, so both consume these constants.
#
# Terminology follows the codebase's existing convention: a "debit" is
# money received from the student (increases the running balance) and a
# "credit" is money returned / credited (decreases it).  The sign of the
# currently-unused types (``fine``, ``reversal``, ``adjustment``) is a
# deliberate choice — the hard invariant is ``chain == recomputed sum``,
# not any particular sign.

#: Money received from the student — increases the running balance.
LEDGER_DEBIT_TYPES = frozenset({"payment", "fine"})

#: Money returned / credited to the student — decreases the running balance.
LEDGER_CREDIT_TYPES = frozenset({"refund", "waiver", "discount", "reversal", "adjustment"})


# ═══════════════════════════════════════════════════════════════════════
# Payment Method Service
# ═══════════════════════════════════════════════════════════════════════


class PaymentMethodService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: PaymentMethodCreate) -> PaymentMethod:
        existing = await self._find_by_code(data.code)
        if existing:
            raise ConflictError(f"Payment method with code '{data.code}' already exists")
        pm = PaymentMethod(**data.model_dump())
        self.session.add(pm)
        await self.session.flush()
        return pm

    async def get(self, pm_id: int) -> PaymentMethod:
        result = await self.session.execute(
            select(PaymentMethod).where(PaymentMethod.id == pm_id)
        )
        pm = result.scalar_one_or_none()
        if pm is None:
            raise NotFoundError(f"Payment method {pm_id} not found")
        return pm

    async def list(
        self,
        is_active: Optional[bool] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PaymentMethod], int]:
        conditions = []
        if is_active is not None:
            conditions.append(PaymentMethod.is_active == is_active)
        if campus_id is not None:
            conditions.append(PaymentMethod.campus_id == campus_id)

        cnt = select(func.count(PaymentMethod.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(PaymentMethod)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(PaymentMethod.name)
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def update(self, pm_id: int, data: PaymentMethodUpdate) -> PaymentMethod:
        pm = await self.get(pm_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pm, field, value)
        pm.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return pm

    async def delete(self, pm_id: int) -> None:
        pm = await self.get(pm_id)
        await self.session.delete(pm)
        await self.session.flush()

    async def _find_by_code(self, code: str) -> PaymentMethod | None:
        result = await self.session.execute(
            select(PaymentMethod).where(PaymentMethod.code == code)
        )
        return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════
# Fee Schedule Service
# ═══════════════════════════════════════════════════════════════════════


class FeeScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: FeeScheduleCreate) -> FeeSchedule:
        existing = await self._find_by_structure_and_installment(
            data.fee_structure_id, data.installment_number
        )
        if existing:
            raise ConflictError(
                f"Installment {data.installment_number} already exists for "
                f"fee structure {data.fee_structure_id}"
            )
        schedule = FeeSchedule(**data.model_dump())
        self.session.add(schedule)
        await self.session.flush()
        return schedule

    async def get(self, schedule_id: int) -> FeeSchedule:
        result = await self.session.execute(
            select(FeeSchedule).where(FeeSchedule.id == schedule_id)
        )
        s = result.scalar_one_or_none()
        if s is None:
            raise NotFoundError(f"Fee schedule {schedule_id} not found")
        return s

    async def list(
        self,
        fee_structure_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeSchedule], int]:
        conditions = []
        if fee_structure_id is not None:
            conditions.append(FeeSchedule.fee_structure_id == fee_structure_id)
        if status_filter is not None:
            conditions.append(FeeSchedule.status == status_filter)
        if campus_id is not None:
            conditions.append(FeeSchedule.campus_id == campus_id)

        cnt = select(func.count(FeeSchedule.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(FeeSchedule)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(
            FeeSchedule.fee_structure_id, FeeSchedule.installment_number
        )
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def update(self, schedule_id: int, data: FeeScheduleUpdate) -> FeeSchedule:
        s = await self.get(schedule_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(s, field, value)
        s.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return s

    async def delete(self, schedule_id: int) -> None:
        s = await self.get(schedule_id)
        await self.session.delete(s)
        await self.session.flush()

    async def get_by_fee_structure(
        self, fee_structure_id: int
    ) -> Sequence[FeeSchedule]:
        result = await self.session.execute(
            select(FeeSchedule)
            .where(FeeSchedule.fee_structure_id == fee_structure_id)
            .order_by(FeeSchedule.installment_number)
        )
        return result.scalars().all()

    async def _find_by_structure_and_installment(
        self, fee_structure_id: int, installment_number: int
    ) -> FeeSchedule | None:
        result = await self.session.execute(
            select(FeeSchedule).where(
                FeeSchedule.fee_structure_id == fee_structure_id,
                FeeSchedule.installment_number == installment_number,
            )
        )
        return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════
# Transaction Log Service
# ═══════════════════════════════════════════════════════════════════════


class TransactionLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        transaction_type: str,
        student_id: int,
        amount: int,
        payment_id: Optional[int] = None,
        fee_due_id: Optional[int] = None,
        balance_before: int = 0,
        reference_number: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        description: Optional[str] = None,
        campus_id: Optional[int] = None,
        recorded_by: Optional[int] = None,
    ) -> TransactionLog:
        if idempotency_key:
            existing = await self.find_by_idempotency_key(
                idempotency_key, campus_id=campus_id
            )
            if existing:
                return existing

        # Service-layer validation: the ledger is immutable and written by
        # services and jobs as well as by validated router schemas — a
        # direct caller must not be able to journal garbage.
        if transaction_type not in VALID_TRANSACTION_TYPES:
            raise ValidationError(
                f"Invalid transaction type '{transaction_type}'"
            )
        if amount <= 0:
            raise ValidationError(
                "Transaction amount must be a positive integer"
            )

        # Per-student serialization: concurrent payments/refunds for the
        # same student must not both read the same pre-transaction balance
        # (running-balance drift).  The student row is the serialization
        # point — PostgreSQL honours the row lock, and the recomputed sum
        # below keeps every row truthful even where locks are not enforced.
        # LOCK ORDERING: this is intentionally the LAST lock acquired in a
        # student's money flow (the fees service already holds the fee-due /
        # payment row locks).  Never acquire a fee-due or payment lock after
        # this one — that would invert the order and deadlock.
        from app.domains.student.models import Student
        await self.session.execute(
            select(Student.id)
            .where(Student.id == student_id)
            .with_for_update()
        )

        # Opening balance comes from the authoritative recomputed sum, so a
        # drifted or legacy chain can never corrupt the next row.
        if not balance_before:
            balance_before = await self.get_student_balance(
                student_id, campus_id
            )
        is_credit = transaction_type in LEDGER_CREDIT_TYPES
        balance_after = balance_before - amount if is_credit else balance_before + amount

        log = TransactionLog(
            transaction_type=transaction_type,
            payment_id=payment_id,
            fee_due_id=fee_due_id,
            student_id=student_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_number=reference_number,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
            description=description,
            campus_id=campus_id,
            recorded_by=recorded_by,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def find_by_idempotency_key(
        self, key: str, campus_id: Optional[int] = None
    ) -> TransactionLog | None:
        """Find a prior transaction log by idempotency key.

        Scoped to ``campus_id`` when provided: a key supplied by one
        tenant must never resolve to another tenant's ledger record.
        """
        query = select(TransactionLog).where(
            TransactionLog.idempotency_key == key
        )
        if campus_id is not None:
            query = query.where(TransactionLog.campus_id == campus_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get(self, log_id: int) -> TransactionLog:
        result = await self.session.execute(
            select(TransactionLog).where(TransactionLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        if log is None:
            raise NotFoundError(f"Transaction log {log_id} not found")
        return log

    async def list(
        self,
        student_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        payment_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        min_amount: Optional[int] = None,
        max_amount: Optional[int] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[TransactionLog], int]:
        conditions = []
        if student_id is not None:
            conditions.append(TransactionLog.student_id == student_id)
        if transaction_type is not None:
            conditions.append(TransactionLog.transaction_type == transaction_type)
        if payment_id is not None:
            conditions.append(TransactionLog.payment_id == payment_id)
        if campus_id is not None:
            conditions.append(TransactionLog.campus_id == campus_id)
        if from_date is not None:
            conditions.append(TransactionLog.created_at >= from_date)
        if to_date is not None:
            conditions.append(TransactionLog.created_at <= to_date)
        if min_amount is not None:
            conditions.append(TransactionLog.amount >= min_amount)
        if max_amount is not None:
            conditions.append(TransactionLog.amount <= max_amount)
        # P13 — free-text search over the ledger (reference number, description,
        # idempotency key) plus a direct student-id lookup for `#123` queries.
        if q:
            needle = q.strip()
            if needle:
                numeric_student = None
                if needle.isdigit():
                    try:
                        numeric_student = int(needle)
                    except ValueError:
                        # absurdly long all-digit input — treat as text only
                        numeric_student = None
                like_terms = [
                    TransactionLog.reference_number.ilike(f"%{needle}%"),
                    TransactionLog.description.ilike(f"%{needle}%"),
                    TransactionLog.idempotency_key.ilike(f"%{needle}%"),
                ]
                if numeric_student is not None:
                    conditions.append(
                        or_(TransactionLog.student_id == numeric_student, *like_terms)
                    )
                else:
                    conditions.append(or_(*like_terms))

        cnt = select(func.count(TransactionLog.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(TransactionLog)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(TransactionLog.created_at.desc())
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def export_transactions_csv(
        self,
        student_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        payment_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        min_amount: Optional[int] = None,
        max_amount: Optional[int] = None,
        q: Optional[str] = None,
    ) -> str:
        """CSV dump of the ledger rows matching the same filters as ``list``.

        Uses the same condition-building as ``list`` (including the P13
        free-text search) but without pagination, so a finance user can
        export the full matching ledger for reconciliation.
        """
        conditions = []
        if student_id is not None:
            conditions.append(TransactionLog.student_id == student_id)
        if transaction_type is not None:
            conditions.append(TransactionLog.transaction_type == transaction_type)
        if payment_id is not None:
            conditions.append(TransactionLog.payment_id == payment_id)
        if campus_id is not None:
            conditions.append(TransactionLog.campus_id == campus_id)
        if from_date is not None:
            conditions.append(TransactionLog.created_at >= from_date)
        if to_date is not None:
            conditions.append(TransactionLog.created_at <= to_date)
        if min_amount is not None:
            conditions.append(TransactionLog.amount >= min_amount)
        if max_amount is not None:
            conditions.append(TransactionLog.amount <= max_amount)
        if q:
            needle = q.strip()
            if needle:
                numeric_student = None
                if needle.isdigit():
                    try:
                        numeric_student = int(needle)
                    except ValueError:
                        numeric_student = None
                like_terms = [
                    TransactionLog.reference_number.ilike(f"%{needle}%"),
                    TransactionLog.description.ilike(f"%{needle}%"),
                    TransactionLog.idempotency_key.ilike(f"%{needle}%"),
                ]
                if numeric_student is not None:
                    conditions.append(
                        or_(TransactionLog.student_id == numeric_student, *like_terms)
                    )
                else:
                    conditions.append(or_(*like_terms))

        q = select(TransactionLog)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.order_by(TransactionLog.created_at.desc())
        result = await self.session.execute(q)
        logs = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Date", "Type", "Student ID", "Payment ID", "Amount (cents)",
            "Balance After (cents)", "Reference", "Description", "Idempotency Key",
        ])
        for log in logs:
            writer.writerow([
                log.id,
                log.created_at.isoformat() if log.created_at else "",
                log.transaction_type,
                log.student_id,
                log.payment_id or "",
                log.amount,
                log.balance_after if log.balance_after is not None else "",
                log.reference_number or "",
                log.description or "",
                log.idempotency_key or "",
            ])
        return output.getvalue()

    async def get_student_balance(
        self, student_id: int, campus_id: Optional[int] = None
    ) -> int:
        credits_q = select(func.coalesce(func.sum(TransactionLog.amount), 0)).where(
            TransactionLog.student_id == student_id,
            TransactionLog.transaction_type.in_(LEDGER_DEBIT_TYPES),
        )
        if campus_id is not None:
            credits_q = credits_q.where(TransactionLog.campus_id == campus_id)
        logs = await self.session.execute(credits_q)
        credits = logs.scalar() or 0

        debits_q = select(func.coalesce(func.sum(TransactionLog.amount), 0)).where(
            TransactionLog.student_id == student_id,
            TransactionLog.transaction_type.in_(LEDGER_CREDIT_TYPES),
        )
        if campus_id is not None:
            debits_q = debits_q.where(TransactionLog.campus_id == campus_id)
        debits = await self.session.execute(debits_q)
        return credits - (debits.scalar() or 0)

    # NOTE: the previous ``_get_last_balance`` (last-row read without any
    # per-student serialization) was removed — the running balance is now
    # always derived from the authoritative recomputed sum in ``record``,
    # so a stale last row can never corrupt the next ledger entry.


# ═══════════════════════════════════════════════════════════════════════
# Payment Reconciliation Service
# ═══════════════════════════════════════════════════════════════════════


class ReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        data: ReconciliationCreate,
        reconciled_by: int,
        campus_id: Optional[int] = None,
    ) -> PaymentReconciliation:
        """Create a draft reconciliation.

        ``campus_id`` is the *authoritative* tenant scope supplied by the
        router (from ``effective_campus_id``); it overrides any value the
        client put in the payload so a reconciliation can never be tagged
        with a campus the caller does not belong to.  Every item's payment
        must belong to that same campus.
        """
        rec_campus = campus_id if campus_id is not None else data.campus_id
        rec = PaymentReconciliation(
            reconciliation_date=data.reconciliation_date,
            total_amount=data.total_amount,
            total_count=data.total_count,
            status="draft",
            notes=data.notes,
            campus_id=rec_campus,
            reconciled_by=reconciled_by,
        )
        self.session.add(rec)
        await self.session.flush()

        for item_data in data.items:
            payment = await self._validate_payment(
                item_data.payment_id, campus_id=rec_campus
            )
            diff = item_data.expected_amount - item_data.actual_amount
            item = ReconciliationItem(
                reconciliation_id=rec.id,
                payment_id=item_data.payment_id,
                expected_amount=item_data.expected_amount,
                actual_amount=item_data.actual_amount,
                difference=diff,
                status="matched" if diff == 0 else "discrepancy",
                notes=item_data.notes,
            )
            self.session.add(item)

        await self.session.flush()

        result = await self.session.execute(
            select(PaymentReconciliation)
            .where(PaymentReconciliation.id == rec.id)
            .options(joinedload(PaymentReconciliation.items))
        )
        # ``joinedload`` on a collection requires ``unique()`` before
        # extracting a single scalar.
        return result.scalars().unique().one()

    async def get(self, rec_id: int) -> PaymentReconciliation:
        result = await self.session.execute(
            select(PaymentReconciliation)
            .where(PaymentReconciliation.id == rec_id)
            .options(joinedload(PaymentReconciliation.items))
        )
        rec = result.scalar_one_or_none()
        if rec is None:
            raise NotFoundError(f"Reconciliation {rec_id} not found")
        return rec

    async def list(
        self,
        status_filter: Optional[str] = None,
        campus_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        q: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PaymentReconciliation], int]:
        conditions = []
        if status_filter is not None:
            conditions.append(PaymentReconciliation.status == status_filter)
        if campus_id is not None:
            conditions.append(PaymentReconciliation.campus_id == campus_id)
        if from_date is not None:
            conditions.append(PaymentReconciliation.reconciliation_date >= from_date)
        if to_date is not None:
            conditions.append(PaymentReconciliation.reconciliation_date <= to_date)
        # P13 — free-text search over the reconciliation notes (and a direct
        # id lookup for `#123` queries), mirroring the transactions `q`.
        if q is not None and q.strip():
            like = f"%{q.strip()}%"
            try:
                num = int(q.strip())
            except ValueError:
                num = 0
            conditions.append(
                or_(
                    PaymentReconciliation.notes.ilike(like),
                    PaymentReconciliation.id == num,
                )
            )

        cnt = select(func.count(PaymentReconciliation.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(PaymentReconciliation).options(joinedload(PaymentReconciliation.items))
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(PaymentReconciliation.reconciliation_date.desc())
        result = await self.session.execute(q)
        # .unique(): the query joinedloads the items collection, so a result
        # spanning several parent rows needs row-identity dedup before
        # iteration — without it scalars() raises on the second row.
        items = list({r.id: r for r in result.scalars().unique().all()}.values())
        return items[:limit], total

    async def verify(
        self,
        rec_id: int,
        reviewed_by: int,
        actor: Optional["AuditActor"] = None,
    ) -> PaymentReconciliation:
        rec = await self.get(rec_id)
        if rec.status != "draft":
            raise ValidationError(f"Reconciliation {rec_id} is already {rec.status}")
        rec.status = "verified"
        rec.verified_by = reviewed_by
        rec.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self._audit_review("VERIFY", rec, actor)
        await self.session.flush()
        return rec

    async def approve(
        self,
        rec_id: int,
        reviewed_by: int,
        actor: Optional["AuditActor"] = None,
    ) -> PaymentReconciliation:
        rec = await self.get(rec_id)
        if rec.status not in ("draft", "verified"):
            raise ValidationError(f"Reconciliation {rec_id} cannot be approved from status {rec.status}")
        rec.status = "approved"
        rec.approved_by = reviewed_by
        rec.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self._audit_review("APPROVE", rec, actor)
        await self.session.flush()
        return rec

    async def _audit_review(
        self,
        action: str,
        rec: PaymentReconciliation,
        actor: Optional["AuditActor"],
    ) -> None:
        """Record a VERIFY / APPROVE audit entry for a reconciliation
        review (best-effort, shares the caller's transaction)."""
        try:
            from app.domains.audit.service import AuditService

            audit_svc = AuditService(self.session)
            await audit_svc.record(
                action=action,
                resource_type="reconciliation",
                resource_id=str(rec.id),
                actor=actor,
                details={
                    "rec_id": rec.id,
                    "status_after": rec.status,
                    "reconciled_by": rec.reconciled_by,
                },
            )
        except Exception:
            logger.warning(
                "Failed to write audit entry for reconciliation %s (non-fatal)", action,
                exc_info=True,
            )

    async def _validate_payment(self, payment_id: int, campus_id: Optional[int] = None):
        from app.domains.fees.models import Payment
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            raise NotFoundError(f"Payment {payment_id} not found")
        # A reconciliation must never reference a payment from another
        # campus (legacy NULL-campus payments remain accepted).
        if campus_id is not None and payment.campus_id not in (None, campus_id):
            raise ValidationError(
                f"Payment {payment_id} does not belong to campus {campus_id}"
            )
        return payment


# ═══════════════════════════════════════════════════════════════════════
# Financial Exception Service (P13)
# ═══════════════════════════════════════════════════════════════════════


class FinancialExceptionService:
    """P13 — deterministic financial anomaly detection (read-only).

    Findings are computed from real records on every read — nothing is
    stored, so there is no drift between the ledger and what operators see.
    Each finding carries a stable ``key`` (category + entity id); promoting
    it into a P8/P11 operational case references the underlying entity via
    ``source_type=financial_exception`` / ``source_id`` (the case service
    validates the reference).

    Detection rules (each grounded in existing record state):

    * ``reconciliation-discrepancy`` — reconciliation items left unmatched
      or with a non-zero difference (the reconciliation workflow's own
      state);
    * ``payment-no-receipt`` — payments with no generated receipt (receipts
      are generated per payment, so a missing one is actionable);
    * ``payment-no-transaction`` — payments with no transaction-log entry
      (money recorded without a ledger entry is a data-integrity signal);
    * ``duplicate-payment`` — the same student + amount + date more than
      once (a review heuristic, never an accusation).

    Per-category scans are bounded (top 500 rows each); the summary counts
    come from the same bounded result, which is appropriate for an
    operational surface that always sorts by severity first.
    """

    SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    PER_CATEGORY_LIMIT = 500

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_exceptions(
        self,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        findings = await self._detect_all(campus_id)

        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for f in findings:
            by_category[f["category"]] = by_category.get(f["category"], 0) + 1
            by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1

        # Operational ordering: highest severity first, then most recent.
        epoch_zero = datetime.datetime.min.replace(tzinfo=timezone.utc)
        findings.sort(
            key=lambda f: (
                self.SEVERITY_RANK.get(f["severity"], 9),
                -((f["created_at"] or epoch_zero).timestamp()),
            )
        )

        return {
            "total": len(findings),
            "by_category": by_category,
            "by_severity": by_severity,
            "items": findings[skip : skip + limit],
        }

    async def _detect_all(self, campus_id: Optional[int]) -> list[dict]:
        from app.domains.fees.models import Payment
        from app.domains.student.models import Student

        findings: list[dict] = []
        # Legacy NULL-campus payments remain in scope, matching the existing
        # receipt/reconciliation semantics.
        payment_scope = None
        if campus_id is not None:
            payment_scope = or_(
                Payment.campus_id == campus_id, Payment.campus_id.is_(None)
            )

        # 1. reconciliation discrepancies / unmatched items
        rec_conds = [ReconciliationItem.status.in_(["unmatched", "discrepancy"])]
        if campus_id is not None:
            rec_conds.append(PaymentReconciliation.campus_id == campus_id)
        rec_rows = (
            await self.session.execute(
                select(
                    ReconciliationItem.id,
                    ReconciliationItem.payment_id,
                    ReconciliationItem.expected_amount,
                    ReconciliationItem.actual_amount,
                    ReconciliationItem.difference,
                    ReconciliationItem.status.label("item_status"),
                    ReconciliationItem.created_at,
                    PaymentReconciliation.id.label("rec_id"),
                    PaymentReconciliation.status.label("rec_status"),
                    Payment.student_id,
                    Payment.amount.label("payment_amount"),
                )
                .join(
                    PaymentReconciliation,
                    PaymentReconciliation.id == ReconciliationItem.reconciliation_id,
                )
                .join(Payment, Payment.id == ReconciliationItem.payment_id)
                .where(and_(*rec_conds))
                .order_by(ReconciliationItem.created_at.desc())
                .limit(self.PER_CATEGORY_LIMIT)
            )
        ).all()
        for r in rec_rows:
            findings.append(
                {
                    "key": f"reconciliation-discrepancy:{r.id}",
                    "category": "reconciliation",
                    "severity": "high",
                    "title": "Reconciliation discrepancy",
                    "description": (
                        f"Payment #{r.payment_id} in reconciliation #{r.rec_id} "
                        f"({r.rec_status}): expected {r.expected_amount}, actual "
                        f"{r.actual_amount}, difference {r.difference}."
                    ),
                    "student_id": r.student_id,
                    "payment_id": r.payment_id,
                    "amount": r.payment_amount,
                    "reconciliation_item_id": r.id,
                    "reconciliation_status": r.rec_status,
                    "evidence": {
                        "expected_amount": r.expected_amount,
                        "actual_amount": r.actual_amount,
                        "difference": r.difference,
                        "item_status": r.item_status,
                    },
                    "created_at": r.created_at,
                }
            )

        # 2. payments without a generated receipt
        rec_exists = (
            select(Receipt.id).where(Receipt.payment_id == Payment.id).exists()
        )
        nr_conds = [~rec_exists]
        if payment_scope is not None:
            nr_conds.append(payment_scope)
        no_receipt_rows = (
            await self.session.execute(
                select(
                    Payment.id,
                    Payment.student_id,
                    Payment.amount,
                    Payment.payment_date,
                    Payment.payment_method,
                    Payment.created_at,
                )
                .where(and_(*nr_conds))
                .order_by(Payment.created_at.desc())
                .limit(self.PER_CATEGORY_LIMIT)
            )
        ).all()
        for r in no_receipt_rows:
            findings.append(
                {
                    "key": f"payment-no-receipt:{r.id}",
                    "category": "receipts",
                    "severity": "medium",
                    "title": "Payment without receipt",
                    "description": (
                        f"Payment #{r.id} ({r.payment_method or 'unknown'}, "
                        f"{r.payment_date or 'no date'}) has no generated receipt."
                    ),
                    "student_id": r.student_id,
                    "payment_id": r.id,
                    "amount": r.amount,
                    "evidence": {
                        "payment_method": r.payment_method,
                        "payment_date": r.payment_date,
                    },
                    "created_at": r.created_at,
                }
            )

        # 3. payments with no transaction-log entry
        tx_exists = (
            select(TransactionLog.id)
            .where(TransactionLog.payment_id == Payment.id)
            .exists()
        )
        nt_conds = [~tx_exists]
        if payment_scope is not None:
            nt_conds.append(payment_scope)
        no_tx_rows = (
            await self.session.execute(
                select(
                    Payment.id,
                    Payment.student_id,
                    Payment.amount,
                    Payment.payment_date,
                    Payment.payment_method,
                    Payment.created_at,
                )
                .where(and_(*nt_conds))
                .order_by(Payment.created_at.desc())
                .limit(self.PER_CATEGORY_LIMIT)
            )
        ).all()
        for r in no_tx_rows:
            findings.append(
                {
                    "key": f"payment-no-transaction:{r.id}",
                    "category": "ledger",
                    "severity": "high",
                    "title": "Payment missing from ledger",
                    "description": (
                        f"Payment #{r.id} ({r.payment_method or 'unknown'}) has "
                        "no corresponding transaction-log entry."
                    ),
                    "student_id": r.student_id,
                    "payment_id": r.id,
                    "amount": r.amount,
                    "evidence": {
                        "payment_method": r.payment_method,
                        "payment_date": r.payment_date,
                    },
                    "created_at": r.created_at,
                }
            )

        # 4. duplicate-looking payments (same student + amount + date)
        dup_base = select(
            Payment.id,
            Payment.student_id,
            Payment.amount,
            Payment.payment_date,
            Payment.receipt_number,
            Payment.created_at,
            func.count(Payment.id)
            .over(
                partition_by=[
                    Payment.student_id,
                    Payment.amount,
                    Payment.payment_date,
                ]
            )
            .label("grp"),
        )
        if payment_scope is not None:
            dup_base = dup_base.where(payment_scope)
        dup_sub = dup_base.subquery()
        dup_rows = (
            await self.session.execute(
                select(dup_sub)
                .where(dup_sub.c.grp > 1)
                .order_by(dup_sub.c.student_id, dup_sub.c.amount, dup_sub.c.payment_date)
                .limit(self.PER_CATEGORY_LIMIT)
            )
        ).all()
        peer_groups: dict[tuple, list[int]] = defaultdict(list)
        for r in dup_rows:
            peer_groups[(r.student_id, r.amount, r.payment_date)].append(r.id)
        for r in dup_rows:
            peers = [
                p for p in peer_groups[(r.student_id, r.amount, r.payment_date)] if p != r.id
            ]
            peer_text = ", #".join(str(p) for p in peers[:5])
            findings.append(
                {
                    "key": f"duplicate-payment:{r.id}",
                    "category": "duplicates",
                    "severity": "medium",
                    "title": "Duplicate-looking payment",
                    "description": (
                        f"Payment #{r.id} matches another payment for the same "
                        f"student, amount and date (#{peer_text}"
                        f"{'…' if len(peers) > 5 else ''}). Review for double booking."
                    ),
                    "student_id": r.student_id,
                    "payment_id": r.id,
                    "amount": r.amount,
                    "evidence": {
                        "payment_date": r.payment_date,
                        "receipt_number": r.receipt_number,
                        "peer_payment_ids": peers,
                    },
                    "created_at": r.created_at,
                }
            )

        # one batched lookup each: student names + linked operational cases
        student_ids = {f["student_id"] for f in findings if f["student_id"]}
        student_names: dict[int, str] = {}
        if student_ids:
            srows = (
                await self.session.execute(
                    select(Student.id, Student.first_name, Student.last_name).where(
                        Student.id.in_(student_ids)
                    )
                )
            ).all()
            student_names = {
                r.id: f"{r.first_name} {r.last_name}".strip() for r in srows
            }

        entity_ids = {
            f["reconciliation_item_id"]
            if f["category"] == "reconciliation"
            else f["payment_id"]
            for f in findings
        }
        entity_ids.discard(None)
        linked_cases: dict[int, dict] = {}
        if entity_ids:
            from app.domains.cases.models import CASE_SOURCE_FINANCIAL, Case

            cq = select(Case.id, Case.case_number, Case.status, Case.source_id).where(
                Case.source_type == CASE_SOURCE_FINANCIAL,
                Case.source_id.in_(entity_ids),
            )
            if campus_id is not None:
                cq = cq.where(Case.campus_id == campus_id)
            for r in (await self.session.execute(cq)).all():
                linked_cases[r.source_id] = {
                    "id": r.id,
                    "case_number": r.case_number,
                    "status": r.status,
                }

        for f in findings:
            if f["student_id"] in student_names:
                f["student_name"] = student_names[f["student_id"]]
            entity_id = (
                f["reconciliation_item_id"]
                if f["category"] == "reconciliation"
                else f["payment_id"]
            )
            if entity_id in linked_cases:
                f["linked_case"] = linked_cases[entity_id]

        return findings


# ═══════════════════════════════════════════════════════════════════════
# Receipt Service
# ═══════════════════════════════════════════════════════════════════════


class ReceiptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(
        self,
        data: ReceiptGenerate,
        generated_by: int,
        campus_id: Optional[int] = None,
    ) -> Receipt:
        """Generate a receipt for a payment.

        ``campus_id`` is the authoritative tenant scope from the router: a
        payment owned by a different campus must not be receipted here
        (prevents cross-tenant junction + amount disclosure).  Legacy
        NULL-campus payments remain accepted.
        """
        from app.domains.fees.models import Payment

        payment = await self.session.execute(
            select(Payment).where(Payment.id == data.payment_id)
        )
        payment = payment.scalar_one_or_none()
        if payment is None:
            raise NotFoundError(f"Payment {data.payment_id} not found")

        if campus_id is not None and payment.campus_id not in (None, campus_id):
            raise ValidationError(
                f"Payment {data.payment_id} does not belong to campus {campus_id}"
            )

        existing = await self._find_by_payment(data.payment_id)
        if existing:
            return existing

        return await self._create_with_retry(
            data, payment, generated_by, campus_id=campus_id
        )

    async def _create_with_retry(
        self,
        data: ReceiptGenerate,
        payment: Any,
        generated_by: int,
        campus_id: Optional[int] = None,
        attempts: int = 5,
    ) -> Receipt:
        """Insert a receipt, retrying when a concurrent request wins the
        receipt-number race (unique ``receipt_number`` constraint).

        Each attempt runs in its own savepoint, so a failed attempt rolls
        back cleanly and re-reads the latest sequence before retrying.
        """
        for _ in range(attempts):
            try:
                async with self.session.begin_nested():
                    receipt_number = await self._generate_receipt_number()
                    receipt = Receipt(
                        payment_id=data.payment_id,
                        receipt_number=receipt_number,
                        receipt_date=datetime.date.today(),
                        amount=payment.amount,
                        payment_method_name=payment.payment_method or "unknown",
                        reference_number=payment.receipt_number,
                        notes=data.notes,
                        status="active",
                        generated_by=generated_by,
                        campus_id=campus_id,
                    )
                    self.session.add(receipt)
                    await self.session.flush()
                return receipt
            except IntegrityError:
                logger.info(
                    "Receipt number collision on attempt; retrying", exc_info=True
                )
        raise ConflictError(
            "Could not allocate a unique receipt number - try again"
        )

    async def get(self, receipt_id: int) -> Receipt:
        result = await self.session.execute(
            select(Receipt).where(Receipt.id == receipt_id)
        )
        receipt = result.scalar_one_or_none()
        if receipt is None:
            raise NotFoundError(f"Receipt {receipt_id} not found")
        return receipt

    async def get_by_payment(self, payment_id: int) -> Receipt | None:
        result = await self.session.execute(
            select(Receipt).where(Receipt.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, receipt_number: str) -> Receipt:
        result = await self.session.execute(
            select(Receipt).where(Receipt.receipt_number == receipt_number)
        )
        receipt = result.scalar_one_or_none()
        if receipt is None:
            raise NotFoundError(f"Receipt {receipt_number} not found")
        return receipt

    async def list(
        self,
        payment_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Receipt], int]:
        conditions = []
        if payment_id is not None:
            conditions.append(Receipt.payment_id == payment_id)
        if campus_id is not None:
            conditions.append(Receipt.campus_id == campus_id)
        if status_filter is not None:
            conditions.append(Receipt.status == status_filter)
        if from_date is not None:
            conditions.append(Receipt.receipt_date >= from_date)
        if to_date is not None:
            conditions.append(Receipt.receipt_date <= to_date)

        cnt = select(func.count(Receipt.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(Receipt)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(Receipt.created_at.desc())
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def increment_print_count(self, receipt_id: int) -> Receipt:
        receipt = await self.get(receipt_id)
        receipt.printed_count += 1
        receipt.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return receipt

    async def get_receipt_detail(self, receipt_id: int) -> dict:
        receipt = await self.get(receipt_id)
        from app.domains.fees.models import Payment, FeeDue, FeeStructure, FeeType
        from app.domains.student.models import Student
        from app.domains.academic.models import AcademicYear

        payment = (
            await self.session.execute(
                select(Payment).where(Payment.id == receipt.payment_id)
            )
        ).scalar_one_or_none()

        detail = {
            "id": receipt.id,
            "receipt_number": receipt.receipt_number,
            "receipt_date": str(receipt.receipt_date),
            "amount": receipt.amount,
            "payment_method_name": receipt.payment_method_name,
            "reference_number": receipt.reference_number,
            "status": receipt.status,
            "printed_count": receipt.printed_count,
            "created_at": receipt.created_at,
        }

        if payment:
            student = (
                await self.session.execute(
                    select(Student).where(Student.id == payment.student_id)
                )
            ).scalar_one_or_none()
            if student:
                detail["student_name"] = (
                    f"{student.first_name} {student.last_name}"
                )
                detail["student_number"] = student.student_number

            fee_due = (
                await self.session.execute(
                    select(FeeDue).where(FeeDue.id == payment.fee_due_id)
                )
            ).scalar_one_or_none()
            if fee_due:
                structure = (
                    await self.session.execute(
                        select(FeeStructure).where(
                            FeeStructure.id == fee_due.fee_structure_id
                        )
                    )
                ).scalar_one_or_none()
                if structure:
                    fee_type = (
                        await self.session.execute(
                            select(FeeType).where(FeeType.id == structure.fee_type_id)
                        )
                    ).scalar_one_or_none()
                    if fee_type:
                        detail["fee_type_name"] = fee_type.name
                    year = (
                        await self.session.execute(
                            select(AcademicYear).where(
                                AcademicYear.id == structure.academic_year_id
                            )
                        )
                    ).scalar_one_or_none()
                    if year:
                        detail["academic_year_name"] = year.name

        return detail

    async def generate_receipt_html(self, receipt_id: int) -> str:
        detail = await self.get_receipt_detail(receipt_id)
        receipt = await self.get(receipt_id)

        def esc(value: Any) -> str:
            return html.escape(str(value), quote=True) if value is not None else "N/A"

        receipt_number = esc(detail["receipt_number"])
        receipt_date = esc(detail["receipt_date"])
        student_name = esc(detail.get("student_name", "N/A"))
        student_number = esc(detail.get("student_number", "N/A"))
        fee_type_name = esc(detail.get("fee_type_name", "N/A"))
        payment_method_name = esc(detail["payment_method_name"])
        reference_row = (
            f'<tr><td class="label">Reference:</td><td>{esc(detail["reference_number"])}</td></tr>'
            if detail.get("reference_number")
            else ""
        )
        amount = detail["amount"] / 100

        receipt_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Receipt {receipt_number}</title>
<style>
  body {{ font-family: 'Courier New', monospace; font-size: 12px; max-width: 80mm; margin: 0 auto; padding: 10px; }}
  .header {{ text-align: center; margin-bottom: 10px; }}
  .header h1 {{ font-size: 16px; margin: 0; }}
  .header p {{ margin: 2px 0; font-size: 11px; }}
  hr {{ border: none; border-top: 1px dashed #000; margin: 8px 0; }}
  .row {{ display: flex; justify-content: space-between; margin: 4px 0; }}
  .label {{ font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 4px 2px; }}
  .total-row {{ font-weight: bold; border-top: 1px solid #000; }}
  .footer {{ text-align: center; margin-top: 10px; font-size: 10px; }}
</style></head>
<body>
<div class="header">
  <h1>RECEIPT</h1>
  <p>#{receipt_number}</p>
  <p>{receipt_date}</p>
</div>
<hr>
<table>
  <tr><td class="label">Student:</td><td>{student_name}</td></tr>
  <tr><td class="label">Student #:</td><td>{student_number}</td></tr>
  <tr><td class="label">Fee Type:</td><td>{fee_type_name}</td></tr>
  <tr><td class="label">Payment Method:</td><td>{payment_method_name}</td></tr>
  {reference_row}
</table>
<hr>
<div class="row">
  <span class="label">Amount Paid:</span>
  <span>&#8377;{amount:.2f}</span>
</div>
<hr>
<div class="footer">
  <p>This is a computer-generated receipt.</p>
  <p>Printed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>
<script>window.print();</script>
</body></html>"""
        return receipt_html

    async def export_receipts_csv(
        self,
        campus_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        conditions = []
        if campus_id is not None:
            conditions.append(Receipt.campus_id == campus_id)
        if from_date is not None:
            conditions.append(Receipt.receipt_date >= from_date)
        if to_date is not None:
            conditions.append(Receipt.receipt_date <= to_date)

        q = select(Receipt)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.order_by(Receipt.receipt_date.desc())
        result = await self.session.execute(q)
        receipts = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Receipt Number", "Date", "Amount (cents)", "Payment Method", "Reference", "Status", "Printed Count"])
        for r in receipts:
            writer.writerow([
                r.receipt_number, r.receipt_date, r.amount,
                r.payment_method_name, r.reference_number or "",
                r.status, r.printed_count,
            ])
        return output.getvalue()

    async def _find_by_payment(self, payment_id: int) -> Receipt | None:
        result = await self.session.execute(
            select(Receipt).where(Receipt.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def _generate_receipt_number(self) -> str:
        today = datetime.date.today()
        prefix = f"RCP-{today.year}{today.month:02d}{today.day:02d}-"
        result = await self.session.execute(
            select(
                func.max(
                    func.cast(
                        func.substr(Receipt.receipt_number, len(prefix) + 1),
                        Integer,
                    )
                )
            ).where(Receipt.receipt_number.like(f"{prefix}%"))
        )
        last_seq = result.scalar_one_or_none()
        seq = (last_seq or 0) + 1
        return f"{prefix}{seq:04d}"


# ═══════════════════════════════════════════════════════════════════════
# Outstanding Balances Service
# ═══════════════════════════════════════════════════════════════════════


class OutstandingBalanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_outstanding(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        from app.domains.fees.models import FeeDue, FeeStructure
        from app.domains.student.models import Student
        from app.domains.academic.models import Enrollment, Class, Section

        conditions = [FeeDue.status.in_(["unpaid", "partially_paid"])]
        if academic_year_id is not None:
            conditions.append(FeeDue.academic_year_id == academic_year_id)
        if campus_id is not None:
            conditions.append(FeeDue.campus_id == campus_id)

        q = (
            select(
                FeeDue.student_id,
                func.sum(FeeDue.original_amount).label("total_assigned"),
                func.sum(FeeDue.amount_paid).label("total_paid"),
                func.count(FeeDue.id).label("due_count"),
                func.sum(
                    func.case(
                        (FeeDue.due_date < str(datetime.date.today()), 1),
                        else_=0,
                    )
                ).label("overdue_count"),
            )
            .where(and_(*conditions))
            .group_by(FeeDue.student_id)
        )
        result = await self.session.execute(q)
        rows = result.all()

        items = []
        total_assigned = total_paid = total_outstanding = total_overdue = 0
        student_ids = set()

        for row in rows:
            sid = row.student_id
            assigned = row.total_assigned or 0
            paid = row.total_paid or 0
            outstanding = assigned - paid
            overdue = row.overdue_count or 0

            student_ids.add(sid)
            total_assigned += assigned
            total_paid += paid
            total_outstanding += outstanding
            total_overdue += overdue

            items.append({
                "student_id": sid,
                "total_assigned": assigned,
                "total_paid": paid,
                "outstanding": outstanding,
                "due_count": row.due_count,
                "overdue_count": overdue,
                "status": "overdue" if overdue > 0 else "outstanding",
            })

        items.sort(key=lambda x: x["outstanding"], reverse=True)
        paginated = items[skip: skip + limit]

        return {
            "total_students": len(student_ids),
            "total_assigned": total_assigned,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "total_overdue": total_overdue,
            "items": paginated,
        }


# ═══════════════════════════════════════════════════════════════════════
# Finance Reports Service
# ═══════════════════════════════════════════════════════════════════════


class FinanceReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.transaction_svc = TransactionLogService(session)

    async def generate_collection_summary_csv(
        self, academic_year_id: Optional[int] = None, campus_id: Optional[int] = None
    ) -> str:
        from app.domains.fees.models import Payment, FeeDue, FeeStructure

        conditions = []
        if academic_year_id is not None:
            conditions.append(FeeDue.academic_year_id == academic_year_id)
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)

        q = (
            select(
                FeeDue.student_id,
                FeeStructure.class_id,
                func.sum(FeeDue.original_amount).label("total_fees"),
                func.coalesce(func.sum(Payment.amount), 0).label("total_paid"),
            )
            .join(FeeStructure, FeeStructure.id == FeeDue.fee_structure_id)
            .outerjoin(Payment, Payment.fee_due_id == FeeDue.id)
        )
        if conditions:
            q = q.where(and_(*conditions))
        q = q.group_by(FeeDue.student_id, FeeStructure.class_id)
        result = await self.session.execute(q)
        rows = result.all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Student ID", "Class ID", "Total Fees (cents)", "Total Paid (cents)", "Outstanding (cents)"])
        for row in rows:
            outstanding = (row.total_fees or 0) - row.total_paid
            writer.writerow([row.student_id, row.class_id, row.total_fees or 0, row.total_paid, outstanding])
        return output.getvalue()

    async def generate_report(
        self, data: FinanceReportGenerate, generated_by: int
    ) -> FinanceReport:
        report = FinanceReport(
            report_type=data.report_type,
            title=data.title,
            parameters=data.parameters or {},
            file_format=data.file_format,
            status="completed",
            campus_id=data.campus_id,
            generated_by=generated_by,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_report(self, report_id: int) -> FinanceReport:
        result = await self.session.execute(
            select(FinanceReport).where(FinanceReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise NotFoundError(f"Finance report {report_id} not found")
        return report

    async def list_reports(
        self,
        report_type: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FinanceReport], int]:
        conditions = []
        if report_type is not None:
            conditions.append(FinanceReport.report_type == report_type)
        if campus_id is not None:
            conditions.append(FinanceReport.campus_id == campus_id)

        cnt = select(func.count(FinanceReport.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(FinanceReport)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(FinanceReport.created_at.desc())
        result = await self.session.execute(q)
        return result.scalars().all(), total


# ═══════════════════════════════════════════════════════════════════════
# Dashboard Service
# ═══════════════════════════════════════════════════════════════════════


class SchoolFinanceDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_dashboard(
        self, campus_id: Optional[int] = None
    ) -> dict:
        from app.domains.fees.models import Payment, FeeDue

        conditions = []
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)

        total_payments_q = select(func.coalesce(func.sum(Payment.amount), 0))
        if conditions:
            total_payments_q = total_payments_q.where(and_(*conditions))
        total_collected = (await self.session.execute(total_payments_q)).scalar() or 0

        payment_count_q = select(func.count(Payment.id))
        if conditions:
            payment_count_q = payment_count_q.where(and_(*conditions))
        payment_count = (await self.session.execute(payment_count_q)).scalar() or 0

        due_conditions = []
        if campus_id is not None:
            due_conditions.append(FeeDue.campus_id == campus_id)

        total_due_q = select(func.coalesce(func.sum(FeeDue.original_amount), 0))
        if due_conditions:
            total_due_q = total_due_q.where(and_(*due_conditions))
        total_assigned = (await self.session.execute(total_due_q)).scalar() or 0

        total_paid_q = select(func.coalesce(func.sum(FeeDue.amount_paid), 0))
        if due_conditions:
            total_paid_q = total_paid_q.where(and_(*due_conditions))
        total_paid = (await self.session.execute(total_paid_q)).scalar() or 0

        total_outstanding = total_assigned - total_paid

        today = datetime.date.today().isoformat()
        today_conditions = [Payment.payment_date == today]
        if campus_id is not None:
            today_conditions.append(Payment.campus_id == campus_id)
        today_payments_q = select(
            func.coalesce(func.sum(Payment.amount), 0)
        ).where(and_(*today_conditions))
        today_collection = (await self.session.execute(today_payments_q)).scalar() or 0

        today_count_q = select(func.count(Payment.id)).where(and_(*today_conditions))
        today_count = (await self.session.execute(today_count_q)).scalar() or 0

        rec_conditions = []
        if campus_id is not None:
            rec_conditions.append(PaymentReconciliation.campus_id == campus_id)

        rec_count_q = select(func.count(PaymentReconciliation.id))
        if rec_conditions:
            rec_count_q = rec_count_q.where(and_(*rec_conditions))
        total_rec = (await self.session.execute(rec_count_q)).scalar() or 0

        pending_rec_q = select(func.count(PaymentReconciliation.id)).where(
            PaymentReconciliation.status.in_(["draft", "submitted"])
        )
        if campus_id is not None:
            pending_rec_q = pending_rec_q.where(
                PaymentReconciliation.campus_id == campus_id
            )
        pending = (await self.session.execute(pending_rec_q)).scalar() or 0

        collection_rate = round((total_collected / total_assigned * 100), 1) if total_assigned > 0 else 0.0

        recent_q = select(TransactionLog).order_by(TransactionLog.created_at.desc()).limit(10)
        if campus_id is not None:
            recent_q = recent_q.where(TransactionLog.campus_id == campus_id)
        recent_logs = (await self.session.execute(recent_q)).scalars().all()

        from app.domains.school_finance.schemas import TransactionLogResponse
        return {
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "total_overdue": 0,
            "payment_count": payment_count,
            "reconciled_count": total_rec - pending,
            "pending_reconciliation": pending,
            "collection_rate": collection_rate,
            "today_collection": today_collection,
            "today_count": today_count,
            "recent_transactions": [
                TransactionLogResponse.model_validate(t).model_dump()
                for t in recent_logs
            ],
        }
