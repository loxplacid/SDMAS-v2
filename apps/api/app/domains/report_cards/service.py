from __future__ import annotations

import datetime
import logging
from typing import Optional, Sequence

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Term,
)
from app.domains.academic_ops.models import GradeRecord
from app.domains.attendance.models import AttendanceRecord
from app.domains.report_cards.schemas import (
    AttendanceSummaryOut,
    ClassMarksheet,
    ClassMarksheetRow,
    MarksheetCell,
    MarksheetSubject,
    ReportCardSubject,
    ReportCardTerm,
    StudentReportCard,
)
from app.domains.student.models import Student

logger = logging.getLogger(__name__)


class ReportCardService:
    """Aggregates grade records, GPA, attendance and teacher remarks for
    per-student report cards and per-class marksheets.

    Data sources
    ------------
    - Grade records: ``academic_ops.models.GradeRecord`` (joined to
      ``Subject`` / ``Term`` via the enrollment of the student).
    - Attendance: ``attendance.models.AttendanceRecord`` — summary counts
      scoped to the academic year (or term) date range.
    - Teacher remarks: the ``remarks`` column on grade records.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Lookups ──────────────────────────────────────────────────────

    async def _get_student(self, student_id: int) -> Student:
        student = await self.session.get(Student, student_id)
        if not student:
            raise NotFoundError(f"Student {student_id} not found")
        return student

    async def _get_year(self, academic_year_id: int) -> AcademicYear:
        year = await self.session.get(AcademicYear, academic_year_id)
        if not year:
            raise NotFoundError(f"Academic year {academic_year_id} not found")
        return year

    async def _get_class(self, class_id: int) -> Class:
        cls = await self.session.get(Class, class_id)
        if not cls:
            raise NotFoundError(f"Class {class_id} not found")
        return cls

    async def _get_term(self, term_id: Optional[int]) -> Optional[Term]:
        if term_id is None:
            return None
        term = await self.session.get(Term, term_id)
        if not term:
            raise NotFoundError(f"Term {term_id} not found")
        return term

    async def _get_enrollment(
        self, student_id: int, academic_year_id: int
    ) -> Enrollment:
        result = await self.session.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.academic_year_id == academic_year_id,
            )
        )
        enrollment = result.scalars().first()
        if not enrollment:
            raise NotFoundError(
                f"Student {student_id} has no enrollment in academic year {academic_year_id}"
            )
        return enrollment

    # ── Grade records ────────────────────────────────────────────────

    async def _grade_records(
        self,
        enrollment_id: int,
        term_id: Optional[int] = None,
    ) -> list[GradeRecord]:
        conditions: list = [
            GradeRecord.enrollment_id == enrollment_id,
            GradeRecord.status == "active",
        ]
        if term_id is not None:
            conditions.append(GradeRecord.term_id == term_id)
        result = await self.session.execute(
            select(GradeRecord).where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def _subject_map(self, subject_ids: set[int]) -> dict[int, Subject]:
        if not subject_ids:
            return {}
        result = await self.session.execute(
            select(Subject).where(Subject.id.in_(subject_ids))
        )
        return {s.id: s for s in result.scalars().all()}

    async def _term_map(self, term_ids: set[int]) -> dict[int, Term]:
        if not term_ids:
            return {}
        result = await self.session.execute(
            select(Term).where(Term.id.in_(term_ids))
        )
        return {t.id: t for t in result.scalars().all()}

    # ── Attendance ───────────────────────────────────────────────────

    async def _attendance_summaries(
        self,
        student_ids: Sequence[int],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> dict[int, AttendanceSummaryOut]:
        """Batch attendance summaries for many students in one query.

        Avoids the per-student N+1 pattern when building a class
        marksheet.
        """
        result: dict[int, AttendanceSummaryOut] = {}
        if not student_ids:
            return result
        try:
            conditions: list = [AttendanceRecord.student_id.in_(student_ids)]
            if start_date:
                conditions.append(AttendanceRecord.attendance_date >= start_date)
            if end_date:
                conditions.append(AttendanceRecord.attendance_date <= end_date)
            rows = (
                await self.session.execute(
                    select(AttendanceRecord.student_id, AttendanceRecord.status)
                    .where(and_(*conditions))
                )
            ).all()
            counts: dict[int, dict[str, int]] = {}
            for sid, status in rows:
                bucket = counts.setdefault(sid, {"total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0})
                bucket["total"] += 1
                if status in bucket:
                    bucket[status] += 1
            for sid, b in counts.items():
                total = b["total"]
                pct = round((b["present"] / total * 100), 1) if total > 0 else 0.0
                result[sid] = AttendanceSummaryOut(
                    total=total,
                    present=b["present"],
                    absent=b["absent"],
                    late=b["late"],
                    excused=b["excused"],
                    percentage=pct,
                )
        except Exception as exc:  # noqa: BLE001 — attendance is optional enrichment
            logger.debug("Batch attendance summary failed: %s", exc)
        return result

    async def _attendance_summary(
        self,
        student_id: int,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> AttendanceSummaryOut:
        """Count attendance records for a student within a date window."""
        try:
            conditions: list = [AttendanceRecord.student_id == student_id]
            if start_date:
                conditions.append(AttendanceRecord.attendance_date >= start_date)
            if end_date:
                conditions.append(AttendanceRecord.attendance_date <= end_date)

            result = await self.session.execute(
                select(
                    AttendanceRecord.id,
                    AttendanceRecord.status,
                ).where(and_(*conditions))
            )
            rows = result.all()
            total = len(rows)
            present = sum(1 for _, st in rows if st == "present")
            absent = sum(1 for _, st in rows if st == "absent")
            late = sum(1 for _, st in rows if st == "late")
            excused = sum(1 for _, st in rows if st == "excused")
            pct = round((present / total * 100), 1) if total > 0 else 0.0
            return AttendanceSummaryOut(
                total=total,
                present=present,
                absent=absent,
                late=late,
                excused=excused,
                percentage=pct,
            )
        except Exception as exc:  # noqa: BLE001 — attendance is optional enrichment
            logger.debug("Attendance summary failed: %s", exc)
            return AttendanceSummaryOut()

    def _date_window(
        self,
        year: AcademicYear,
        term: Optional[Term],
    ) -> tuple[Optional[str], Optional[str]]:
        """ISO date window (start, end) for the year, narrowed by term."""
        if term is not None:
            return term.start_date or None, term.end_date or None
        start = year.start_date.isoformat() if year.start_date else None
        end = year.end_date.isoformat() if year.end_date else None
        return start, end

    # ── Report card ──────────────────────────────────────────────────

    async def get_student_report_card(
        self,
        student_id: int,
        academic_year_id: int,
        term_id: Optional[int] = None,
    ) -> StudentReportCard:
        student = await self._get_student(student_id)
        year = await self._get_year(academic_year_id)
        term = await self._get_term(term_id)
        enrollment = await self._get_enrollment(student_id, academic_year_id)

        records = await self._grade_records(enrollment.id, term_id)
        subject_ids = {r.subject_id for r in records}
        term_ids = {r.term_id for r in records if r.term_id is not None}
        subjects = await self._subject_map(subject_ids)
        terms = await self._term_map(term_ids)

        # Group records by term.
        grouped: dict[Optional[int], list[GradeRecord]] = {}
        for r in records:
            grouped.setdefault(r.term_id, []).append(r)

        start_date, end_date = self._date_window(year, term)
        attendance = await self._attendance_summary(
            student.id, start_date, end_date
        )

        def _subject_sort_key(gr: GradeRecord) -> str:
            subj = subjects.get(gr.subject_id)
            return subj.name if subj else ""

        card_terms: list[ReportCardTerm] = []
        all_percentages: list[float] = []
        all_gpas: list[float] = []
        remarks: list[str] = []

        for term_key, grp in sorted(
            grouped.items(),
            key=lambda kv: (kv[0] is None, kv[0] or 0),
        ):
            term_obj = terms.get(term_key) if term_key is not None else None
            term_name = term_obj.name if term_obj else "General"

            subject_lines: list[ReportCardSubject] = []
            total = 0.0
            max_total = 0
            gpas: list[float] = []
            for gr in sorted(grp, key=_subject_sort_key):
                subj = subjects.get(gr.subject_id)
                if not subj:
                    continue
                total += gr.marks_obtained or 0
                max_total += gr.max_marks or 100
                if gr.grade_point is not None:
                    gpas.append(float(gr.grade_point))
                if gr.remarks and gr.remarks.strip():
                    remarks.append(gr.remarks.strip())
                subject_lines.append(
                    ReportCardSubject(
                        subject_id=subj.id,
                        subject_name=subj.name,
                        subject_code=subj.code,
                        marks_obtained=gr.marks_obtained,
                        max_marks=gr.max_marks,
                        grade=gr.grade,
                        grade_point=gr.grade_point,
                        remarks=gr.remarks,
                    )
                )

            pct = round((total / max_total * 100), 1) if max_total > 0 else None
            gpa = round(sum(gpas) / len(gpas), 2) if gpas else None
            if pct is not None:
                all_percentages.append(pct)
            if gpa is not None:
                all_gpas.append(gpa)

            card_terms.append(
                ReportCardTerm(
                    term_id=term_key,
                    term_name=term_name,
                    subjects=subject_lines,
                    total_marks=round(total, 2),
                    total_max_marks=max_total,
                    percentage=pct,
                    grade_point_average=gpa,
                )
            )

        overall_pct = (
            round(sum(all_percentages) / len(all_percentages), 1)
            if all_percentages
            else None
        )
        overall_gpa = (
            round(sum(all_gpas) / len(all_gpas), 2) if all_gpas else None
        )

        cls = await self.session.get(Class, enrollment.class_id) if enrollment.class_id else None
        section = await self.session.get(Section, enrollment.section_id) if enrollment.section_id else None

        return StudentReportCard(
            student_id=student.id,
            student_name=f"{student.first_name} {student.last_name}",
            student_number=student.student_number,
            class_name=cls.name if cls else None,
            section_name=section.name if section else None,
            academic_year_name=year.name,
            term_filter=term.name if term else None,
            terms=card_terms,
            overall_percentage=overall_pct,
            overall_grade_point_average=overall_gpa,
            attendance=attendance,
            teacher_remarks=remarks[:20],
        )

    # ── Class marksheet ──────────────────────────────────────────────

    async def get_class_marksheet(
        self,
        class_id: int,
        academic_year_id: int,
        term_id: Optional[int] = None,
    ) -> ClassMarksheet:
        cls = await self._get_class(class_id)
        year = await self._get_year(academic_year_id)
        term = await self._get_term(term_id)

        # Enrolled students for the class/year.
        result = await self.session.execute(
            select(Enrollment).where(
                Enrollment.class_id == class_id,
                Enrollment.academic_year_id == academic_year_id,
            )
        )
        enrollments = list(result.scalars().all())
        if not enrollments:
            return ClassMarksheet(
                class_id=class_id,
                class_name=cls.name,
                academic_year_name=year.name,
                term_filter=term.name if term else None,
            )

        student_ids = {e.student_id for e in enrollments}
        enrollment_ids = {e.id for e in enrollments}

        students_result = await self.session.execute(
            select(Student).where(Student.id.in_(student_ids))
        )
        students = {s.id: s for s in students_result.scalars().all()}

        # Grade records for all enrolled students (optionally one term).
        gr_conditions: list = [GradeRecord.enrollment_id.in_(enrollment_ids)]
        if term_id is not None:
            gr_conditions.append(GradeRecord.term_id == term_id)
        gr_result = await self.session.execute(
            select(GradeRecord).where(and_(*gr_conditions))
        )
        grade_records = list(gr_result.scalars().all())

        subject_ids = {r.subject_id for r in grade_records}
        subjects = await self._subject_map(subject_ids)
        subject_list = [
            MarksheetSubject(id=s.id, name=s.name, code=s.code)
            for s in sorted(subjects.values(), key=lambda x: x.name)
        ]

        # group records by (enrollment_id, subject_id)
        by_enrollment_subject: dict[tuple[int, int], GradeRecord] = {}
        for r in grade_records:
            key = (r.enrollment_id, r.subject_id)
            if key not in by_enrollment_subject or (
                r.term_id is not None
                and by_enrollment_subject[key].term_id is None
            ):
                by_enrollment_subject[key] = r

        start_date, end_date = self._date_window(year, term)

        # One batched attendance query for the whole class (avoids N+1).
        attendance_map = await self._attendance_summaries(
            list(student_ids), start_date, end_date
        )

        def _student_sort_key(e: Enrollment) -> tuple[str, str]:
            student = students.get(e.student_id)
            if student is None:
                return ("", "")
            return (student.first_name.lower(), student.last_name.lower())

        rows: list[ClassMarksheetRow] = []
        for e in sorted(enrollments, key=_student_sort_key):
            student = students.get(e.student_id)
            if not student:
                continue

            cells: list[MarksheetCell] = []
            total = 0.0
            max_total = 0
            gpas: list[float] = []
            for subj in subject_list:
                gr = by_enrollment_subject.get((e.id, subj.id))
                if gr is None:
                    cells.append(
                        MarksheetCell(
                            subject_id=subj.id,
                            subject_name=subj.name,
                            subject_code=subj.code,
                        )
                    )
                    continue
                total += gr.marks_obtained or 0
                max_total += gr.max_marks or 100
                if gr.grade_point is not None:
                    gpas.append(float(gr.grade_point))
                cells.append(
                    MarksheetCell(
                        subject_id=subj.id,
                        subject_name=subj.name,
                        subject_code=subj.code,
                        marks_obtained=gr.marks_obtained,
                        max_marks=gr.max_marks,
                        grade=gr.grade,
                        grade_point=gr.grade_point,
                    )
                )

            pct = round((total / max_total * 100), 1) if max_total > 0 else None
            gpa = round(sum(gpas) / len(gpas), 2) if gpas else None
            attendance = attendance_map.get(student.id) or AttendanceSummaryOut()

            rows.append(
                ClassMarksheetRow(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    student_number=student.student_number,
                    subjects=cells,
                    total_marks=round(total, 2),
                    max_marks=max_total,
                    percentage=pct,
                    grade_point_average=gpa,
                    attendance_percentage=attendance.percentage,
                )
            )

        return ClassMarksheet(
            class_id=class_id,
            class_name=cls.name,
            academic_year_name=year.name,
            term_filter=term.name if term else None,
            subjects=subject_list,
            rows=rows,
        )
