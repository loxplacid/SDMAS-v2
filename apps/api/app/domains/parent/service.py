from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.auth.models import User
from app.domains.parent.models import Guardian
from app.domains.parent.schemas import (
    LinkedChild,
    ParentAcademicRecord,
    ParentAcademicResponse,
    ParentAnnouncement,
    ParentAnnouncementsResponse,
    ParentAttendanceRecord,
    ParentAttendanceResponse,
    ParentAttendanceSummary,
    ParentChildSummary,
    ParentCommunication,
    ParentCommunicationsResponse,
    ParentDashboardResponse,
    ParentDocument,
    ParentDocumentsResponse,
    ParentFeeDue,
    ParentFeesResponse,
    ParentFinancialSummary,
    ParentPayment,
    ParentSubjectGrade,
)
from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


class ParentService:
    """Service layer for the parent portal.

    Every method enforces authorization — the parent user must be a
    linked guardian of the requested student.  Guardian *links* are
    additionally tenant-checked so a parent can never create a
    cross-tenant parent↔student junction.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant

    # ── Authorization Helpers ───────────────────────────────────────

    async def get_linked_student_ids(self, user_id: int) -> list[int]:
        """Return the IDs of all students linked to this parent."""
        result = await self.session.execute(
            select(Guardian.student_id).where(
                Guardian.user_id == user_id,
            )
        )
        return [row[0] for row in result.all()]

    async def verify_child_access(
        self, user_id: int, student_id: int
    ) -> Guardian:
        """Verify a parent is linked to a student. Raises if not."""
        result = await self.session.execute(
            select(Guardian).where(
                Guardian.user_id == user_id,
                Guardian.student_id == student_id,
            )
        )
        guardian = result.scalar_one_or_none()
        if not guardian:
            raise NotFoundError("Student not found or not linked to your account")
        return guardian

    async def _get_linked_children(
        self, user_id: int
    ) -> list[LinkedChild]:
        """Get all linked children with guardian metadata."""
        result = await self.session.execute(
            select(Guardian, Student)
            .join(Student, Guardian.student_id == Student.id)
            .where(Guardian.user_id == user_id)
        )
        children: list[LinkedChild] = []
        for guardian, student in result.all():
            children.append(
                LinkedChild(
                    id=student.id,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    student_number=student.student_number,
                    email=student.email,
                    status=student.status,
                    relationship=guardian.relationship,
                    is_primary=guardian.is_primary,
                )
            )
        return children

    # ── Link / Unlink ───────────────────────────────────────────────

    async def link_child(
        self, user_id: int, student_id: int, relationship: str = "parent"
    ) -> Guardian:
        """Link a parent user to a student.

        The student must belong to the parent's own campus — a parent
        may never establish a guardian link to a student on another
        campus, which would otherwise grant read access to that
        student's attendance, fees, grades and documents.
        """
        # Verify student exists
        student = await self.session.get(Student, student_id)
        if not student:
            raise NotFoundError("Student not found")

        # Tenant boundary: only link students in the caller's campus
        # (platform operators may link across campuses explicitly).
        # Fail closed: a service instance with no tenant context cannot
        # link at all — unscoped must never imply cross-tenant access.
        if self.tenant is None or not self.tenant.allow_cross_tenant:
            if (
                self.tenant is None
                or not self.tenant.is_tenant_scoped
                or student.campus_id != self.tenant.campus_id
            ):
                raise NotFoundError("Student not found")

        # Check if already linked
        existing = await self.session.execute(
            select(Guardian).where(
                Guardian.user_id == user_id,
                Guardian.student_id == student_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("This child is already linked to your account")

        guardian = Guardian(
            user_id=user_id,
            student_id=student_id,
            relationship=relationship,
            is_primary=True,
            campus_id=student.campus_id or (self.tenant.campus_id if self.tenant else None),
        )
        self.session.add(guardian)
        await self.session.commit()
        await self.session.refresh(guardian)
        logger.info("Parent user %d linked to student %d", user_id, student_id)
        return guardian

    async def unlink_child(self, user_id: int, student_id: int) -> None:
        """Remove a parent-child link."""
        guardian = await self.verify_child_access(user_id, student_id)
        await self.session.delete(guardian)
        await self.session.commit()
        logger.info("Parent user %d unlinked from student %d", user_id, student_id)

    # ── Dashboard ───────────────────────────────────────────────────

    async def get_dashboard(self, user: User) -> ParentDashboardResponse:
        """Get the parent dashboard with aggregated data."""
        children = await self._get_linked_children(user)
        child_ids = [c.id for c in children]

        if not child_ids:
            return ParentDashboardResponse()

        summaries: list[ParentChildSummary] = []
        total_outstanding = 0
        total_paid = 0

        for child in children:
            # Get current enrollment
            enrollment = await self._get_current_enrollment(child.id)

            # Get attendance
            attendance = await self._get_attendance_summary(child.id)

            # Get financial summary
            financial = await self._get_financial_summary(child.id)
            total_outstanding += financial.total_outstanding
            total_paid += financial.total_paid

            summaries.append(
                ParentChildSummary(
                    id=child.id,
                    first_name=child.first_name,
                    last_name=child.last_name,
                    student_number=child.student_number,
                    status=child.status,
                    relationship=child.relationship,
                    class_name=enrollment.class_name if enrollment else None,
                    section_name=enrollment.section_name if enrollment else None,
                    attendance_percentage=attendance.percentage,
                    total_outstanding=financial.total_outstanding,
                    total_paid=financial.total_paid,
                )
            )

        # Get recent announcements sent to parents
        announcements = await self._get_recent_announcements()

        return ParentDashboardResponse(
            children=summaries,
            total_outstanding=total_outstanding,
            total_paid=total_paid,
            recent_announcements=announcements,
        )

    # ── Children List ───────────────────────────────────────────────

    async def get_children(self, user_id: int) -> list[LinkedChild]:
        """Get all linked children."""
        return await self._get_linked_children(user_id)

    async def get_child_detail(self, user: User, student_id: int) -> dict[str, Any]:
        """Get detailed info about a specific child."""
        await self.verify_child_access(user.id, student_id)
        children = await self._get_linked_children(user.id)
        child = next((c for c in children if c.id == student_id), None)
        if not child:
            raise NotFoundError("Student not found")

        attendance = await self._get_attendance_summary(student_id)
        financial = await self._get_financial_summary(student_id)
        enrollment = await self._get_current_enrollment(student_id)

        return {
            "child": child,
            "attendance": attendance,
            "financial": financial,
            "current_enrollment": enrollment,
            "unread_notifications": 0,
        }

    # ── Attendance ──────────────────────────────────────────────────

    async def get_attendance(
        self, user: User, student_id: int, days: int = 90
    ) -> ParentAttendanceResponse:
        """Get attendance data for a child."""
        await self.verify_child_access(user.id, student_id)
        children = await self._get_linked_children(user.id)
        child = next((c for c in children if c.id == student_id), None)
        if not child:
            raise NotFoundError("Student not found")

        summary = await self._get_attendance_summary(student_id, days)

        records = await self._get_recent_attendance_records(student_id, limit=30)
        streak = await self._calculate_streak(student_id)
        days_since = await self._days_since_last_absence(student_id)

        return ParentAttendanceResponse(
            child=child,
            summary=summary,
            records=records,
            current_streak=streak,
            days_since_last_absence=days_since,
        )

    # ── Fees / Payments ─────────────────────────────────────────────

    async def get_fees(
        self, user: User, student_id: int
    ) -> ParentFeesResponse:
        """Get fees, payments, and receipts for a child."""
        await self.verify_child_access(user.id, student_id)
        children = await self._get_linked_children(user.id)
        child = next((c for c in children if c.id == student_id), None)
        if not child:
            raise NotFoundError("Student not found")

        summary = await self._get_financial_summary(student_id)
        dues = await self._get_fee_dues(student_id)
        payments = await self._get_payments(student_id)

        return ParentFeesResponse(
            child=child,
            summary=summary,
            dues=dues,
            payments=payments,
        )

    # ── Academic Performance ────────────────────────────────────────

    async def get_academic(
        self, user: User, student_id: int
    ) -> ParentAcademicResponse:
        """Get academic performance data for a child."""
        await self.verify_child_access(user.id, student_id)
        children = await self._get_linked_children(user.id)
        child = next((c for c in children if c.id == student_id), None)
        if not child:
            raise NotFoundError("Student not found")

        current = await self._get_current_enrollment(student_id)
        history = await self._get_academic_history(student_id)
        grades = await self._get_grades(student_id)
        attendance = await self._get_attendance_summary(student_id)

        return ParentAcademicResponse(
            child=child,
            current_enrollment=current,
            academic_history=history,
            grades=grades,
            attendance_summary=attendance,
        )

    # ── Announcements ───────────────────────────────────────────────

    async def get_announcements(
        self, user: User
    ) -> ParentAnnouncementsResponse:
        """Get school announcements visible to parents."""
        announcements = await self._get_recent_announcements()
        return ParentAnnouncementsResponse(announcements=announcements)

    # ── Documents ───────────────────────────────────────────────────

    async def get_documents(
        self, user: User, student_id: int
    ) -> ParentDocumentsResponse:
        """Get documents for a child."""
        await self.verify_child_access(user.id, student_id)
        children = await self._get_linked_children(user.id)
        child = next((c for c in children if c.id == student_id), None)
        if not child:
            raise NotFoundError("Student not found")

        documents = await self._get_student_documents(student_id)

        return ParentDocumentsResponse(child=child, documents=documents)

    # ── Communications ──────────────────────────────────────────────

    async def get_communications(
        self, user: User
    ) -> ParentCommunicationsResponse:
        """Get communications sent to this parent."""
        comms = await self._get_parent_communications(user.id)
        return ParentCommunicationsResponse(communications=comms)

    # ── Internal Data Helpers ───────────────────────────────────────

    async def _get_current_enrollment(
        self, student_id: int
    ) -> Optional[ParentAcademicRecord]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT ay.name, c.name, s.name, e.status
                       FROM enrollments e
                       LEFT JOIN academic_years ay ON ay.id = e.academic_year_id
                       LEFT JOIN classes c ON c.id = e.class_id
                       LEFT JOIN sections s ON s.id = e.section_id
                       WHERE e.student_id = :sid AND e.status = 'active'
                       ORDER BY e.enrolled_at DESC LIMIT 1"""
                ),
                {"sid": student_id},
            )
            row = result.one_or_none()
            if row:
                return ParentAcademicRecord(
                    academic_year_name=row[0],
                    class_name=row[1],
                    section_name=row[2],
                    status=row[3],
                )
        except Exception as exc:
            logger.debug("Enrollment query failed: %s", exc)
        return None

    async def _get_attendance_summary(
        self, student_id: int, days: int = 365
    ) -> ParentAttendanceSummary:
        try:
            start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
            result = await self.session.execute(
                text(
                    """SELECT COUNT(*),
                              SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END)
                       FROM attendance_records
                       WHERE student_id = :sid AND attendance_date >= :start"""
                ),
                {"sid": student_id, "start": start},
            )
            row = result.one()
            total = row[0] or 0
            present = row[1] or 0
            absent = row[2] or 0
            late = row[3] or 0
            excused = row[4] or 0
            pct = round((present / total * 100), 1) if total > 0 else 0.0
            return ParentAttendanceSummary(
                total=total, present=present, absent=absent,
                late=late, excused=excused, percentage=pct,
            )
        except Exception as exc:
            logger.debug("Attendance summary query failed: %s", exc)
            return ParentAttendanceSummary()

    async def _get_recent_attendance_records(
        self, student_id: int, limit: int = 30
    ) -> list[ParentAttendanceRecord]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT id, attendance_date, status, notes
                       FROM attendance_records
                       WHERE student_id = :sid
                       ORDER BY attendance_date DESC LIMIT :lim"""
                ),
                {"sid": student_id, "lim": limit},
            )
            return [
                ParentAttendanceRecord(
                    id=r[0], attendance_date=str(r[1]),
                    status=r[2], notes=r[3],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Recent attendance query failed: %s", exc)
            return []

    async def _calculate_streak(self, student_id: int) -> int:
        """Count consecutive present days going backwards."""
        try:
            result = await self.session.execute(
                text(
                    """SELECT attendance_date, status
                       FROM attendance_records
                       WHERE student_id = :sid
                       ORDER BY attendance_date DESC"""
                ),
                {"sid": student_id},
            )
            streak = 0
            for row in result.all():
                if row[1] == "present":
                    streak += 1
                else:
                    break
            return streak
        except Exception:
            return 0

    async def _days_since_last_absence(self, student_id: int) -> int:
        try:
            result = await self.session.execute(
                text(
                    """SELECT attendance_date FROM attendance_records
                       WHERE student_id = :sid AND status IN ('absent', 'late')
                       ORDER BY attendance_date DESC LIMIT 1"""
                ),
                {"sid": student_id},
            )
            row = result.one_or_none()
            if row:
                last_absence = datetime.datetime.strptime(
                    str(row[0]), "%Y-%m-%d"
                ).date()
                return (datetime.date.today() - last_absence).days
            return 0
        except Exception:
            return 0

    async def _get_financial_summary(
        self, student_id: int
    ) -> ParentFinancialSummary:
        try:
            result = await self.session.execute(
                text(
                    """SELECT
                        COALESCE(SUM(fd.original_amount), 0),
                        COALESCE(SUM(fd.amount_paid), 0),
                        COALESCE(SUM(fd.original_amount - fd.amount_paid), 0),
                        SUM(CASE WHEN fd.status = 'unpaid' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN fd.status = 'partially_paid' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN fd.status = 'paid' THEN 1 ELSE 0 END)
                       FROM fee_dues fd WHERE fd.student_id = :sid"""
                ),
                {"sid": student_id},
            )
            row = result.one()
            return ParentFinancialSummary(
                total_fees_assigned=row[0],
                total_paid=row[1],
                total_outstanding=row[2],
                unpaid_count=row[3],
                partially_paid_count=row[4],
                paid_count=row[5],
            )
        except Exception as exc:
            logger.debug("Financial summary query failed: %s", exc)
            return ParentFinancialSummary()

    async def _get_fee_dues(
        self, student_id: int
    ) -> list[ParentFeeDue]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT fd.id, ft.name, fd.original_amount, fd.amount_paid,
                              (fd.original_amount - fd.amount_paid), fd.due_date, fd.status
                       FROM fee_dues fd
                       LEFT JOIN fee_structures fs ON fs.id = fd.fee_structure_id
                       LEFT JOIN fee_types ft ON ft.id = fs.fee_type_id
                       WHERE fd.student_id = :sid
                       ORDER BY fd.due_date ASC NULLS LAST"""
                ),
                {"sid": student_id},
            )
            return [
                ParentFeeDue(
                    id=r[0], fee_type_name=r[1],
                    original_amount=r[2], amount_paid=r[3],
                    balance=r[4],
                    due_date=str(r[5]) if r[5] else None,
                    status=r[6],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Fee dues query failed: %s", exc)
            return []

    async def _get_payments(
        self, student_id: int
    ) -> list[ParentPayment]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT id, amount, payment_date, payment_method,
                              receipt_number, created_at
                       FROM payments WHERE student_id = :sid
                       ORDER BY created_at DESC LIMIT 30"""
                ),
                {"sid": student_id},
            )
            return [
                ParentPayment(
                    id=r[0], amount=r[1],
                    payment_date=str(r[2]) if r[2] else None,
                    payment_method=r[3],
                    receipt_number=r[4],
                    created_at=str(r[5]),
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Payments query failed: %s", exc)
            return []

    async def _get_academic_history(
        self, student_id: int
    ) -> list[ParentAcademicRecord]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT ay.name, c.name, s.name, e.status
                       FROM enrollments e
                       LEFT JOIN academic_years ay ON ay.id = e.academic_year_id
                       LEFT JOIN classes c ON c.id = e.class_id
                       LEFT JOIN sections s ON s.id = e.section_id
                       WHERE e.student_id = :sid
                       ORDER BY e.enrolled_at DESC"""
                ),
                {"sid": student_id},
            )
            return [
                ParentAcademicRecord(
                    academic_year_name=r[0], class_name=r[1],
                    section_name=r[2], status=r[3],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Academic history query failed: %s", exc)
            return []

    async def _get_grades(
        self, student_id: int
    ) -> list[ParentSubjectGrade]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT sub.name, gr.grade, gr.score, gr.remarks
                       FROM grades gr
                       LEFT JOIN subjects sub ON sub.id = gr.subject_id
                       WHERE gr.student_id = :sid
                       ORDER BY gr.created_at DESC"""
                ),
                {"sid": student_id},
            )
            return [
                ParentSubjectGrade(
                    subject_name=r[0], grade=r[1],
                    score=r[2], remarks=r[3],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Grades query failed: %s", exc)
            return []

    async def _get_recent_announcements(
        self, limit: int = 10
    ) -> list[ParentAnnouncement]:
        try:
            # Announcements are campus-scoped: a parent only sees
            # announcements from their own campus (plus system-wide
            # announcements whose campus_id is NULL).
            conditions = [
                "cm.message_type IN ('announcement', 'parent')",
                "cm.status = 'sent'",
            ]
            params: dict[str, Any] = {"lim": limit}
            if self.tenant is not None and self.tenant.is_tenant_scoped:
                conditions.append(
                    "(cm.campus_id IS NULL OR cm.campus_id = :campus_id)"
                )
                params["campus_id"] = self.tenant.campus_id
            elif self.tenant is None or not self.tenant.allow_cross_tenant:
                # Default-deny for unscoped non-platform callers.
                conditions.append("cm.campus_id IS NULL")

            result = await self.session.execute(
                text(
                    """SELECT cm.id, cm.subject, cm.body, cm.priority, cm.created_at, u.display_name
                       FROM communication_messages cm
                       LEFT JOIN users u ON u.id = cm.sender_id
                       WHERE """
                    + " AND ".join(conditions)
                    + "\n                       ORDER BY cm.created_at DESC\n                       LIMIT :lim"
                ),
                params,
            )
            return [
                ParentAnnouncement(
                    id=r[0], title=r[1], body=r[2],
                    priority=r[3], created_at=r[4], sender_name=r[5],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Announcements query failed: %s", exc)
            return []

    async def _get_student_documents(
        self, student_id: int
    ) -> list[ParentDocument]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT d.id, d.filename, d.mime_type, d.file_size, d.created_at, dc.name
                       FROM documents d
                       LEFT JOIN document_categories dc ON dc.id = d.category_id
                       WHERE d.student_id = :sid
                       ORDER BY d.created_at DESC"""
                ),
                {"sid": student_id},
            )
            return [
                ParentDocument(
                    id=r[0], filename=r[1], mime_type=r[2],
                    file_size=r[3], created_at=r[4], category_name=r[5],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Documents query failed: %s", exc)
            return []

    async def _get_parent_communications(
        self, user_id: int, limit: int = 20
    ) -> list[ParentCommunication]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT cm.id, cm.subject, cm.body, cm.message_type,
                              cm.status, cm.created_at, u.display_name
                       FROM communication_messages cm
                       JOIN message_recipients mr ON mr.message_id = cm.id
                       LEFT JOIN users u ON u.id = cm.sender_id
                       WHERE mr.recipient_type = 'user' AND mr.recipient_id = :uid
                       ORDER BY cm.created_at DESC
                       LIMIT :lim"""
                ),
                {"uid": user_id, "lim": limit},
            )
            return [
                ParentCommunication(
                    id=r[0], subject=r[1], body=r[2],
                    message_type=r[3], status=r[4],
                    created_at=r[5], sender_name=r[6],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Communications query failed: %s", exc)
            return []
