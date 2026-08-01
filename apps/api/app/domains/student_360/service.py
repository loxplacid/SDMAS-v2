from __future__ import annotations

import datetime
import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.student_360.schemas import (
    AcademicRecord,
    AttendanceSummary,
    EnrollmentInfo,
    FeeDueItem,
    FinancialSummary,
    GuardianInfo,
    HostelInfo,
    PaymentItem,
    RiskFindingBrief,
    Student360Response,
    StudentHealthInfo,
    StudentIdentity,
    TransportInfo,
)

logger = logging.getLogger(__name__)


class Student360Service:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_student_360(self, student_id: int) -> Student360Response:
        student_repo = StudentRepository(self.session)
        student = await student_repo.get_by_id(student_id)

        identity = StudentIdentity.model_validate(student)

        guardians = await self._get_guardians(student_id)
        contacts = await self._get_contacts(student_id)
        enrollments = await self._get_enrollments(student_id)
        current_enrollment = next(
            (e for e in enrollments if e.status == "active"), None
        )
        attendance = await self._get_attendance_summary(student_id)
        attendance_records = await self._get_recent_attendance(student_id)
        financial = await self._get_financial_summary(student_id)
        fee_dues = await self._get_fee_dues(student_id)
        payments = await self._get_payments(student_id)
        academic_history = await self._get_academic_history(student_id)
        health = await self._get_health_info(student_id)
        transport = await self._get_transport_info(student_id)
        hostel = await self._get_hostel_info(student_id)
        risk_findings = await self._get_risk_findings(student_id)

        return Student360Response(
            identity=identity,
            guardians=guardians,
            contacts=contacts,
            enrollments=enrollments,
            current_enrollment=current_enrollment,
            attendance=attendance,
            attendance_records=attendance_records,
            financial=financial,
            fee_dues=fee_dues,
            payments=payments,
            academic_history=academic_history,
            health=health,
            transport=transport,
            hostel=hostel,
            risk_findings=risk_findings,
        )

    async def _get_guardians(self, student_id: int) -> list[GuardianInfo]:
        try:
            result = await self.session.execute(
                text(
                    "SELECT g.name, g.relationship, g.contact "
                    "FROM guardians g WHERE g.student_id = :sid"
                ),
                {"sid": student_id},
            )
            rows = result.all()
            return [
                GuardianInfo(name=r[0], relationship=r[1], contact=r[2])
                for r in rows
            ]
        except Exception as exc:
            logger.debug("No guardians table or query failed: %s", exc)
            return []

    async def _get_contacts(self, student_id: int) -> list:
        try:
            result = await self.session.execute(
                text(
                    "SELECT sc.type, sc.value, sc.is_primary "
                    "FROM student_contacts sc WHERE sc.student_id = :sid"
                ),
                {"sid": student_id},
            )
            return [
                {"type": r[0], "value": r[1], "is_primary": r[2]}
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("No student_contacts table: %s", exc)
            return []

    async def _get_enrollments(self, student_id: int) -> list[EnrollmentInfo]:
        try:
            result = await self.session.execute(
                text(
                    """
                    SELECT e.id, e.academic_year_id, ay.name AS ay_name,
                           e.class_id, c.name AS class_name,
                           e.section_id, s.name AS section_name,
                           e.status, e.enrolled_at
                    FROM enrollments e
                    LEFT JOIN academic_years ay ON ay.id = e.academic_year_id
                    LEFT JOIN classes c ON c.id = e.class_id
                    LEFT JOIN sections s ON s.id = e.section_id
                    WHERE e.student_id = :sid
                    ORDER BY e.enrolled_at DESC
                    """
                ),
                {"sid": student_id},
            )
            return [
                EnrollmentInfo(
                    id=r[0],
                    academic_year_id=r[1],
                    academic_year_name=r[2],
                    class_id=r[3],
                    class_name=r[4],
                    section_id=r[5],
                    section_name=r[6],
                    status=r[7],
                    enrolled_at=str(r[8]) if r[8] else "",
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Enrollment query failed: %s", exc)
            return []

    async def _get_attendance_summary(
        self, student_id: int
    ) -> AttendanceSummary:
        try:
            today = datetime.date.today()
            start = today - datetime.timedelta(days=90)
            result = await self.session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS present,
                        SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) AS absent,
                        SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) AS late,
                        SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END) AS excused
                    FROM attendance_records
                    WHERE student_id = :sid
                      AND attendance_date >= :start
                    """
                ),
                {"sid": student_id, "start": start.isoformat()},
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

    async def _get_recent_attendance(self, student_id: int) -> list[dict]:
        try:
            result = await self.session.execute(
                text(
                    """
                    SELECT ar.id, ar.attendance_date, ar.status, ar.notes
                    FROM attendance_records ar
                    WHERE ar.student_id = :sid
                    ORDER BY ar.attendance_date DESC
                    LIMIT 20
                    """
                ),
                {"sid": student_id},
            )
            return [
                {
                    "id": r[0],
                    "attendance_date": str(r[1]),
                    "status": r[2],
                    "notes": r[3],
                }
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Recent attendance query failed: %s", exc)
            return []

    async def _get_financial_summary(
        self, student_id: int
    ) -> FinancialSummary:
        try:
            result = await self.session.execute(
                text(
                    """
                    SELECT
                        COALESCE(SUM(fd.original_amount), 0) AS total_assigned,
                        COALESCE(SUM(fd.amount_paid), 0) AS total_paid,
                        COALESCE(SUM(fd.original_amount - fd.amount_paid), 0) AS outstanding,
                        SUM(CASE WHEN fd.status = 'unpaid' THEN 1 ELSE 0 END) AS unpaid_count,
                        SUM(CASE WHEN fd.status = 'partially_paid' THEN 1 ELSE 0 END) AS partial_count,
                        SUM(CASE WHEN fd.status = 'paid' THEN 1 ELSE 0 END) AS paid_count
                    FROM fee_dues fd
                    WHERE fd.student_id = :sid
                    """
                ),
                {"sid": student_id},
            )
            row = result.one()
            return FinancialSummary(
                total_fees_assigned=row[0],
                total_paid=row[1],
                total_outstanding=row[2],
                unpaid_count=row[3],
                partially_paid_count=row[4],
                paid_count=row[5],
            )
        except Exception as exc:
            logger.debug("Financial summary query failed: %s", exc)
            return FinancialSummary()

    async def _get_fee_dues(self, student_id: int) -> list[FeeDueItem]:
        try:
            result = await self.session.execute(
                text(
                    """
                    SELECT fd.id, ft.name AS fee_type_name,
                           fd.original_amount, fd.amount_paid,
                           (fd.original_amount - fd.amount_paid) AS balance,
                           fd.due_date, fd.status
                    FROM fee_dues fd
                    LEFT JOIN fee_structures fs ON fs.id = fd.fee_structure_id
                    LEFT JOIN fee_types ft ON ft.id = fs.fee_type_id
                    WHERE fd.student_id = :sid
                    ORDER BY fd.due_date ASC NULLS LAST, fd.created_at DESC
                    """
                ),
                {"sid": student_id},
            )
            return [
                FeeDueItem(
                    id=r[0],
                    fee_type_name=r[1],
                    original_amount=r[2],
                    amount_paid=r[3],
                    balance=r[4],
                    due_date=str(r[5]) if r[5] else None,
                    status=r[6],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Fee dues query failed: %s", exc)
            return []

    async def _get_payments(self, student_id: int) -> list[PaymentItem]:
        try:
            result = await self.session.execute(
                text(
                    """
                    SELECT id, amount, payment_date, payment_method,
                           receipt_number, created_at
                    FROM payments
                    WHERE student_id = :sid
                    ORDER BY created_at DESC
                    LIMIT 30
                    """
                ),
                {"sid": student_id},
            )
            return [
                PaymentItem(
                    id=r[0],
                    amount=r[1],
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
    ) -> list[AcademicRecord]:
        try:
            result = await self.session.execute(
                text(
                    """
                    SELECT e.id, ay.name, c.name, s.name, e.status, e.enrolled_at
                    FROM enrollments e
                    LEFT JOIN academic_years ay ON ay.id = e.academic_year_id
                    LEFT JOIN classes c ON c.id = e.class_id
                    LEFT JOIN sections s ON s.id = e.section_id
                    WHERE e.student_id = :sid
                    ORDER BY e.enrolled_at DESC
                    """
                ),
                {"sid": student_id},
            )
            return [
                AcademicRecord(
                    enrollment_id=r[0],
                    academic_year_name=r[1],
                    class_name=r[2],
                    section_name=r[3],
                    status=r[4],
                    enrolled_at=str(r[5]) if r[5] else "",
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Academic history query failed: %s", exc)
            return []

    async def _get_health_info(
        self, student_id: int
    ) -> StudentHealthInfo:
        try:
            result = await self.session.execute(
                text(
                    "SELECT blood_group, allergies, medical_conditions, emergency_contact "
                    "FROM student_health WHERE student_id = :sid"
                ),
                {"sid": student_id},
            )
            row = result.one_or_none()
            if row:
                return StudentHealthInfo(
                    blood_group=row[0],
                    allergies=row[1],
                    medical_conditions=row[2],
                    emergency_contact=row[3],
                )
        except Exception as exc:
            logger.debug("No student_health table: %s", exc)
        return StudentHealthInfo()

    async def _get_transport_info(
        self, student_id: int
    ) -> TransportInfo | None:
        try:
            result = await self.session.execute(
                text(
                    "SELECT route, pickup_point, dropoff_point, vehicle_number "
                    "FROM student_transport WHERE student_id = :sid"
                ),
                {"sid": student_id},
            )
            row = result.one_or_none()
            if row:
                return TransportInfo(
                    route=row[0],
                    pickup_point=row[1],
                    dropoff_point=row[2],
                    vehicle_number=row[3],
                )
        except Exception as exc:
            logger.debug("No student_transport table: %s", exc)
        return None

    async def _get_hostel_info(
        self, student_id: int
    ) -> HostelInfo | None:
        try:
            result = await self.session.execute(
                text(
                    "SELECT h.name AS hostel_name, sh.room_number, sh.bed_number "
                    "FROM student_hostel sh "
                    "LEFT JOIN hostels h ON h.id = sh.hostel_id "
                    "WHERE sh.student_id = :sid"
                ),
                {"sid": student_id},
            )
            row = result.one_or_none()
            if row:
                return HostelInfo(
                    hostel_name=row[0],
                    room_number=row[1],
                    bed_number=row[2],
                )
        except Exception as exc:
            logger.debug("No student_hostel table: %s", exc)
        return None

    async def _get_risk_findings(self, student_id: int) -> list[RiskFindingBrief]:
        """Open risk findings for the student (from the persisted snapshot)."""
        try:
            from app.domains.risk.models import RiskFinding

            result = await self.session.execute(
                select(RiskFinding)
                .where(
                    RiskFinding.student_id == student_id,
                    RiskFinding.status == "open",
                )
                .order_by(RiskFinding.severity.desc(), RiskFinding.score.desc())
            )
            return [
                RiskFindingBrief(
                    id=f.id,
                    rule_code=f.rule_code,
                    category=f.category,
                    severity=f.severity,
                    score=f.score,
                    reason=f.reason,
                    recommended_action=f.recommended_action,
                    detected_at=f.detected_at,
                )
                for f in result.scalars().all()
            ]
        except Exception as exc:  # noqa: BLE001 — risk is optional enrichment
            logger.debug("Risk findings query failed: %s", exc)
            return []
