"""Teacher 360 aggregation service.

Composes existing academic, attendance, leave, workflow, timetable, and audit
data into a single teacher-level 360 view.  Follows the ``student_360`` /
``class_360`` convention of raw SQL aggregation (read-only, best-effort with
graceful fallbacks) while adding tenant scoping via ``campus_id``.

Note: teachers are not directly linked to ``users`` in the current schema, so
leave data is resolved through ``leave_requests.user_id`` when the school
creates user accounts for teachers (1:1 by id is a common convention here).
Where no link exists, leave simply renders empty.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.teacher_360.schemas import (
    ActivityItem,
    AssignedClassItem,
    AttendanceSummary,
    LeaveItem,
    Teacher360Response,
    TeacherProfile,
    TeacherSubjectItem,
    WorkflowItem,
    WorkloadItem,
)
from app.domains.academic.repository import TeacherRepository
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


class Teacher360Service:
    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant

    async def get_teacher_360(
        self, teacher_id: int, campus_id: Optional[int] = None
    ) -> Teacher360Response:
        teacher_repo = TeacherRepository(self.session, self.tenant)
        teacher = await teacher_repo.get_by_id(teacher_id)

        profile = TeacherProfile.model_validate(teacher)
        subjects = await self._get_subjects(teacher_id, campus_id)
        assignments = await self._get_assignments(teacher_id, campus_id)
        attendance = await self._get_attendance(teacher_id, campus_id)
        leave = await self._get_leave(teacher_id, campus_id)
        workload = await self._get_workload(teacher_id, campus_id)
        workflows = await self._get_pending_workflows(teacher_id, campus_id)
        activity = await self._get_recent_activity(teacher_id, campus_id)

        return Teacher360Response(
            profile=profile,
            subjects=subjects,
            assignments=assignments,
            attendance=attendance,
            leave=leave,
            workload=workload,
            pending_workflows=workflows,
            recent_activity=activity,
        )

    def _scope(self, campus_id: Optional[int], table: str) -> str:
        """Return an AND clause fragment pinning rows to the campus.

        ``table`` is the SQL table/alias whose ``campus_id`` column is
        compared — multi-table queries must qualify the column or the
        scope clause becomes ambiguous.  ``None`` (platform admin)
        means no restriction; scoped tenants only see their own campus.

        Legacy rows whose ``campus_id`` is NULL are **never** matched:
        ambiguous ownership must not surface to a scoped tenant
        (fail-closed on NULL campus, same as ``class_360``).
        """
        if not campus_id:
            return ""
        return f"AND {table}.campus_id = :campus_id"

    async def _get_subjects(
        self, teacher_id: int, campus_id: Optional[int]
    ) -> list[TeacherSubjectItem]:
        try:
            scope = self._scope(campus_id, "ta")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT DISTINCT s.id, s.name, s.code
                    FROM subjects s
                    JOIN teacher_assignments ta ON ta.subject_id = s.id
                    WHERE ta.teacher_id = :tid AND ta.status = 'active'
                    {scope}
                    ORDER BY s.name
                    """
                ),
                {"tid": teacher_id, "campus_id": campus_id},
            )
            return [
                TeacherSubjectItem(
                    subject_id=r[0], subject_name=r[1], code=r[2]
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Teacher subjects query failed: %s", exc)
            return []

    async def _get_assignments(
        self, teacher_id: int, campus_id: Optional[int]
    ) -> list[AssignedClassItem]:
        try:
            scope = self._scope(campus_id, "ta")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT ta.id, c.id, c.name, ay.name AS ay_name,
                           s.id AS section_id, s.name AS section_name,
                           sub.name AS subject_name
                    FROM teacher_assignments ta
                    JOIN classes c ON c.id = ta.class_id
                    LEFT JOIN academic_years ay ON ay.id = c.academic_year_id
                    LEFT JOIN subjects sub ON sub.id = ta.subject_id
                    LEFT JOIN sections s ON s.class_id = c.id AND s.status = 'active'
                    WHERE ta.teacher_id = :tid AND ta.status = 'active'
                    {scope}
                    ORDER BY c.name, s.name
                    """
                ),
                {"tid": teacher_id, "campus_id": campus_id},
            )
            return [
                AssignedClassItem(
                    assignment_id=r[0],
                    class_id=r[1],
                    class_name=r[2],
                    academic_year_name=r[3],
                    section_id=r[4],
                    section_name=r[5],
                    subject_name=r[6],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Teacher assignments query failed: %s", exc)
            return []

    async def _get_attendance(
        self, teacher_id: int, campus_id: Optional[int]
    ) -> AttendanceSummary:
        """Attendance recorded across the sections this teacher teaches."""
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
                    WHERE class_id IN (
                        SELECT class_id FROM teacher_assignments
                        WHERE teacher_id = :tid AND status = 'active'
                    )
                    AND attendance_date >= :start
                    {scope}
                    """
                ),
                {"tid": teacher_id, "start": start.isoformat(), "campus_id": campus_id},
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
            logger.debug("Teacher attendance query failed: %s", exc)
            return AttendanceSummary()

    async def _get_leave(
        self, teacher_id: int, campus_id: Optional[int]
    ) -> list[LeaveItem]:
        try:
            scope = self._scope(campus_id, "lr")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT lr.id, lr.leave_type, lr.start_date, lr.end_date,
                           COALESCE(wi.status, 'pending') AS status,
                           lr.duration_days
                    FROM leave_requests lr
                    LEFT JOIN workflow_instances wi ON wi.id = lr.workflow_instance_id
                    WHERE lr.user_id = :tid
                    {scope}
                    ORDER BY lr.start_date DESC
                    LIMIT 20
                    """
                ),
                {"tid": teacher_id, "campus_id": campus_id},
            )
            return [
                LeaveItem(
                    id=r[0],
                    leave_type=r[1],
                    start_date=r[2],
                    end_date=r[3],
                    status=r[4],
                    duration_days=r[5] or 0,
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Teacher leave query failed: %s", exc)
            return []

    async def _get_workload(
        self, teacher_id: int, campus_id: Optional[int]
    ) -> WorkloadItem:
        try:
            scope = self._scope(campus_id, "teacher_assignments")
            # Assigned classes + subjects from teacher_assignments
            result = await self.session.execute(
                text(
                    f"""
                    SELECT COUNT(DISTINCT class_id) AS classes,
                           COUNT(DISTINCT subject_id) AS subjects
                    FROM teacher_assignments
                    WHERE teacher_id = :tid AND status = 'active'
                    {scope}
                    """
                ),
                {"tid": teacher_id, "campus_id": campus_id},
            )
            row = result.one()
            classes = row[0] or 0
            subjects = row[1] or 0

            # Timetable periods (timetable_entries may not exist everywhere)
            periods = 0
            try:
                scope = self._scope(campus_id, "timetable_entries")
                result = await self.session.execute(
                    text(
                        f"""
                        SELECT COUNT(*) FROM timetable_entries
                        WHERE teacher_id = :tid AND status = 'active'
                        {scope}
                        """
                    ),
                    {"tid": teacher_id, "campus_id": campus_id},
                )
                periods = result.scalar() or 0
            except Exception as exc:
                logger.debug("Timetable workload query failed: %s", exc)

            return WorkloadItem(
                assigned_classes=classes,
                subjects=subjects,
                timetable_periods=periods,
            )
        except Exception as exc:
            logger.debug("Workload query failed: %s", exc)
            return WorkloadItem()

    async def _get_pending_workflows(
        self, teacher_id: int, campus_id: Optional[int]
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
                    WHERE wi.entity_type = 'teacher' AND wi.entity_id = :tid
                      AND wi.status = 'active'
                    {scope}
                    ORDER BY wi.created_at DESC
                    LIMIT 20
                    """
                ),
                {"tid": teacher_id, "campus_id": campus_id},
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
            logger.debug("Teacher workflow query failed: %s", exc)
            return []

    async def _get_recent_activity(
        self, teacher_id: int, campus_id: Optional[int]
    ) -> list[ActivityItem]:
        try:
            scope = self._scope(campus_id, "audit_logs")
            result = await self.session.execute(
                text(
                    f"""
                    SELECT created_at, action, resource_type, user_id, details
                    FROM audit_logs
                    WHERE resource_type = 'teacher' AND resource_id = :rid
                    {scope}
                    ORDER BY created_at DESC
                    LIMIT 20
                    """
                ),
                {"rid": str(teacher_id), "campus_id": campus_id},
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
            logger.debug("Teacher activity query failed: %s", exc)
            return []
