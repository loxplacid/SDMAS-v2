from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.attendance.models import AttendanceRecord
from app.domains.attendance.repository import AttendanceRepository
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
    PaymentRepository,
)
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository


def _stream_csv(headers: list[str], rows: list[list[str]], filename: str) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    content = output.getvalue().encode("utf-8-sig")

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.student_repo = StudentRepository(session)
        self.year_repo = AcademicYearRepository(session)
        self.class_repo = ClassRepository(session)
        self.section_repo = SectionRepository(session)
        self.enrollment_repo = EnrollmentRepository(session)
        self.attendance_repo = AttendanceRepository(session)
        self.fee_due_repo = FeeDueRepository(session)
        self.structure_repo = FeeStructureRepository(session)
        self.fee_type_repo = FeeTypeRepository(session)
        self.payment_repo = PaymentRepository(session)

    async def export_students_csv(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> StreamingResponse:
        if search:
            students, _ = await self.student_repo.search(search, skip=0, limit=100000)
        else:
            students, _ = await self.student_repo.list(status=status, skip=0, limit=100000)

        headers = ["Student Number", "First Name", "Last Name", "Email", "Date of Birth", "Status"]
        rows = [
            [
                s.student_number,
                s.first_name,
                s.last_name,
                s.email or "",
                str(s.date_of_birth) if s.date_of_birth else "",
                s.status,
            ]
            for s in students
        ]

        return _stream_csv(headers, rows, "students.csv")

    async def export_attendance_csv(
        self,
        section_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> StreamingResponse:
        conditions = []
        if section_id is not None:
            conditions.append(AttendanceRecord.section_id == section_id)
        if start_date is not None:
            conditions.append(AttendanceRecord.attendance_date >= start_date)
        if end_date is not None:
            conditions.append(AttendanceRecord.attendance_date <= end_date)

        query = select(AttendanceRecord)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(AttendanceRecord.attendance_date)

        result = await self.session.execute(query)
        records = result.scalars().all()

        student_cache: dict[int, Student] = {}
        section_cache: dict[int, Section] = {}
        class_cache: dict[int, str] = {}

        async def _get_student(sid: int) -> Student:
            if sid not in student_cache:
                student_cache[sid] = await self.student_repo.get_by_id(sid)
            return student_cache[sid]

        async def _get_section(sid: int) -> Section:
            if sid not in section_cache:
                section_cache[sid] = await self.section_repo.get_by_id(sid)
            return section_cache[sid]

        headers = [
            "Student Number", "Student Name", "Date", "Status",
            "Notes", "Section", "Class",
        ]
        rows: list[list[str]] = []

        for r in records:
            student = await _get_student(r.student_id)
            section = await _get_section(r.section_id)
            class_name = class_cache.get(section.class_id)
            if class_name is None:
                cls = await self.class_repo.get_by_id(section.class_id)
                class_name = cls.name
                class_cache[section.class_id] = class_name

            rows.append(
                [
                    student.student_number,
                    f"{student.first_name} {student.last_name}",
                    r.attendance_date,
                    r.status,
                    r.notes or "",
                    section.name,
                    class_name,
                ]
            )

        return _stream_csv(headers, rows, "attendance.csv")

    async def export_payments_csv(
        self,
        academic_year_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> StreamingResponse:
        conditions = []
        if start_date is not None:
            conditions.append(Payment.payment_date >= start_date)
        if end_date is not None:
            conditions.append(Payment.payment_date <= end_date)

        query = select(Payment)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(Payment.payment_date)

        result = await self.session.execute(query)
        payments = result.scalars().all()

        student_cache: dict[int, Student] = {}
        due_cache: dict[int, FeeDue] = {}
        structure_cache: dict[int, FeeStructure] = {}
        fee_type_cache: dict[int, FeeType] = {}
        year_name_cache: dict[int, str] = {}

        headers = [
            "Receipt Number", "Student Number", "Student Name",
            "Amount", "Payment Date", "Payment Method",
            "Fee Type", "Academic Year",
        ]
        rows: list[list[str]] = []

        for p in payments:
            if p.student_id not in student_cache:
                try:
                    student_cache[p.student_id] = await self.student_repo.get_by_id(
                        p.student_id
                    )
                except Exception:
                    continue

            student = student_cache[p.student_id]

            due = due_cache.get(p.fee_due_id)
            if due is None:
                due = await self.fee_due_repo.get_by_id(p.fee_due_id)
                due_cache[p.fee_due_id] = due

            structure = structure_cache.get(due.fee_structure_id)
            if structure is None:
                structure = await self.structure_repo.get_by_id(
                    due.fee_structure_id
                )
                structure_cache[due.fee_structure_id] = structure

            fee_type = fee_type_cache.get(structure.fee_type_id)
            if fee_type is None:
                fee_type = await self.fee_type_repo.get_by_id(
                    structure.fee_type_id
                )
                fee_type_cache[structure.fee_type_id] = fee_type

            year_name = year_name_cache.get(due.academic_year_id)
            if year_name is None:
                year = await self.year_repo.get_by_id(due.academic_year_id)
                year_name = year.name
                year_name_cache[due.academic_year_id] = year_name

            if academic_year_id is not None and due.academic_year_id != academic_year_id:
                continue

            rows.append(
                [
                    p.receipt_number or "",
                    student.student_number,
                    f"{student.first_name} {student.last_name}",
                    str(p.amount),
                    p.payment_date or "",
                    p.payment_method or "",
                    fee_type.name,
                    year_name,
                ]
            )

        return _stream_csv(headers, rows, "payments.csv")