"""Class 360 aggregation service.

Composes existing academic, attendance, fee, workflow, and audit data into a
single class-level 360 view.  Follows the ``student_360`` convention of raw
SQL aggregation (read-only, best-effort with graceful fallbacks) while adding
tenant scoping via ``campus_id`` so no cross-campus data ever leaks.

Each ``_get_*`` helper is isolated: a missing table or unexpected query error
degrades to an empty default instead of failing the whole view.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.class_360.schemas import (
    AcademicPerformanceItem,
    ActivityItem,
    AttendanceSummary,
    Class360Response,
    ClassIdentity,
    FeeSummary,
    SectionSummary,
    StudentAttentionItem,
    SubjectSummary,
    TeacherAssignmentItem,
    WorkflowItem,
)
from app.domains.academic.models import Class
from app.domains.academic.repository import ClassRepository

logger = logging.getLogger(__name__)

_ATTENTION_LIMIT = 10


class Class360Service:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_class_360(
        self, class_id: int, campus_id: Optional[int] = None
    ) -> Class360Response:
        class_repo = ClassRepository(self.session)
        cls = await class_repo.get_by_id(class_id)

        identity = await self._get_identity(cls)
        sections = await self._get_sections(class_id, campus_id)
        attendance = await self._get_attendance(class_id, campus_id)
        fees = await self._get_fees(class_id, campus_id)
        teachers = await self._get_teachers(class_id, campus_id)
        subjects = await self._get_subjects(class_id, campus_id)
        attention = await self._get_students_requiring_attention(
            class_id, campus_id
        )
        performance = await self._get_academic_performance(class_id, campus_id)
        workflows = await self._get_pending_workflows(class_id, campus_id)
        activity = await self._get_recent_activity(class_id, campus_id)

        return Class360Response(
            identity=identity,
            sections=sections,
            student_count=sum(s.student_count for s in sections),
            attendance=attendance,
            fees=fees,
            teachers=teachers,
            subjects=subjects,
            students_requiring_attention=attention,
            academic_performance=performance,
            pending_workflows=workflows,
            recent_activity=activity,
        )

    async def _get_identity(self, cls: Class) -> ClassIdentity:
        year_name = None
        if cls.academic_year_id:
            try:
                result = await self.session.execute(
                    text(
                        "SELECT name FROM academic_years WHERE id = :yid"
                    ),
                    {"yid": cls.academic_year_id},
                )
                row = result.one_or_none()
                if row:
                    year_name = row[0]
            except Exception as exc:
                logger.debug("Academic year lookup failed: %s", exc)
        return ClassIdentity(
            id=cls.id,
            name=cls.name,
            academic_year_id=cls.academic_year_id,
            academic_year_name=year_name,
            status=cls.status,
            campus_id=cls.campus_id,
        )

    def _scope(self, campus_id: Optional[int], table: str) -> str:
        """Return an AND clause fragment pinning rows to the campus.

        ``table`` is the SQL table/alias whose ``campus_id`` column is
        compared — multi-table queries must qualify the column or the
        scope clause becomes ambiguous.  ``None`` (platform admin /
        legacy mode) means no restriction.
        """
        if not campus_id:
            return ""
        return (
            f"AND ({table}.campus_id = :campus_id "
            f"OR {table}.campus_id IS NULL)"
        )

    async def _get_sections(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[SectionSummary]:
        try:
            scope = self._scope(campus_id, "s")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT s.id, s.name, s.status,
                           COUNT(e.id) AS student_count
                    FROM sections s
                    LEFT JOIN enrollments e
                           ON e.section_id = s.id AND e.status = 'active'
                    WHERE s.class_id = :cid
                    {scope}
                    GROUP BY s.id
                    ORDER BY s.name
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            return [
                SectionSummary(
                    id=r[0], name=r[1], status=r[2], student_count=r[3] or 0
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Sections query failed: %s", exc)
            return []

    async def _get_attendance(
        self, class_id: int, campus_id: Optional[int]
    ) -> AttendanceSummary:
        try:
            today = datetime.date.today()
            start = today - datetime.timedelta(days=90)
            scope = self._scope(campus_id, "attendance_records")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS present,
                        SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) AS absent,
                        SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late,
                        SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) AS excused
                    FROM attendance_records
                    WHERE class_id = :cid AND attendance_date >= :start
                    {scope}
                    """
                ),
                {"cid": class_id, "start": start.isoformat(), "campus_id": campus_id},
            )
            row = result.one()
            total = row[0] or 0
            present = row[1] or 0
            absent = row[2] or 0
            late = row[3] or 0
            excused = row[4] or 0
            pct = round((present / total * 100), 1) if total > 0 else 0.0
            return AttendanceSummary(
                total=total,
                present=present,
                absent=absent,
                late=late,
                excused=excused,
                percentage=pct,
            )
        except Exception as exc:
            logger.debug("Attendance summary query failed: %s", exc)
            return AttendanceSummary()

    async def _get_fees(
        self, class_id: int, campus_id: Optional[int]
    ) -> FeeSummary:
        try:
            scope = self._scope(campus_id, "fd")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT
                        COALESCE(SUM(fd.original_amount), 0) AS assigned,
                        COALESCE(SUM(fd.amount_paid), 0) AS collected,
                        COALESCE(SUM(fd.original_amount - fd.amount_paid), 0) AS outstanding,
                        SUM(CASE WHEN (fd.original_amount - fd.amount_paid) > 0
                                 THEN 1 ELSE 0 END) AS with_outstanding
                    FROM fee_dues fd
                    JOIN enrollments e ON e.student_id = fd.student_id
                       AND e.status = 'active'
                    WHERE e.class_id = :cid
                    {scope}
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            row = result.one()
            return FeeSummary(
                total_assigned=row[0] or 0,
                total_collected=row[1] or 0,
                total_outstanding=row[2] or 0,
                students_with_outstanding=row[3] or 0,
            )
        except Exception as exc:
            logger.debug("Fee summary query failed: %s", exc)
            return FeeSummary()

    async def _get_teachers(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[TeacherAssignmentItem]:
        try:
            scope = self._scope(campus_id, "ta")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT t.id, t.first_name, t.last_name,
                           ta.subject_id, s.name AS subject_name
                    FROM teacher_assignments ta
                    JOIN teachers t ON t.id = ta.teacher_id
                    LEFT JOIN subjects s ON s.id = ta.subject_id
                    WHERE ta.class_id = :cid AND ta.status = 'active'
                    {scope}
                    ORDER BY t.first_name, t.last_name
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            return [
                TeacherAssignmentItem(
                    teacher_id=r[0],
                    teacher_name=f"{r[1]} {r[2]}".strip(),
                    subject_id=r[3],
                    subject_name=r[4],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Teachers query failed: %s", exc)
            return []

    async def _get_subjects(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[SubjectSummary]:
        try:
            scope = self._scope(campus_id, "ta")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT DISTINCT s.id, s.name, s.code
                    FROM subjects s
                    JOIN teacher_assignments ta ON ta.subject_id = s.id
                    WHERE ta.class_id = :cid AND ta.status = 'active'
                    {scope}
                    ORDER BY s.name
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            return [
                SubjectSummary(id=r[0], name=r[1], code=r[2]) for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Subjects query failed: %s", exc)
            return []

    async def _get_students_requiring_attention(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[StudentAttentionItem]:
        try:
            today = datetime.date.today()
            start = today - datetime.timedelta(days=90)
            scope = self._scope(campus_id, "e")
            # Students with low attendance (below 75% over last 90 days)
            result = await self.session.execute(
                text(
                    f"""
                    SELECT e.student_id, st.student_number,
                           st.first_name, st.last_name,
                           SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) AS present,
                           COUNT(ar.id) AS total
                    FROM enrollments e
                    JOIN students st ON st.id = e.student_id
                    LEFT JOIN attendance_records ar
                           ON ar.student_id = e.student_id
                          AND ar.attendance_date >= :start
                    WHERE e.class_id = :cid AND e.status = 'active'
                    {scope}
                    GROUP BY e.student_id
                    """
                ),
                {
                    "cid": class_id,
                    "start": start.isoformat(),
                    "campus_id": campus_id,
                },
            )
            attention: dict[int, StudentAttentionItem] = {}
            for r in result.all():
                sid = r[0]
                present, total = r[4] or 0, r[5] or 0
                pct = round((present / total * 100), 1) if total > 0 else 100.0
                if pct < 75.0:
                    attention[sid] = StudentAttentionItem(
                        student_id=sid,
                        student_number=r[1],
                        full_name=f"{r[2]} {r[3]}".strip(),
                        reason="Low attendance",
                        attendance_percentage=pct,
                    )

            # Students with outstanding fees in this class
            result = await self.session.execute(
                text(
                    f"""
                    SELECT fd.student_id, st.student_number,
                           st.first_name, st.last_name,
                           COALESCE(SUM(fd.original_amount - fd.amount_paid), 0) AS outstanding
                    FROM fee_dues fd
                    JOIN enrollments e ON e.student_id = fd.student_id
                       AND e.status = 'active'
                    JOIN students st ON st.id = fd.student_id
                    WHERE e.class_id = :cid
                    {scope}
                    GROUP BY fd.student_id
                    HAVING COALESCE(SUM(fd.original_amount - fd.amount_paid), 0) > 0
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            for r in result.all():
                sid = r[0]
                item = attention.get(sid)
                if item is None:
                    attention[sid] = StudentAttentionItem(
                        student_id=sid,
                        student_number=r[1],
                        full_name=f"{r[2]} {r[3]}".strip(),
                        reason="Outstanding fees",
                        outstanding=r[4] or 0,
                    )
                else:
                    item.reason += " + outstanding fees"
                    item.outstanding = r[4] or 0

            items = sorted(
                attention.values(),
                key=lambda i: (i.reason != "Low attendance", -i.outstanding),
            )
            return items[:_ATTENTION_LIMIT]
        except Exception as exc:
            logger.debug("Requiring-attention query failed: %s", exc)
            return []

    async def _get_academic_performance(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[AcademicPerformanceItem]:
        try:
            scope = self._scope(campus_id, "e")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT s.id, s.name,
                           AVG(gr.marks_obtained * 100.0 / NULLIF(gr.max_marks, 0)) AS avg_pct,
                           COUNT(gr.id) AS records
                    FROM grade_records gr
                    JOIN enrollments e ON e.id = gr.enrollment_id
                    JOIN subjects s ON s.id = gr.subject_id
                    WHERE e.class_id = :cid
                    {scope}
                    GROUP BY s.id, s.name
                    ORDER BY s.name
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            return [
                AcademicPerformanceItem(
                    subject_id=r[0],
                    subject_name=r[1],
                    average_percentage=round(r[2], 1) if r[2] is not None else 0.0,
                    records=r[3] or 0,
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Academic performance query failed: %s", exc)
            return []

    async def _get_pending_workflows(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[WorkflowItem]:
        try:
            scope = self._scope(campus_id, "wi")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT wi.id, w.name, wi.entity_type, wi.entity_id,
                           wi.status, ws.name AS step_name, wi.created_at
                    FROM workflow_instances wi
                    JOIN workflows w ON w.id = wi.workflow_id
                    LEFT JOIN workflow_steps ws ON ws.id = wi.current_step_id
                    WHERE wi.entity_type = 'class' AND wi.entity_id = :cid
                      AND wi.status = 'active'
                    {scope}
                    ORDER BY wi.created_at DESC
                    LIMIT 20
                    """
                ),
                {"cid": class_id, "campus_id": campus_id},
            )
            return [
                WorkflowItem(
                    id=r[0],
                    workflow_name=r[1],
                    entity_type=r[2],
                    entity_id=r[3],
                    status=r[4],
                    current_step=r[5],
                    created_at=str(r[6]) if r[6] else "",
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Workflow query failed: %s", exc)
            return []

    async def _get_recent_activity(
        self, class_id: int, campus_id: Optional[int]
    ) -> list[ActivityItem]:
        try:
            scope = self._scope(campus_id, "audit_logs")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT created_at, action, resource_type, user_id, details
                    FROM audit_logs
                    WHERE resource_type IN ('academic', 'class')
                      AND resource_id = :rid
                    {scope}
                    ORDER BY created_at DESC
                    LIMIT 20
                    """
                ),
                {"rid": str(class_id), "campus_id": campus_id},
            )
            return [
                ActivityItem(
                    date=str(r[0]),
                    action=r[1],
                    resource_type=r[2],
                    user_id=r[3],
                    details=r[4],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Recent activity query failed: %s", exc)
            return []
