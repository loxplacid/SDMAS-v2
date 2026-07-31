from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Enrollment, Subject, Term
from app.domains.student.models import Student
from app.domains.academic_ops.models import GradeRecord, GradingStructure
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class AcademicPerformanceReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="academic_performance",
            name="Academic Performance",
            description="Student academic performance with scores, grades, grade points and remarks",
            category="academic",
            allowed_roles=["admin", "teacher", "manager"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="term_id", label="Term", type="select", required=False),
                ReportFilter(key="class_id", label="Class", type="select", required=False),
                ReportFilter(key="section_id", label="Section", type="select", required=False),
                ReportFilter(key="subject_id", label="Subject", type="select", required=False),
            ],
            columns=[
                ReportColumn(key="student_name", header="Student Name"),
                ReportColumn(key="student_number", header="Student Number"),
                ReportColumn(key="class_name", header="Class"),
                ReportColumn(key="subject_name", header="Subject"),
                ReportColumn(key="term_name", header="Term"),
                ReportColumn(key="score", header="Score", type="number", format="0.00"),
                ReportColumn(key="grade", header="Grade"),
                ReportColumn(key="grade_point", header="Grade Point", type="number", format="0.0"),
                ReportColumn(key="remarks", header="Remarks"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        term_id = params.get("term_id")
        class_id = params.get("class_id")
        section_id = params.get("section_id")
        subject_id = params.get("subject_id")

        conditions = [Enrollment.academic_year_id == academic_year_id]
        if class_id is not None:
            conditions.append(Enrollment.class_id == class_id)
        if section_id is not None:
            conditions.append(Enrollment.section_id == section_id)
        if campus_id is not None:
            conditions.append(Enrollment.campus_id == campus_id)

        enroll_result = await session.execute(
            select(Enrollment).where(and_(*conditions))
        )
        enrollments = enroll_result.scalars().all()
        enrollment_ids = {e.id for e in enrollments}
        student_ids = {e.student_id for e in enrollments}
        class_ids = {e.class_id for e in enrollments if e.class_id is not None}

        if not enrollment_ids:
            return {
                "grade_records": [],
                "students": {},
                "classes": {},
                "subjects": {},
                "terms": {},
            }

        grade_conditions = [GradeRecord.enrollment_id.in_(enrollment_ids)]
        if term_id is not None:
            grade_conditions.append(GradeRecord.term_id == term_id)
        if subject_id is not None:
            grade_conditions.append(GradeRecord.subject_id == subject_id)
        if campus_id is not None:
            grade_conditions.append(GradeRecord.campus_id == campus_id)

        grade_result = await session.execute(
            select(GradeRecord).where(and_(*grade_conditions))
        )
        grade_records = grade_result.scalars().all()

        subject_ids = {g.subject_id for g in grade_records}
        term_ids = {g.term_id for g in grade_records if g.term_id is not None}
        grading_ids = {g.grading_structure_id for g in grade_records if g.grading_structure_id is not None}

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

        subjects = {}
        if subject_ids:
            subj_result = await session.execute(
                select(Subject).where(Subject.id.in_(subject_ids))
            )
            subjects = {s.id: s for s in subj_result.scalars().all()}

        terms = {}
        if term_ids:
            t_result = await session.execute(
                select(Term).where(Term.id.in_(term_ids))
            )
            terms = {t.id: t for t in t_result.scalars().all()}

        grading_structures = {}
        if grading_ids:
            gs_result = await session.execute(
                select(GradingStructure).where(GradingStructure.id.in_(grading_ids))
            )
            grading_structures = {gs.id: gs for gs in gs_result.scalars().all()}

        enrollment_map = {e.id: e for e in enrollments}

        return {
            "grade_records": grade_records,
            "enrollment_map": enrollment_map,
            "students": students,
            "classes": classes,
            "subjects": subjects,
            "terms": terms,
            "grading_structures": grading_structures,
        }

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        rows = []
        for gr in data["grade_records"]:
            enrollment = data["enrollment_map"].get(gr.enrollment_id)
            student = data["students"].get(enrollment.student_id) if enrollment else None
            cls = data["classes"].get(enrollment.class_id) if enrollment and enrollment.class_id else None
            subject = data["subjects"].get(gr.subject_id)
            term = data["terms"].get(gr.term_id) if gr.term_id else None
            grading = data["grading_structures"].get(gr.grading_structure_id) if gr.grading_structure_id else None

            rows.append({
                "student_name": f"{student.first_name} {student.last_name}" if student else "",
                "student_number": student.student_number if student else "",
                "class_name": cls.name if cls else "",
                "subject_name": subject.name if subject else "",
                "term_name": term.name if term else "",
                "score": gr.marks_obtained if gr.marks_obtained is not None else 0.0,
                "grade": gr.grade or (grading.name if grading else ""),
                "grade_point": gr.grade_point,
                "remarks": gr.remarks or "",
            })

        rows.sort(key=lambda x: (x["class_name"], x["student_name"], x["subject_name"]))
        return rows
