from __future__ import annotations

import csv
import datetime
import io
import logging
import uuid
from collections import defaultdict
from datetime import date, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select
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
)

logger = logging.getLogger(__name__)


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
            existing = await self.find_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        last_balance = await self._get_last_balance(student_id)
        balance_before = balance_before or last_balance
        balance_after = balance_before - amount if transaction_type in ("refund", "waiver", "discount") else balance_before + amount

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

    async def find_by_idempotency_key(self, key: str) -> TransactionLog | None:
        result = await self.session.execute(
            select(TransactionLog).where(TransactionLog.idempotency_key == key)
        )
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

    async def get_student_balance(self, student_id: int) -> int:
        logs = await self.session.execute(
            select(func.coalesce(func.sum(TransactionLog.amount), 0)).where(
                TransactionLog.student_id == student_id,
                TransactionLog.transaction_type.in_(["payment"]),
            )
        )
        credits = logs.scalar() or 0

        debits = await self.session.execute(
            select(func.coalesce(func.sum(TransactionLog.amount), 0)).where(
                TransactionLog.student_id == student_id,
                TransactionLog.transaction_type.in_(["refund", "waiver", "discount"]),
            )
        )
        return credits - (debits.scalar() or 0)

    async def _get_last_balance(self, student_id: int) -> int:
        result = await self.session.execute(
            select(TransactionLog)
            .where(TransactionLog.student_id == student_id)
            .order_by(TransactionLog.created_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        return last.balance_after if last else 0


# ═══════════════════════════════════════════════════════════════════════
# Payment Reconciliation Service
# ═══════════════════════════════════════════════════════════════════════


class ReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: ReconciliationCreate, reconciled_by: int) -> PaymentReconciliation:
        rec = PaymentReconciliation(
            reconciliation_date=data.reconciliation_date,
            total_amount=data.total_amount,
            total_count=data.total_count,
            status="draft",
            notes=data.notes,
            campus_id=data.campus_id,
            reconciled_by=reconciled_by,
        )
        self.session.add(rec)
        await self.session.flush()

        for item_data in data.items:
            payment = await self._validate_payment(item_data.payment_id)
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
        return result.scalar_one()

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

        cnt = select(func.count(PaymentReconciliation.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(PaymentReconciliation).options(joinedload(PaymentReconciliation.items))
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(PaymentReconciliation.reconciliation_date.desc())
        result = await self.session.execute(q)
        items = list({r.id: r for r in result.scalars().all()}.values())
        return items[:limit], total

    async def verify(self, rec_id: int, reviewed_by: int) -> PaymentReconciliation:
        rec = await self.get(rec_id)
        if rec.status != "draft":
            raise ValidationError(f"Reconciliation {rec_id} is already {rec.status}")
        rec.status = "verified"
        rec.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return rec

    async def approve(self, rec_id: int, reviewed_by: int) -> PaymentReconciliation:
        rec = await self.get(rec_id)
        if rec.status not in ("draft", "verified"):
            raise ValidationError(f"Reconciliation {rec_id} cannot be approved from status {rec.status}")
        rec.status = "approved"
        rec.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return rec

    async def _validate_payment(self, payment_id: int):
        from app.domains.fees.models import Payment
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            raise NotFoundError(f"Payment {payment_id} not found")
        return payment


# ═══════════════════════════════════════════════════════════════════════
# Receipt Service
# ═══════════════════════════════════════════════════════════════════════


class ReceiptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(self, data: ReceiptGenerate, generated_by: int) -> Receipt:
        from app.domains.fees.models import Payment

        payment = await self.session.execute(
            select(Payment).where(Payment.id == data.payment_id)
        )
        payment = payment.scalar_one_or_none()
        if payment is None:
            raise NotFoundError(f"Payment {data.payment_id} not found")

        existing = await self._find_by_payment(data.payment_id)
        if existing:
            return existing

        receipt_number = await self._generate_receipt_number()
        receipt = Receipt(
            payment_id=data.payment_id,
            receipt_number=receipt_number,
            receipt_date=datetime.date.today(),
            amount=payment.amount,
            payment_method_name=payment.payment_method,
            reference_number=payment.receipt_number,
            notes=data.notes,
            status="active",
            generated_by=generated_by,
        )
        self.session.add(receipt)
        await self.session.flush()
        return receipt

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
        from app.domains.academic.models import AcademicYear, Class, Section
        from app.domains.academic.repository import SectionRepository

        payment = await self.session.execute(
            select(Payment)
            .options(
                joinedload(Payment.student),
                joinedload(Payment.fee_due).joinedload(FeeDue.fee_structure)
                .joinedload(FeeStructure.fee_type),
            )
            .where(Payment.id == receipt.payment_id)
        )
        payment = payment.scalar_one_or_none()

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
            detail["student_name"] = getattr(payment, "student", None) and f"{payment.student.first_name} {payment.student.last_name}"
            detail["student_number"] = getattr(payment, "student", None) and payment.student.student_number
            if payment.fee_due and payment.fee_due.fee_structure:
                detail["fee_type_name"] = payment.fee_due.fee_structure.fee_type.name
                detail["academic_year_name"] = getattr(payment.fee_due.fee_structure, "academic_year", None) and payment.fee_due.fee_structure.academic_year.name

        return detail

    async def generate_receipt_html(self, receipt_id: int) -> str:
        detail = await self.get_receipt_detail(receipt_id)
        receipt = await self.get(receipt_id)

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Receipt {detail['receipt_number']}</title>
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
  <p>#{detail['receipt_number']}</p>
  <p>{detail['receipt_date']}</p>
</div>
<hr>
<table>
  <tr><td class="label">Student:</td><td>{detail.get('student_name', 'N/A')}</td></tr>
  <tr><td class="label">Student #:</td><td>{detail.get('student_number', 'N/A')}</td></tr>
  <tr><td class="label">Fee Type:</td><td>{detail.get('fee_type_name', 'N/A')}</td></tr>
  <tr><td class="label">Payment Method:</td><td>{detail['payment_method_name']}</td></tr>
  {f'<tr><td class="label">Reference:</td><td>{detail["reference_number"]}</td></tr>' if detail.get('reference_number') else ''}
</table>
<hr>
<div class="row">
  <span class="label">Amount Paid:</span>
  <span>${detail['amount'] / 100:.2f}</span>
</div>
<hr>
<div class="footer">
  <p>This is a computer-generated receipt.</p>
  <p>Printed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>
<script>window.print();</script>
</body></html>"""
        return html

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
        last = await self.session.execute(
            select(Receipt.receipt_number)
            .where(Receipt.receipt_number.like(f"{prefix}%"))
            .order_by(Receipt.id.desc())
            .limit(1)
        )
        last_num = last.scalar_one_or_none()
        if last_num:
            seq = int(last_num.split("-")[-1]) + 1
        else:
            seq = 1
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
        from app.domains.fees.models import Payment, FeeDue
        from app.domains.student.models import Student
        from app.domains.academic.models import Class

        conditions = []
        if academic_year_id is not None:
            conditions.append(FeeDue.academic_year_id == academic_year_id)
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)

        q = (
            select(
                FeeDue.student_id,
                FeeDue.class_id,
                func.sum(FeeDue.original_amount).label("total_fees"),
                func.coalesce(func.sum(Payment.amount), 0).label("total_paid"),
            )
            .outerjoin(Payment, Payment.fee_due_id == FeeDue.id)
        )
        if conditions:
            q = q.where(and_(*conditions))
        q = q.group_by(FeeDue.student_id, FeeDue.class_id)
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

        total_payments = await self.session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
        )
        if conditions:
            total_payments = total_payments.where(and_(*conditions))
        total_collected = total_payments.scalar() or 0

        payment_count_result = await self.session.execute(
            select(func.count(Payment.id))
        )
        if conditions:
            payment_count_result = payment_count_result.where(and_(*conditions))
        payment_count = payment_count_result.scalar() or 0

        due_conditions = []
        if campus_id is not None:
            due_conditions.append(FeeDue.campus_id == campus_id)

        total_due = await self.session.execute(
            select(func.coalesce(func.sum(FeeDue.original_amount), 0))
        )
        if due_conditions:
            total_due = total_due.where(and_(*due_conditions))
        total_assigned = total_due.scalar() or 0

        total_paid_due = await self.session.execute(
            select(func.coalesce(func.sum(FeeDue.amount_paid), 0))
        )
        if due_conditions:
            total_paid_due = total_paid_due.where(and_(*due_conditions))
        total_paid = total_paid_due.scalar() or 0

        total_outstanding = total_assigned - total_paid

        today = datetime.date.today().isoformat()
        today_payments = await self.session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.payment_date == today
            )
        )
        today_collection = today_payments.scalar() or 0

        today_count_result = await self.session.execute(
            select(func.count(Payment.id)).where(
                Payment.payment_date == today
            )
        )
        today_count = today_count_result.scalar() or 0

        rec_conditions = []
        if campus_id is not None:
            rec_conditions.append(PaymentReconciliation.campus_id == campus_id)

        rec_count = await self.session.execute(
            select(func.count(PaymentReconciliation.id))
        )
        if rec_conditions:
            rec_count = rec_count.where(and_(*rec_conditions))
        total_rec = rec_count.scalar() or 0

        pending_rec = await self.session.execute(
            select(func.count(PaymentReconciliation.id)).where(
                PaymentReconciliation.status.in_(["draft", "submitted"])
            )
        )
        pending = pending_rec.scalar() or 0

        collection_rate = round((total_collected / total_assigned * 100), 1) if total_assigned > 0 else 0.0

        recent = await self.session.execute(
            select(TransactionLog)
            .order_by(TransactionLog.created_at.desc())
            .limit(10)
        )
        recent_logs = recent.scalars().all()

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
