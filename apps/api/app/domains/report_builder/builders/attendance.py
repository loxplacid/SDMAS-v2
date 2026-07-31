from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Enrollment
from app.domains.attendance.models import AttendanceRecord
from app.domains.student.models import Student
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class AttendanceSummaryReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="attendance_summary",
            name="Attendance Summary",
            description="Summary of student attendance with present/absent/late/excused counts and percentages",
            category="attendance",
            allowed_roles=["admin", "teacher", "manager"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="class_id", label="Class", type="select", required=False),
                ReportFilter(key="section_id", label="Section", type="select", required=False),
                ReportFilter(key="from_date", label="From Date", type="date", required=False),
                ReportFilter(key="to_date", label="To Date", type="date", required=False),
            ],
            columns=[
                ReportColumn(key="student_name", header="Student Name"),
                ReportColumn(key="student_number", header="Student Number"),
                ReportColumn(key="class_name", header="Class"),
                ReportColumn(key="section_name", header="Section"),
                ReportColumn(key="present_days", header="Present Days", type="integer"),
                ReportColumn(key="absent_days", header="Absent Days", type="integer"),
                ReportColumn(key="late_days", header="Late Days", type="integer"),
                ReportColumn(key="excused_days", header="Excused Days", type="integer"),
                ReportColumn(key="total_days", header="Total Days", type="integer"),
                ReportColumn(key="percentage", header="Percentage", type="number", format="0.00"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        class_id = params.get("class_id")
        section_id = params.get("section_id")
        from_date = params.get("from_date")
        to_date = params.get("to_date")

        stmt = (
            select(
                AttendanceRecord.student_id,
                AttendanceRecord.class_id,
                AttendanceRecord.section_id,
                func.count().label("total_days"),
                func.sum(case((AttendanceRecord.status == "present", 1), else_=0)).label("present_days"),
                func.sum(case((AttendanceRecord.status == "absent", 1), else_=0)).label("absent_days"),
                func.sum(case((AttendanceRecord.status == "late", 1), else_=0)).label("late_days"),
                func.sum(case((AttendanceRecord.status == "excused", 1), else_=0)).label("excused_days"),
            )
            .where(AttendanceRecord.academic_year_id == academic_year_id)
            .group_by(AttendanceRecord.student_id, AttendanceRecord.class_id, AttendanceRecord.section_id)
        )

        if class_id is not None:
            stmt = stmt.where(AttendanceRecord.class_id == class_id)
        if section_id is not None:
            stmt = stmt.where(AttendanceRecord.section_id == section_id)
        if from_date is not None:
            stmt = stmt.where(AttendanceRecord.attendance_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(AttendanceRecord.attendance_date <= to_date)

        if campus_id is not None:
            stmt = stmt.where(AttendanceRecord.campus_id == campus_id)

        result = await session.execute(stmt)
        rows = result.all()

        student_ids = {r.student_id for r in rows}
        class_ids = {r.class_id for r in rows}
        section_ids = {r.section_id for r in rows}

        students = {}
        if student_ids:
            s_result = await session.execute(
                select(Student).where(Student.id.in_(student_ids))
            )
            students = {s.id: s for s in s_result.scalars().all()}

        classes = {}
        if class_ids:
            c_result = await session.execute(
                select(Class).where(Class.id.in_(class_ids))
            )
            classes = {c.id: c for c in c_result.scalars().all()}

        sections = {}
        if section_ids:
            sec_result = await session.execute(
                select(Section).where(Section.id.in_(section_ids))
            )
            sections = {sec.id: sec for sec in sec_result.scalars().all()}

        return {
            "aggregates": rows,
            "students": students,
            "classes": classes,
            "sections": sections,
        }

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        rows = []
        for r in data["aggregates"]:
            student = data["students"].get(r.student_id)
            cls = data["classes"].get(r.class_id)
            section = data["sections"].get(r.section_id)
            total = r.total_days
            present = r.present_days or 0
            percentage = round((present / total) * 100, 2) if total > 0 else 0.0

            rows.append({
                "student_name": f"{student.first_name} {student.last_name}" if student else "",
                "student_number": student.student_number if student else "",
                "class_name": cls.name if cls else "",
                "section_name": section.name if section else "",
                "present_days": present,
                "absent_days": r.absent_days or 0,
                "late_days": r.late_days or 0,
                "excused_days": r.excused_days or 0,
                "total_days": total,
                "percentage": percentage,
            })

        rows.sort(key=lambda x: x["student_name"])
        return rows

    def build_summary(self, data: Any) -> dict[str, Any]:
        aggregates = data["aggregates"]
        total_present = sum(r.present_days or 0 for r in aggregates)
        total_days = sum(r.total_days for r in aggregates)
        overall_pct = round((total_present / total_days) * 100, 2) if total_days > 0 else 0.0

        return {
            "total_students": len(aggregates),
            "total_present_days": total_present,
            "total_days": total_days,
            "overall_percentage": overall_pct,
        }
