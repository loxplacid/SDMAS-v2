from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.academic.models import Class, Enrollment
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
from app.domains.student.repository import StudentRepository


class FeeReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.fee_due_repo = FeeDueRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.student_repo = StudentRepository(session)
        self.year_repo = AcademicYearRepository(session)
        self.class_repo = ClassRepository(session)
        self.enrollment_repo = EnrollmentRepository(session)
        self.structure_repo = FeeStructureRepository(session)
        self.fee_type_repo = FeeTypeRepository(session)

    async def get_collection_report(
        self,
        academic_year_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        year = await self.year_repo.get_by_id(academic_year_id)

        classes, _ = await self.class_repo.list(
            year_id=academic_year_id, limit=10000
        )

        all_dues = await self.fee_due_repo.find_by_academic_year(academic_year_id)

        payments_conditions = []
        if start_date is not None:
            payments_conditions.append(Payment.payment_date >= start_date)
        if end_date is not None:
            payments_conditions.append(Payment.payment_date <= end_date)

        payments_result = await self.session.execute(
            select(Payment).where(and_(*payments_conditions))
            if payments_conditions
            else select(Payment)
        )
        all_payments = payments_result.scalars().all()

        payment_totals: dict[int, int] = {}
        for p in all_payments:
            payment_totals[p.student_id] = (
                payment_totals.get(p.student_id, 0) + p.amount
            )

        report: list[dict] = []
        for cls in classes:
            enrollments, _ = await self.enrollment_repo.list(
                class_id=cls.id, academic_year_id=academic_year_id, limit=10000
            )
            student_ids = {e.student_id for e in enrollments}

            total_assigned = 0
            total_collected = 0
            for due in all_dues:
                if due.student_id in student_ids:
                    total_assigned += due.original_amount
                    total_collected += payment_totals.get(due.student_id, 0)

            outstanding = total_assigned - total_collected
            percentage = (
                round((total_collected / total_assigned) * 10000) / 100
                if total_assigned > 0
                else 0.0
            )

            report.append(
                {
                    "class_id": cls.id,
                    "class_name": cls.name,
                    "total_students": len(student_ids),
                    "total_fees_assigned": total_assigned,
                    "total_collected": total_collected,
                    "total_outstanding": outstanding,
                    "collection_percentage": percentage,
                }
            )

        return report

    async def get_outstanding_report(
        self,
        academic_year_id: int,
        class_id: Optional[int] = None,
    ) -> list[dict]:
        year = await self.year_repo.get_by_id(academic_year_id)

        enroll_conditions = [Enrollment.academic_year_id == academic_year_id]
        if class_id is not None:
            enroll_conditions.append(Enrollment.class_id == class_id)

        enroll_result = await self.session.execute(
            select(Enrollment).where(and_(*enroll_conditions))
        )
        enrollments = enroll_result.scalars().all()

        if not enrollments:
            return []

        student_ids = {e.student_id for e in enrollments}
        class_map: dict[int, str] = {}
        for e in enrollments:
            if e.class_id is not None:
                try:
                    cls = await self.class_repo.get_by_id(e.class_id)
                    class_map[e.student_id] = cls.name
                except NotFoundError:
                    class_map[e.student_id] = "Unknown"

        dues = await self.fee_due_repo.find_by_academic_year(academic_year_id)
        student_dues: dict[int, list[FeeDue]] = {}
        for d in dues:
            if d.student_id in student_ids:
                student_dues.setdefault(d.student_id, []).append(d)

        report: list[dict] = []
        for sid in student_ids:
            s_dues = student_dues.get(sid, [])
            total_fees = sum(d.original_amount for d in s_dues)
            total_paid = sum(d.amount_paid for d in s_dues)
            outstanding = total_fees - total_paid

            if outstanding <= 0:
                continue

            unpaid = sum(1 for d in s_dues if d.status == "unpaid")
            partial = sum(1 for d in s_dues if d.status == "partially_paid")

            try:
                student = await self.student_repo.get_by_id(sid)
                student_name = f"{student.first_name} {student.last_name}"
                student_number = student.student_number
            except NotFoundError:
                student_name = "Unknown"
                student_number = ""

            report.append(
                {
                    "student_id": sid,
                    "student_name": student_name,
                    "student_number": student_number,
                    "class_name": class_map.get(sid, "Unknown"),
                    "total_fees": total_fees,
                    "total_paid": total_paid,
                    "outstanding": outstanding,
                    "due_count": len(s_dues),
                    "unpaid_count": unpaid,
                    "partially_paid_count": partial,
                }
            )

        report.sort(key=lambda x: x["outstanding"], reverse=True)
        return report

    async def get_detailed_receipt(self, payment_id: int) -> dict:
        payment = await self.payment_repo.get_by_id(payment_id)

        student = await self.student_repo.get_by_id(payment.student_id)
        student_name = f"{student.first_name} {student.last_name}"

        due = await self.fee_due_repo.get_by_id(payment.fee_due_id)
        structure = await self.structure_repo.get_by_id(due.fee_structure_id)
        fee_type = await self.fee_type_repo.get_by_id(structure.fee_type_id)
        year = await self.year_repo.get_by_id(due.academic_year_id)

        return {
            "payment_id": payment.id,
            "receipt_number": payment.receipt_number,
            "student_id": student.id,
            "student_name": student_name,
            "student_number": student.student_number,
            "fee_due_id": due.id,
            "amount": payment.amount,
            "payment_date": payment.payment_date,
            "payment_method": payment.payment_method,
            "academic_year_name": year.name,
            "fee_type_name": fee_type.name,
            "created_at": payment.created_at,
        }