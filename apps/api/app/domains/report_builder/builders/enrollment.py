from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Enrollment
from app.domains.student.models import Student
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class EnrollmentSummaryReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="enrollment_summary",
            name="Enrollment Summary",
            description="Enrollment summary grouped by class and section with gender and status breakdown",
            category="student",
            allowed_roles=["admin", "manager"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="class_id", label="Class", type="select", required=False),
            ],
            columns=[
                ReportColumn(key="class_name", header="Class"),
                ReportColumn(key="section_name", header="Section"),
                ReportColumn(key="total_students", header="Total Students", type="integer"),
                ReportColumn(key="male_count", header="Male", type="integer"),
                ReportColumn(key="female_count", header="Female", type="integer"),
                ReportColumn(key="active_count", header="Active", type="integer"),
                ReportColumn(key="withdrawn_count", header="Withdrawn", type="integer"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        class_id = params.get("class_id")

        conditions = [Enrollment.academic_year_id == academic_year_id]
        if class_id is not None:
            conditions.append(Enrollment.class_id == class_id)
        if campus_id is not None:
            conditions.append(Enrollment.campus_id == campus_id)

        enroll_result = await session.execute(
            select(Enrollment).where(and_(*conditions))
        )
        enrollments = enroll_result.scalars().all()

        class_ids = {e.class_id for e in enrollments if e.class_id is not None}
        section_ids = {e.section_id for e in enrollments if e.section_id is not None}
        student_ids = {e.student_id for e in enrollments}

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

        students = {}
        if student_ids:
            s_result = await session.execute(
                select(Student).where(Student.id.in_(student_ids))
            )
            students = {s.id: s for s in s_result.scalars().all()}

        return {
            "enrollments": enrollments,
            "classes": classes,
            "sections": sections,
            "students": students,
        }

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        group_key = lambda e: (e.class_id, e.section_id)
        groups: dict[tuple, dict] = {}

        for e in data["enrollments"]:
            key = group_key(e)
            if key not in groups:
                groups[key] = {
                    "class_id": e.class_id,
                    "section_id": e.section_id,
                    "total": 0,
                    "active": 0,
                    "withdrawn": 0,
                    "student_ids": set(),
                }
            g = groups[key]
            g["total"] += 1
            g["student_ids"].add(e.student_id)
            if e.status == "active":
                g["active"] += 1
            elif e.status == "withdrawn":
                g["withdrawn"] += 1

        rows = []
        for key, g in groups.items():
            cls = data["classes"].get(g["class_id"]) if g["class_id"] else None
            section = data["sections"].get(g["section_id"]) if g["section_id"] else None

            male = 0
            female = 0
            for sid in g["student_ids"]:
                student = data["students"].get(sid)
                gender = getattr(student, "gender", "") if student else ""
                if gender and gender.lower() in ("m", "male"):
                    male += 1
                elif gender and gender.lower() in ("f", "female"):
                    female += 1

            rows.append({
                "class_name": cls.name if cls else "",
                "section_name": section.name if section else "",
                "total_students": g["total"],
                "male_count": male,
                "female_count": female,
                "active_count": g["active"],
                "withdrawn_count": g["withdrawn"],
            })

        rows.sort(key=lambda x: (x["class_name"], x["section_name"]))
        return rows
