from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.student.models import Student
from app.domains.fees.models import Payment, FeeDue, FeeStructure, FeeType
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class PaymentJournalReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="payment_journal",
            name="Payment / Receipt Journal",
            description="Detailed payment journal with student, amount, method and fee type information",
            category="fees",
            allowed_roles=["admin", "manager", "accountant"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="from_date", label="From Date", type="date", required=False),
                ReportFilter(key="to_date", label="To Date", type="date", required=False),
                ReportFilter(key="payment_method", label="Payment Method", type="select", required=False),
                ReportFilter(key="student_id", label="Student", type="select", required=False),
            ],
            columns=[
                ReportColumn(key="payment_id", header="Payment ID", type="integer"),
                ReportColumn(key="receipt_number", header="Receipt Number"),
                ReportColumn(key="student_name", header="Student Name"),
                ReportColumn(key="student_number", header="Student Number"),
                ReportColumn(key="amount", header="Amount", type="integer"),
                ReportColumn(key="payment_date", header="Payment Date"),
                ReportColumn(key="payment_method", header="Payment Method"),
                ReportColumn(key="fee_type", header="Fee Type"),
                ReportColumn(key="status", header="Status"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        payment_method = params.get("payment_method")
        student_id = params.get("student_id")

        conditions = [FeeDue.academic_year_id == academic_year_id]
        if from_date is not None:
            conditions.append(Payment.payment_date >= from_date)
        if to_date is not None:
            conditions.append(Payment.payment_date <= to_date)
        if payment_method is not None:
            conditions.append(Payment.payment_method == payment_method)
        if student_id is not None:
            conditions.append(Payment.student_id == student_id)
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)

        stmt = (
            select(Payment, FeeDue, FeeStructure, FeeType, Student)
            .join(FeeDue, Payment.fee_due_id == FeeDue.id)
            .join(FeeStructure, FeeDue.fee_structure_id == FeeStructure.id)
            .join(FeeType, FeeStructure.fee_type_id == FeeType.id)
            .join(Student, Payment.student_id == Student.id)
            .where(and_(*conditions))
            .order_by(Payment.payment_date.desc(), Payment.id.desc())
        )

        result = await session.execute(stmt)
        return result.all()

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        rows = []
        for row in data:
            payment, fee_due, structure, fee_type, student = row
            rows.append({
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number or "",
                "student_name": f"{student.first_name} {student.last_name}",
                "student_number": student.student_number,
                "amount": payment.amount,
                "payment_date": payment.payment_date or "",
                "payment_method": payment.payment_method or "",
                "fee_type": fee_type.name,
                "status": fee_due.status,
            })
        return rows
