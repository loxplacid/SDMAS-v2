from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func, and_
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
from app.domains.student.repository import StudentRepository
from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext


class AttendanceReportService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.attendance_repo = AttendanceRepository(session, tenant)
        self.student_repo = StudentRepository(session, tenant)
        self.year_repo = AcademicYearRepository(session, tenant)
        self.class_repo = ClassRepository(session, tenant)
        self.section_repo = SectionRepository(session, tenant)
        self.enrollment_repo = EnrollmentRepository(session, tenant)

    async def get_class_attendance_summary(
        self,
        class_id: int,
        academic_year_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        cls = await self.class_repo.get_by_id(class_id)

        enrollments, _ = await self.enrollment_repo.list(
            class_id=class_id, academic_year_id=academic_year_id, limit=10000
        )
        student_ids = {e.student_id for e in enrollments}

        conditions = [
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.academic_year_id == academic_year_id,
        ]
        if start_date is not None:
            conditions.append(AttendanceRecord.attendance_date >= start_date)
        if end_date is not None:
            conditions.append(AttendanceRecord.attendance_date <= end_date)

        result = await self.session.execute(
            self.attendance_repo.scoped_query(AttendanceRecord).where(
                and_(*conditions)
            )
        )
        records = result.scalars().all()

        present = sum(1 for r in records if r.status == "present")
        absent = sum(1 for r in records if r.status == "absent")
        late = sum(1 for r in records if r.status == "late")
        excused = sum(1 for r in records if r.status == "excused")
        total = len(records)
        percentage = round((present / total) * 10000) / 100 if total > 0 else 0.0

        return {
            "class_id": class_id,
            "class_name": cls.name,
            "academic_year_id": academic_year_id,
            "total_students": len(student_ids),
            "total_records": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "present_percentage": percentage,
        }

    async def get_section_attendance_summary(
        self,
        section_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        section = await self.section_repo.get_by_id(section_id)
        cls = await self.class_repo.get_by_id(section.class_id)

        enrollments, _ = await self.enrollment_repo.list(
            section_id=section_id, limit=10000
        )
        student_ids = {e.student_id for e in enrollments}

        conditions = [AttendanceRecord.section_id == section_id]
        if start_date is not None:
            conditions.append(AttendanceRecord.attendance_date >= start_date)
        if end_date is not None:
            conditions.append(AttendanceRecord.attendance_date <= end_date)

        result = await self.session.execute(
            self.attendance_repo.scoped_query(AttendanceRecord).where(
                and_(*conditions)
            )
        )
        records = result.scalars().all()

        present = sum(1 for r in records if r.status == "present")
        absent = sum(1 for r in records if r.status == "absent")
        late = sum(1 for r in records if r.status == "late")
        excused = sum(1 for r in records if r.status == "excused")
        total = len(records)
        percentage = round((present / total) * 10000) / 100 if total > 0 else 0.0

        return {
            "section_id": section_id,
            "section_name": section.name,
            "class_id": cls.id,
            "class_name": cls.name,
            "total_students": len(student_ids),
            "total_records": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "present_percentage": percentage,
        }

    async def get_attendance_overview(
        self, academic_year_id: int
    ) -> dict:
        year = await self.year_repo.get_by_id(academic_year_id)

        classes, total_classes = await self.class_repo.list(
            year_id=academic_year_id, limit=10000
        )
        class_ids = [c.id for c in classes]

        sections_result = await self.session.execute(
            self.section_repo.scoped_query(Section).where(
                Section.class_id.in_(class_ids)
            )
        )
        sections = sections_result.scalars().all()

        enrollments, _ = await self.enrollment_repo.list(
            academic_year_id=academic_year_id, limit=10000
        )
        student_ids = {e.student_id for e in enrollments}

        result = await self.session.execute(
            self.attendance_repo.scoped_query(AttendanceRecord).where(
                AttendanceRecord.academic_year_id == academic_year_id
            )
        )
        records = result.scalars().all()

        present = sum(1 for r in records if r.status == "present")
        absent = sum(1 for r in records if r.status == "absent")
        late = sum(1 for r in records if r.status == "late")
        excused = sum(1 for r in records if r.status == "excused")
        total = len(records)
        percentage = round((present / total) * 10000) / 100 if total > 0 else 0.0

        return {
            "academic_year_id": academic_year_id,
            "total_classes": total_classes,
            "total_sections": len(sections),
            "total_students": len(student_ids),
            "total_records": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "overall_present_percentage": percentage,
        }