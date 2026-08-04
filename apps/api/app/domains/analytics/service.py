"""Analytics service using efficient database-side aggregation.

All analytics queries avoid N+1 patterns by using SQL GROUP BY / aggregate
functions and returning only required columns.
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    and_,
    case,
    func,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Section,
    Enrollment,
    Teacher,
    Subject,
    Term,
    TeacherAssignment,
)
from app.domains.attendance.models import AttendanceRecord
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.student.models import Student


class AnalyticsService:
    """Read-only analytics queries, all via database aggregation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    async def get_overview(self, campus_id: Optional[int] = None) -> dict:
        """Combined high-level overview for the executive dashboard.

        Pass ``campus_id`` to scope every metric to a single tenant
        (used by the command center). ``None`` returns school-wide
        numbers for backward compatibility.
        """

        # Student counts
        student_q = select(
            func.count(Student.id),
            func.sum(case((Student.status == "active", 1), else_=0)),
            func.sum(case((Student.status == "inactive", 1), else_=0)),
        )
        if campus_id is not None:
            student_q = student_q.where(Student.campus_id == campus_id)
        student_counts = await self.session.execute(student_q)
        total_s, active_s, inactive_s = student_counts.one()
        total_s = total_s or 0
        active_s = active_s or 0
        inactive_s = inactive_s or 0

        # Current active academic year
        active_year_q = select(AcademicYear).where(AcademicYear.status == "active")
        if campus_id is not None:
            active_year_q = active_year_q.where(AcademicYear.campus_id == campus_id)
        active_year_result = await self.session.execute(
            active_year_q.limit(1)
        )
        active_year = active_year_result.scalar_one_or_none()

        # Academic structure counts — one round-trip via scalar subqueries.
        # (A plain multi-table select would cross-join the tables and
        # inflate (or zero) the counts, so each count is its own subquery.)
        def _count(model):
            inner = select(func.count(model.id))
            if campus_id is not None:
                inner = inner.where(model.campus_id == campus_id)
            return inner.scalar_subquery()

        counts_result = await self.session.execute(
            select(
                _count(Class).label("classes"),
                _count(Section).label("sections"),
                _count(Teacher).label("teachers"),
                _count(Subject).label("subjects"),
            )
        )
        row = counts_result.one()
        total_classes = row.classes or 0
        total_sections = row.sections or 0
        total_teachers = row.teachers or 0
        total_subjects = row.subjects or 0

        # Overall attendance percentage
        att_q = select(
            func.count(AttendanceRecord.id),
            func.sum(
                case(
                    (AttendanceRecord.status == "present", 1), else_=0
                )
            ),
        )
        if campus_id is not None:
            att_q = att_q.where(AttendanceRecord.campus_id == campus_id)
        att_result = await self.session.execute(att_q)
        total_att, present_att = att_result.one()
        total_att = total_att or 0
        present_att = present_att or 0
        att_pct = (
            round((present_att / total_att) * 10000) / 100
            if total_att > 0
            else 0.0
        )

        # Financial totals (across all years)
        finance_q = select(
            func.coalesce(func.sum(FeeDue.original_amount), 0),
            func.coalesce(func.sum(FeeDue.amount_paid), 0),
        )
        if campus_id is not None:
            finance_q = finance_q.where(FeeDue.campus_id == campus_id)
        finance_result = await self.session.execute(finance_q)
        total_fees, total_paid = finance_result.one()
        outstanding = total_fees - total_paid
        coll_pct = (
            round((total_paid / total_fees) * 10000) / 100
            if total_fees > 0
            else 0.0
        )

        # Low attendance students (below 90%)
        low_att_count = await self._count_low_attendance_students(90, campus_id=campus_id)

        # Unpaid/partially paid counts
        status_q = select(
            func.sum(
                case((FeeDue.status == "unpaid", 1), else_=0)
            ),
            func.sum(
                case(
                    (FeeDue.status == "partially_paid", 1), else_=0
                )
            ),
        )
        if campus_id is not None:
            status_q = status_q.where(FeeDue.campus_id == campus_id)
        status_query = await self.session.execute(status_q)
        unpaid, partial = status_query.one()

        return {
            "total_students": total_s,
            "active_students": active_s,
            "inactive_students": inactive_s,
            "current_academic_year": active_year.name if active_year else None,
            "total_classes": total_classes or 0,
            "total_sections": total_sections or 0,
            "total_teachers": total_teachers or 0,
            "total_subjects": total_subjects or 0,
            "overall_attendance_percentage": att_pct,
            "total_collected": total_paid,
            "total_outstanding": outstanding,
            "collection_percentage": coll_pct,
            "low_attendance_count": low_att_count,
            "unpaid_count": unpaid or 0,
            "partially_paid_count": partial or 0,
        }

    # ------------------------------------------------------------------
    # Attendance Analytics
    # ------------------------------------------------------------------

    async def get_attendance_overview(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> dict:
        conditions = self._attendance_conditions(
            academic_year_id, class_id, section_id, campus_id
        )
        query = select(
            func.count(AttendanceRecord.id),
            func.sum(
                case(
                    (AttendanceRecord.status == "present", 1), else_=0
                )
            ),
            func.sum(
                case(
                    (AttendanceRecord.status == "absent", 1), else_=0
                )
            ),
            func.sum(
                case((AttendanceRecord.status == "late", 1), else_=0)
            ),
            func.sum(
                case(
                    (AttendanceRecord.status == "excused", 1), else_=0
                )
            ),
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        total, present, absent, late, excused = result.one()
        total = total or 0
        present = present or 0
        absent = absent or 0
        late = late or 0
        excused = excused or 0
        pct = (
            round((present / total) * 10000) / 100 if total > 0 else 0.0
        )

        return {
            "total_records": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "attendance_percentage": pct,
        }

    async def get_attendance_trends(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        granularity: str = "daily",
        campus_id: Optional[int] = None,
    ) -> dict:
        conditions = self._attendance_conditions(
            academic_year_id, class_id, section_id, campus_id
        )

        date_col = AttendanceRecord.attendance_date
        query = select(
            date_col,
            func.count(AttendanceRecord.id),
            func.sum(
                case(
                    (AttendanceRecord.status == "present", 1), else_=0
                )
            ),
            func.sum(
                case(
                    (AttendanceRecord.status == "absent", 1), else_=0
                )
            ),
            func.sum(
                case((AttendanceRecord.status == "late", 1), else_=0)
            ),
            func.sum(
                case(
                    (AttendanceRecord.status == "excused", 1), else_=0
                )
            ),
        )
        if conditions:
            query = query.where(and_(*conditions))
        query = query.group_by(date_col).order_by(date_col)

        result = await self.session.execute(query)
        rows = result.all()

        if granularity == "monthly":
            aggregated: dict[str, dict] = {}
            for row in rows:
                month_key = row[0][:7]  # "2026-03"
                if month_key not in aggregated:
                    aggregated[month_key] = {
                        "date": month_key,
                        "present": 0,
                        "absent": 0,
                        "late": 0,
                        "excused": 0,
                        "total": 0,
                    }
                aggregated[month_key]["present"] += row[2] or 0
                aggregated[month_key]["absent"] += row[3] or 0
                aggregated[month_key]["late"] += row[4] or 0
                aggregated[month_key]["excused"] += row[5] or 0
                aggregated[month_key]["total"] += row[1] or 0
            trend = list(aggregated.values())
            granularity = "monthly"
        elif granularity == "weekly":
            aggregated = {}
            for row in rows:
                try:
                    d = datetime.date.fromisoformat(row[0])
                    week_key = d.isocalendar()[1]
                    year_key = d.year
                    key = f"{year_key}-W{week_key:02d}"
                except (ValueError, TypeError):
                    key = row[0]
                if key not in aggregated:
                    aggregated[key] = {
                        "date": key,
                        "present": 0,
                        "absent": 0,
                        "late": 0,
                        "excused": 0,
                        "total": 0,
                    }
                aggregated[key]["present"] += row[2] or 0
                aggregated[key]["absent"] += row[3] or 0
                aggregated[key]["late"] += row[4] or 0
                aggregated[key]["excused"] += row[5] or 0
                aggregated[key]["total"] += row[1] or 0
            trend = list(aggregated.values())
            granularity = "weekly"
        else:
            trend = [
                {
                    "date": r[0],
                    "present": r[2] or 0,
                    "absent": r[3] or 0,
                    "late": r[4] or 0,
                    "excused": r[5] or 0,
                    "total": r[1] or 0,
                }
                for r in rows
            ]
            granularity = "daily"

        return {"trend": trend, "granularity": granularity}

    async def get_attendance_class_comparison(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        query = (
            select(
                Class.id,
                Class.name,
                func.count(AttendanceRecord.id),
                func.sum(
                    case(
                        (AttendanceRecord.status == "present", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.status == "absent", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.status == "late", 1), else_=0
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.status == "excused", 1),
                        else_=0,
                    )
                ),
            )
            .select_from(AttendanceRecord)
            .join(Class, AttendanceRecord.class_id == Class.id)
        )
        if academic_year_id is not None:
            query = query.where(
                AttendanceRecord.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            query = query.where(AttendanceRecord.campus_id == campus_id)
        query = query.group_by(Class.id, Class.name).order_by(Class.name)

        result = await self.session.execute(query)
        rows = result.all()

        output = []
        for r in rows:
            total = r[2] or 0
            present = r[3] or 0
            pct = (
                round((present / total) * 10000) / 100
                if total > 0
                else 0.0
            )
            output.append(
                {
                    "class_id": r[0],
                    "class_name": r[1],
                    "total_records": total,
                    "present": present,
                    "absent": r[4] or 0,
                    "late": r[5] or 0,
                    "excused": r[6] or 0,
                    "attendance_percentage": pct,
                }
            )
        return output

    async def get_attendance_section_comparison(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                AttendanceRecord.academic_year_id == academic_year_id
            )
        if class_id is not None:
            conditions.append(AttendanceRecord.class_id == class_id)
        if campus_id is not None:
            conditions.append(AttendanceRecord.campus_id == campus_id)

        query = (
            select(
                Section.id,
                Section.name,
                Class.name,
                func.count(AttendanceRecord.id),
                func.sum(
                    case(
                        (AttendanceRecord.status == "present", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.status == "absent", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.status == "late", 1), else_=0
                    )
                ),
                func.sum(
                    case(
                        (AttendanceRecord.status == "excused", 1),
                        else_=0,
                    )
                ),
            )
            .select_from(AttendanceRecord)
            .join(Section, AttendanceRecord.section_id == Section.id)
            .join(Class, Section.class_id == Class.id)
        )
        if conditions:
            query = query.where(and_(*conditions))
        query = query.group_by(
            Section.id, Section.name, Class.name
        ).order_by(Class.name, Section.name)

        result = await self.session.execute(query)
        rows = result.all()

        output = []
        for r in rows:
            total = r[3] or 0
            present = r[4] or 0
            pct = (
                round((present / total) * 10000) / 100
                if total > 0
                else 0.0
            )
            output.append(
                {
                    "section_id": r[0],
                    "section_name": r[1],
                    "class_name": r[2],
                    "total_records": total,
                    "present": present,
                    "absent": r[5] or 0,
                    "late": r[6] or 0,
                    "excused": r[7] or 0,
                    "attendance_percentage": pct,
                }
            )
        return output

    async def get_low_attendance_students(
        self,
        threshold: int = 90,
        academic_year_id: Optional[int] = None,
        min_records: int = 1,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        """Identify students with attendance percentage below threshold."""
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                AttendanceRecord.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            conditions.append(AttendanceRecord.campus_id == campus_id)

        subq_stmt = select(
            AttendanceRecord.student_id,
            func.count(AttendanceRecord.id).label("total_records"),
            func.sum(
                case(
                    (AttendanceRecord.status == "present", 1),
                    else_=0,
                )
            ).label("present_count"),
        )
        if conditions:
            subq_stmt = subq_stmt.where(and_(*conditions))
        subq = subq_stmt.group_by(AttendanceRecord.student_id).subquery()

        query = select(
            Student.id,
            Student.first_name,
            Student.last_name,
            Student.student_number,
            subq.c.total_records,
            subq.c.present_count,
        ).join(subq, Student.id == subq.c.student_id)

        result = await self.session.execute(query)
        rows = result.all()

        output = []
        for r in rows:
            total = r[4] or 0
            present = r[5] or 0
            if total < min_records:
                continue
            pct = (
                round((present / total) * 10000) / 100
                if total > 0
                else 0.0
            )
            if pct < threshold:
                output.append(
                    {
                        "student_id": r[0],
                        "student_name": f"{r[1]} {r[2]}",
                        "student_number": r[3],
                        "total_records": total,
                        "present_count": present,
                        "attendance_percentage": pct,
                        "threshold": threshold,
                    }
                )

        output.sort(key=lambda x: x["attendance_percentage"])
        return output

    async def get_term_attendance(
        self,
        term_id: int,
    ) -> Optional[dict]:
        """Get attendance analytics for a specific term."""
        term_result = await self.session.execute(
            select(Term).where(Term.id == term_id)
        )
        term = term_result.scalar_one_or_none()
        if term is None:
            return None

        conditions = [
            AttendanceRecord.attendance_date >= term.start_date,
            AttendanceRecord.attendance_date <= term.end_date,
        ]

        query = select(
            func.count(AttendanceRecord.id),
            func.sum(
                case(
                    (AttendanceRecord.status == "present", 1), else_=0
                )
            ),
            func.sum(
                case(
                    (AttendanceRecord.status == "absent", 1), else_=0
                )
            ),
            func.sum(
                case((AttendanceRecord.status == "late", 1), else_=0)
            ),
            func.sum(
                case(
                    (AttendanceRecord.status == "excused", 1), else_=0
                )
            ),
        ).where(and_(*conditions))

        result = await self.session.execute(query)
        total, present, absent, late, excused = result.one()
        total = total or 0
        present = present or 0
        pct = (
            round((present / total) * 10000) / 100 if total > 0 else 0.0
        )

        return {
            "term_id": term.id,
            "term_name": term.name,
            "total_records": total,
            "present": present,
            "absent": absent or 0,
            "late": late or 0,
            "excused": excused or 0,
            "attendance_percentage": pct,
        }

    async def get_all_term_attendance(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        """Get attendance analytics for all terms via single batch query."""
        conditions = []
        if academic_year_id is not None:
            conditions.append(Term.academic_year_id == academic_year_id)
        if campus_id is not None:
            conditions.append(Term.campus_id == campus_id)

        terms_result = await self.session.execute(
            select(Term).where(and_(*conditions)) if conditions else select(Term)
        )
        terms = terms_result.scalars().all()

        if not terms:
            return []

        min_date = min(t.start_date for t in terms)
        max_date = max(t.end_date for t in terms)

        term_case_expr = case(
            *[
                (
                    and_(
                        AttendanceRecord.attendance_date >= t.start_date,
                        AttendanceRecord.attendance_date <= t.end_date,
                    ),
                    t.id,
                )
                for t in terms
            ],
            else_=None,
        )

        query = select(
            term_case_expr.label("term_id"),
            func.count(AttendanceRecord.id).label("total"),
            func.sum(case((AttendanceRecord.status == "present", 1), else_=0)).label("present"),
            func.sum(case((AttendanceRecord.status == "absent", 1), else_=0)).label("absent"),
            func.sum(case((AttendanceRecord.status == "late", 1), else_=0)).label("late"),
            func.sum(case((AttendanceRecord.status == "excused", 1), else_=0)).label("excused"),
        ).where(
            AttendanceRecord.attendance_date >= min_date,
            AttendanceRecord.attendance_date <= max_date,
        ).group_by(term_case_expr)

        result = await self.session.execute(query)
        rows = result.all()

        term_map = {t.id: t for t in terms}
        results = []
        for row in rows:
            t = term_map.get(row.term_id)
            if t is None:
                continue
            total = row.total or 0
            present = row.present or 0
            pct = round((present / total) * 10000) / 100 if total > 0 else 0.0
            results.append({
                "term_id": t.id,
                "term_name": t.name,
                "total_records": total,
                "present": present,
                "absent": row.absent or 0,
                "late": row.late or 0,
                "excused": row.excused or 0,
                "attendance_percentage": pct,
            })

        seen_ids = {r["term_id"] for r in results}
        for t in terms:
            if t.id not in seen_ids:
                results.append({
                    "term_id": t.id,
                    "term_name": t.name,
                    "total_records": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "excused": 0,
                    "attendance_percentage": 0.0,
                })

        return results

    # ------------------------------------------------------------------
    # Financial Analytics
    # ------------------------------------------------------------------

    async def get_finance_overview(
        self, academic_year_id: Optional[int] = None, campus_id: Optional[int] = None
    ) -> dict:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                FeeDue.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            conditions.append(FeeDue.campus_id == campus_id)

        query = select(
            func.coalesce(func.sum(FeeDue.original_amount), 0),
            func.coalesce(func.sum(FeeDue.amount_paid), 0),
            func.sum(
                case((FeeDue.status == "unpaid", 1), else_=0)
            ),
            func.sum(
                case(
                    (FeeDue.status == "partially_paid", 1), else_=0
                )
            ),
            func.sum(
                case((FeeDue.status == "paid", 1), else_=0)
            ),
            func.count(func.distinct(FeeDue.student_id)),
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        total_fees, total_paid, unpaid_c, partial_c, paid_c, total_students = (
            result.one()
        )
        total_fees = total_fees or 0
        total_paid = total_paid or 0
        unpaid_c = unpaid_c or 0
        partial_c = partial_c or 0
        paid_c = paid_c or 0
        outstanding = total_fees - total_paid
        coll_pct = (
            round((total_paid / total_fees) * 10000) / 100
            if total_fees > 0
            else 0.0
        )

        # Count students with outstanding
        out_query = select(func.count(func.distinct(FeeDue.student_id)))
        out_conditions = [
            FeeDue.amount_paid < FeeDue.original_amount
        ]
        if academic_year_id is not None:
            out_conditions.append(
                FeeDue.academic_year_id == academic_year_id
            )
        out_result = await self.session.execute(
            out_query.where(and_(*out_conditions))
        )
        students_with_outstanding = out_result.scalar() or 0

        return {
            "total_fees_amount": total_fees,
            "total_collected": total_paid,
            "total_outstanding": outstanding,
            "collection_percentage": coll_pct,
            "students_with_outstanding": students_with_outstanding,
            "fully_paid_students": paid_c or 0,
            "partially_paid_students": partial_c or 0,
            "unpaid_students": unpaid_c or 0,
        }

    async def get_collection_trends(
        self,
        academic_year_id: Optional[int] = None,
        granularity: str = "daily",
        campus_id: Optional[int] = None,
    ) -> dict:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                Payment.payment_date.isnot(None)
            )
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)

        date_col = Payment.payment_date
        query = select(
            date_col,
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
        ).where(Payment.payment_date.isnot(None))

        if conditions:
            query = query.where(and_(*conditions))
        query = (
            query.group_by(date_col)
            .order_by(date_col)
        )

        result = await self.session.execute(query)
        rows = result.all()

        if granularity == "monthly":
            aggregated: dict[str, dict] = {}
            for r in rows:
                key = r[0][:7] if r[0] else "unknown"
                if key not in aggregated:
                    aggregated[key] = {"date": key, "amount": 0, "count": 0}
                aggregated[key]["amount"] += r[1] or 0
                aggregated[key]["count"] += r[2] or 0
            trend = list(aggregated.values())
        else:
            trend = [
                {
                    "date": r[0] or "",
                    "amount": r[1] or 0,
                    "count": r[2] or 0,
                }
                for r in rows
            ]

        return {"trend": trend, "granularity": granularity}

    async def get_fee_type_collection(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                FeeDue.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            conditions.append(FeeDue.campus_id == campus_id)

        query = (
            select(
                FeeType.id,
                FeeType.name,
                func.coalesce(func.sum(FeeDue.original_amount), 0),
                func.coalesce(func.sum(FeeDue.amount_paid), 0),
            )
            .select_from(FeeDue)
            .join(
                FeeStructure,
                FeeDue.fee_structure_id == FeeStructure.id,
            )
            .join(FeeType, FeeStructure.fee_type_id == FeeType.id)
        )
        if conditions:
            query = query.where(and_(*conditions))
        query = query.group_by(FeeType.id, FeeType.name).order_by(
            FeeType.name
        )

        result = await self.session.execute(query)
        rows = result.all()

        output = []
        for r in rows:
            expected = r[2] or 0
            collected = r[3] or 0
            outstanding = expected - collected
            pct = (
                round((collected / expected) * 10000) / 100
                if expected > 0
                else 0.0
            )
            output.append(
                {
                    "fee_type_id": r[0],
                    "fee_type_name": r[1],
                    "total_expected": expected,
                    "total_collected": collected,
                    "outstanding": outstanding,
                    "collection_percentage": pct,
                }
            )
        return output

    async def get_class_fee_collection(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                FeeDue.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            conditions.append(FeeDue.campus_id == campus_id)

        query = (
            select(
                Class.id,
                Class.name,
                func.coalesce(func.sum(FeeDue.original_amount), 0),
                func.coalesce(func.sum(FeeDue.amount_paid), 0),
            )
            .select_from(FeeDue)
            .join(Student, FeeDue.student_id == Student.id)
            .join(
                Enrollment,
                and_(
                    Enrollment.student_id == Student.id,
                    Enrollment.academic_year_id
                    == FeeDue.academic_year_id,
                ),
            )
            .join(Class, Enrollment.class_id == Class.id)
        )
        if conditions:
            query = query.where(and_(*conditions))
        query = query.group_by(Class.id, Class.name).order_by(Class.name)

        result = await self.session.execute(query)
        rows = result.all()

        output = []
        for r in rows:
            expected = r[2] or 0
            collected = r[3] or 0
            outstanding = expected - collected
            pct = (
                round((collected / expected) * 10000) / 100
                if expected > 0
                else 0.0
            )
            output.append(
                {
                    "class_id": r[0],
                    "class_name": r[1],
                    "total_expected": expected,
                    "total_collected": collected,
                    "outstanding": outstanding,
                    "collection_percentage": pct,
                }
            )
        return output

    async def get_payment_method_distribution(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                Payment.payment_date.isnot(None)
            )
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)

        query = select(
            Payment.payment_method,
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0),
        ).where(Payment.payment_method.isnot(None))

        if conditions:
            query = query.where(and_(*conditions))
        query = query.group_by(Payment.payment_method).order_by(
            Payment.payment_method
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "payment_method": r[0] or "unknown",
                "transaction_count": r[1] or 0,
                "total_amount": r[2] or 0,
            }
            for r in rows
        ]

    async def get_fee_status_distribution(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                FeeDue.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            conditions.append(FeeDue.campus_id == campus_id)

        query = select(
            FeeDue.status,
            func.count(FeeDue.id),
            func.coalesce(func.sum(FeeDue.original_amount), 0),
        )
        if conditions:
            query = query.where(and_(*conditions))
        query = query.group_by(FeeDue.status)

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "status": r[0] or "unknown",
                "count": r[1] or 0,
                "total_amount": r[2] or 0,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Student Analytics
    # ------------------------------------------------------------------

    async def get_student_overview(self, campus_id: Optional[int] = None) -> dict:
        student_q = select(
            func.count(Student.id),
            func.sum(
                case(
                    (Student.status == "active", 1), else_=0
                )
            ),
            func.sum(
                case(
                    (Student.status == "inactive", 1), else_=0
                )
            ),
        )
        if campus_id is not None:
            student_q = student_q.where(Student.campus_id == campus_id)
        result = await self.session.execute(student_q)

        total, active, inactive = result.one()
        return {
            "total_students": total or 0,
            "active_students": active or 0,
            "inactive_students": inactive or 0,
        }

    async def get_students_by_class(
        self,
        academic_year_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = [Enrollment.status == "active"]
        if academic_year_id is not None:
            conditions.append(
                Enrollment.academic_year_id == academic_year_id
            )
        if campus_id is not None:
            conditions.append(Class.campus_id == campus_id)

        query = (
            select(
                Class.id,
                Class.name,
                func.count(Enrollment.student_id),
            )
            .join(Class, Enrollment.class_id == Class.id)
            .where(and_(*conditions))
            .group_by(Class.id, Class.name)
            .order_by(Class.name)
        )

        result = await self.session.execute(query)
        rows = result.all()
        return [
            {
                "class_id": r[0],
                "class_name": r[1],
                "student_count": r[2] or 0,
            }
            for r in rows
        ]

    async def get_students_by_section(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list[dict]:
        conditions = [Enrollment.status == "active"]
        if academic_year_id is not None:
            conditions.append(
                Enrollment.academic_year_id == academic_year_id
            )
        if class_id is not None:
            conditions.append(Enrollment.class_id == class_id)
        if campus_id is not None:
            conditions.append(Section.campus_id == campus_id)

        query = (
            select(
                Section.id,
                Section.name,
                Class.name,
                func.count(Enrollment.student_id),
            )
            .join(Section, Enrollment.section_id == Section.id)
            .join(Class, Section.class_id == Class.id)
            .where(and_(*conditions))
            .group_by(Section.id, Section.name, Class.name)
            .order_by(Class.name, Section.name)
        )

        result = await self.session.execute(query)
        rows = result.all()
        return [
            {
                "section_id": r[0],
                "section_name": r[1],
                "class_name": r[2],
                "student_count": r[3] or 0,
            }
            for r in rows
        ]

    async def get_enrollment_trends(self, campus_id: Optional[int] = None) -> list[dict]:
        conditions = []
        if campus_id is not None:
            conditions.append(AcademicYear.campus_id == campus_id)

        query = (
            select(
                AcademicYear.id,
                AcademicYear.name,
                func.count(Enrollment.student_id),
            )
            .join(
                AcademicYear,
                Enrollment.academic_year_id == AcademicYear.id,
            )
            .group_by(AcademicYear.id, AcademicYear.name)
            .order_by(AcademicYear.start_date)
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        rows = result.all()
        return [
            {
                "academic_year_id": r[0],
                "academic_year_name": r[1],
                "enrollment_count": r[2] or 0,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Academic Analytics
    # ------------------------------------------------------------------

    async def get_academic_overview(self, campus_id: Optional[int] = None) -> dict:
        def _scoped_count(model):
            q = select(func.count(model.id))
            if campus_id is not None:
                q = q.where(model.campus_id == campus_id)
            return q

        active_year = await self.session.execute(
            select(AcademicYear)
            .where(AcademicYear.status == "active")
            .limit(1)
        )
        year = active_year.scalar_one_or_none()

        # Separate queries to avoid cartesian product from unrelated tables
        cls_c = (await self.session.execute(_scoped_count(Class))).scalar() or 0
        sec_c = (await self.session.execute(_scoped_count(Section))).scalar() or 0
        tch_c = (await self.session.execute(_scoped_count(Teacher))).scalar() or 0
        sub_c = (await self.session.execute(_scoped_count(Subject))).scalar() or 0
        term_c = (await self.session.execute(_scoped_count(Term))).scalar() or 0

        return {
            "active_academic_year": year.name if year else None,
            "total_classes": cls_c or 0,
            "total_sections": sec_c or 0,
            "total_teachers": tch_c or 0,
            "total_subjects": sub_c or 0,
            "total_terms": term_c or 0,
        }

    async def get_teacher_workload(self, campus_id: Optional[int] = None) -> list[dict]:
        # Load teachers with their assignments eagerly
        teachers_q = select(Teacher).order_by(Teacher.first_name, Teacher.last_name)
        if campus_id is not None:
            teachers_q = teachers_q.where(Teacher.campus_id == campus_id)
        teachers_result = await self.session.execute(teachers_q)
        teachers = teachers_result.scalars().all()

        if not teachers:
            return []

        teacher_ids = [t.id for t in teachers]

        # Batch load assignments with related data
        assignments_result = await self.session.execute(
            select(
                TeacherAssignment.teacher_id,
                Subject.name,
                Class.name,
            )
            .outerjoin(Subject, TeacherAssignment.subject_id == Subject.id)
            .outerjoin(Class, TeacherAssignment.class_id == Class.id)
            .where(TeacherAssignment.teacher_id.in_(teacher_ids))
        )
        assign_rows = assignments_result.all()

        # Group by teacher_id
        from collections import defaultdict
        teacher_assignments: dict[int, dict] = defaultdict(
            lambda: {"subjects": set(), "classes": set(), "count": 0}
        )
        for row in assign_rows:
            tid = row[0]
            if row[1]:
                teacher_assignments[tid]["subjects"].add(row[1])
            if row[2]:
                teacher_assignments[tid]["classes"].add(row[2])
            teacher_assignments[tid]["count"] += 1

        output = []
        for teacher in teachers:
            ta = teacher_assignments[teacher.id]
            output.append(
                {
                    "teacher_id": teacher.id,
                    "teacher_name": f"{teacher.first_name} {teacher.last_name}",
                    "employee_number": teacher.employee_number,
                    "assignment_count": ta["count"],
                    "subjects": sorted(ta["subjects"]),
                    "classes": sorted(ta["classes"]),
                }
            )
        return output

    async def get_subject_distribution(self, campus_id: Optional[int] = None) -> list[dict]:
        query = (
            select(
                Subject.id,
                Subject.name,
                Subject.code,
                func.count(TeacherAssignment.id),
            )
            .outerjoin(
                TeacherAssignment,
                Subject.id == TeacherAssignment.subject_id,
            )
            .group_by(Subject.id, Subject.name, Subject.code)
            .order_by(Subject.name)
        )
        if campus_id is not None:
            query = query.where(Subject.campus_id == campus_id)

        result = await self.session.execute(query)
        rows = result.all()
        return [
            {
                "subject_id": r[0],
                "subject_name": r[1],
                "subject_code": r[2],
                "assignment_count": r[3] or 0,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _attendance_conditions(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        campus_id: Optional[int] = None,
    ) -> list:
        conditions = []
        if academic_year_id is not None:
            conditions.append(
                AttendanceRecord.academic_year_id == academic_year_id
            )
        if class_id is not None:
            conditions.append(
                AttendanceRecord.class_id == class_id
            )
        if section_id is not None:
            conditions.append(
                AttendanceRecord.section_id == section_id
            )
        if campus_id is not None:
            conditions.append(AttendanceRecord.campus_id == campus_id)
        return conditions

    async def _count_low_attendance_students(
        self, threshold: int = 90, campus_id: Optional[int] = None
    ) -> int:
        """Count students below attendance threshold using efficient query."""
        subq = (
            select(
                AttendanceRecord.student_id,
                func.count(AttendanceRecord.id).label("total_records"),
                func.sum(
                    case(
                        (AttendanceRecord.status == "present", 1),
                        else_=0,
                    )
                ).label("present_count"),
            )
            .group_by(AttendanceRecord.student_id)
            .subquery()
        )

        # Scope the student set to the campus before counting, so a
        # tenant never counts another campus's students.
        from app.domains.student.models import Student as StudentModel
        inner = select(subq.c.student_id)
        if campus_id is not None:
            inner = inner.join(
                StudentModel, StudentModel.id == subq.c.student_id
            ).where(StudentModel.campus_id == campus_id)

        count_query = select(func.count()).select_from(
            inner.where(subq.c.total_records >= 1).where(
                (subq.c.present_count * 100.0 / subq.c.total_records) < threshold
            ).subquery()
        )

        result = await self.session.execute(count_query)
        return result.scalar() or 0
