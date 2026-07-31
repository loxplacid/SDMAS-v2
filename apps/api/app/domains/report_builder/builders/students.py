from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Enrollment
from app.domains.student.models import Student
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class StudentDirectoryReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="student_directory",
            name="Student Directory",
            description="Directory of all students with enrollment information and guardian details",
            category="student",
            allowed_roles=["admin", "teacher", "manager"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="class_id", label="Class", type="select", required=False),
                ReportFilter(key="section_id", label="Section", type="select", required=False),
                ReportFilter(key="status", label="Status", type="select", required=False),
            ],
            columns=[
                ReportColumn(key="student_number", header="Student Number"),
                ReportColumn(key="first_name", header="First Name"),
                ReportColumn(key="last_name", header="Last Name"),
                ReportColumn(key="class_name", header="Class"),
                ReportColumn(key="section_name", header="Section"),
                ReportColumn(key="gender", header="Gender"),
                ReportColumn(key="date_of_birth", header="Date of Birth"),
                ReportColumn(key="guardian_name", header="Guardian Name"),
                ReportColumn(key="guardian_phone", header="Guardian Phone"),
                ReportColumn(key="status", header="Status"),
                ReportColumn(key="enrollment_date", header="Enrollment Date"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        class_id = params.get("class_id")
        section_id = params.get("section_id")
        status = params.get("status")

        enroll_conditions = [Enrollment.academic_year_id == academic_year_id]
        if class_id is not None:
            enroll_conditions.append(Enrollment.class_id == class_id)
        if section_id is not None:
            enroll_conditions.append(Enrollment.section_id == section_id)
        if status is not None:
            enroll_conditions.append(Enrollment.status == status)
        if campus_id is not None:
            enroll_conditions.append(Enrollment.campus_id == campus_id)

        enroll_result = await session.execute(
            select(Enrollment).where(and_(*enroll_conditions))
        )
        enrollments = enroll_result.scalars().all()

        student_ids = {e.student_id for e in enrollments}
        class_ids = {e.class_id for e in enrollments if e.class_id is not None}
        section_ids = {e.section_id for e in enrollments if e.section_id is not None}

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

        guardian_map: dict[int, dict[str, str]] = {}
        if student_ids:
            try:
                g_result = await session.execute(
                    text(
                        "SELECT g.student_id, g.name, g.contact "
                        "FROM guardians g WHERE g.student_id IN :sids"
                    ),
                    {"sids": tuple(student_ids)},
                )
                for g_row in g_result.all():
                    sid = g_row[0]
                    if sid not in guardian_map:
                        guardian_map[sid] = {"name": "", "contact": ""}
                    if g_row[1]:
                        guardian_map[sid]["name"] = g_row[1]
                    if g_row[2]:
                        guardian_map[sid]["contact"] = g_row[2]
            except Exception:
                pass

        return {
            "enrollments": enrollments,
            "students": students,
            "classes": classes,
            "sections": sections,
            "guardian_map": guardian_map,
        }

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        rows = []
        for e in data["enrollments"]:
            student = data["students"].get(e.student_id)
            cls = data["classes"].get(e.class_id) if e.class_id else None
            section = data["sections"].get(e.section_id) if e.section_id else None
            guardian = data["guardian_map"].get(e.student_id, {})

            rows.append({
                "student_number": student.student_number if student else "",
                "first_name": student.first_name if student else "",
                "last_name": student.last_name if student else "",
                "class_name": cls.name if cls else "",
                "section_name": section.name if section else "",
                "gender": getattr(student, "gender", "") if student else "",
                "date_of_birth": str(student.date_of_birth) if student and student.date_of_birth else "",
                "guardian_name": guardian.get("name", ""),
                "guardian_phone": guardian.get("contact", ""),
                "status": e.status,
                "enrollment_date": e.enrolled_at.isoformat() if e.enrolled_at else "",
            })

        rows.sort(key=lambda x: (x["class_name"], x["section_name"], x["last_name"], x["first_name"]))
        return rows
