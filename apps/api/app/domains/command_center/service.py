"""School Command Center aggregation service.

Composes a single, aggregated operational overview for school
leadership. Every section is built defensively — if one data source
fails, that section reports ``available=False`` while the rest of the
command center still renders (graceful partial failure).

RBAC: financial data is only surfaced to roles granted ``fees.view``
(admin, principal, accountant). Admissions/approvals are leadership-only
(admin, principal). Jobs/operations are admin-only. Teachers receive a
class-focused view.
"""

from __future__ import annotations

import datetime
import logging
from datetime import timezone
from typing import Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.analytics.service import AnalyticsService
from app.domains.admission.models import (
    ADMISSION_STATUS_FLOW,
    AdmissionApplication,
    AdmissionDocument,
)
from app.domains.attendance.models import AttendanceRecord
from app.domains.communications.models import CommunicationMessage
from app.domains.fees.models import FeeDue, Payment
from app.domains.jobs.models import Job
from app.domains.leave.models import LeaveRequest
from app.domains.academic.models import AcademicYear, Teacher, TeacherAssignment
from app.domains.workflow.models import ApprovalHistory, WorkflowInstance
from app.domains.risk.models import RiskFinding
from app.domains.command_center.schemas import (
    Alert,
    CommandCenterOverview,
    Metric,
    NeedsAttention,
    QuickAction,
    SchoolHealth,
    TodayEvent,
    TodaySection,
    TrendPoint,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

LEADERSHIP_ROLES = {"admin", "principal"}
OPERATIONS_ROLES = {"admin"}

FINANCIAL_ROLES = {"admin", "principal", "accountant"}
ATTENDANCE_ROLES = {"admin", "principal", "staff", "teacher"}

# Days before the active year ends to warn leadership that the next
# academic year has not been planned yet (proactive rollover health).
ROLLOVER_WINDOW_DAYS = 60

# ---------------------------------------------------------------------------
# Quick actions (role-filtered)
# ---------------------------------------------------------------------------

_QUICK_ACTIONS = [
    {
        "id": "add-student",
        "label": "Add Student",
        "description": "Register a new student record",
        "route": "/students",
        "icon": "user-plus",
        "roles": {"admin", "principal", "staff"},
    },
    {
        "id": "record-attendance",
        "label": "Record Attendance",
        "description": "Mark today's attendance",
        "route": "/attendance/daily",
        "icon": "check-square",
        "roles": {"admin", "principal", "staff", "teacher"},
    },
    {
        "id": "collect-payment",
        "label": "Collect Payment",
        "description": "Record a fee payment",
        "route": "/fees/payments",
        "icon": "banknote",
        "roles": {"admin", "principal", "accountant"},
    },
    {
        "id": "review-admission",
        "label": "Review Admission",
        "description": "Process admission applications",
        "route": "/admissions",
        "icon": "clipboard",
        "roles": {"admin", "principal"},
    },
    {
        "id": "approve-workflow",
        "label": "Approve Workflow",
        "description": "Handle pending approvals",
        "route": "/admin/approvals",
        "icon": "thumbs-up",
        "roles": {"admin", "principal"},
    },
    {
        "id": "send-announcement",
        "label": "Send Announcement",
        "description": "Broadcast to parents & students",
        "route": "/communications",
        "icon": "megaphone",
        "roles": {"admin", "principal", "staff"},
    },
]


class CommandCenterService:
    """Aggregated operational overview for the School Command Center."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.analytics = AnalyticsService(session)

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    async def get_overview(
        self,
        role: str,
        user,
        campus_id: Optional[int],
    ) -> CommandCenterOverview:
        """Build the full command-center payload for ``role``.

        Args:
            role: The user's primary role code (admin, principal, ...).
            user: The authenticated ``User`` (for teacher resolution).
            campus_id: Effective tenant campus (``None`` = unscoped admin).
        """
        can_finance = role in FINANCIAL_ROLES
        can_attendance = role in ATTENDANCE_ROLES
        is_leadership = role in LEADERSHIP_ROLES
        can_operations = role in OPERATIONS_ROLES

        # Teacher → class-focused resolution
        class_ids: Optional[list[int]] = None
        if role == "teacher":
            class_ids = await self._resolve_teacher_classes(user)
            if not class_ids:
                class_ids = None  # teacher with no assignment → no class scope

        sections: dict[str, bool] = {
            "school_health": True,
            "needs_attention": True,
            "today": True,
            "quick_actions": True,
        }

        school_health = await self._build_health(
            role, campus_id, class_ids, can_finance, can_attendance
        )
        sections["school_health"] = school_health.available

        attention = await self._build_attention(
            role,
            campus_id,
            class_ids,
            can_finance,
            can_attendance,
            is_leadership,
            can_operations,
        )
        sections["needs_attention"] = attention.available

        today = await self._build_today(
            role, campus_id, class_ids, can_finance, can_attendance, is_leadership
        )
        sections["today"] = today.available

        quick_actions = self._build_quick_actions(role)

        year_name = await self._active_year_name(campus_id)

        return CommandCenterOverview(
            generated_at=datetime.datetime.now(timezone.utc),
            role=role,
            campus_id=campus_id,
            academic_year=year_name,
            sections=sections,
            school_health=school_health,
            needs_attention=attention,
            today=today,
            quick_actions=[
                QuickAction(**a) for a in quick_actions
            ],
        )

    # ------------------------------------------------------------------
    # A. School Health
    # ------------------------------------------------------------------

    async def _build_health(
        self,
        role: str,
        campus_id: Optional[int],
        class_ids: Optional[list[int]],
        can_finance: bool,
        can_attendance: bool,
    ) -> SchoolHealth:
        try:
            metrics: list[Metric] = []
            trends: dict[str, list[TrendPoint]] = {}

            if role == "teacher":
                return await self._build_teacher_health(campus_id, class_ids)

            # Attendance rate + today snapshot (attendance.view roles)
            if can_attendance:
                try:
                    att = await self.analytics.get_attendance_overview(campus_id=campus_id)
                    attendance_rate = att["attendance_percentage"]
                    metrics.append(
                        Metric(
                            key="attendance_rate",
                            label="Attendance Rate",
                            value=attendance_rate,
                            display=f"{attendance_rate:.1f}%",
                            status=self._pct_status(attendance_rate, 90, 75),
                            drill_down="/attendance-intelligence/dashboard",
                        )
                    )
                    # Attendance trend (last 14 days) — historical data only
                    try:
                        t = await self.analytics.get_attendance_trends(
                            granularity="daily", campus_id=campus_id
                        )
                        pts = [
                            TrendPoint(
                                label=p["date"],
                                value=round(
                                    (p["present"] / p["total"] * 100) if p["total"] else 0, 1
                                ),
                            )
                            for p in t["trend"][-14:]
                        ]
                        if pts:
                            trends["attendance"] = pts
                    except Exception as exc:  # noqa: BLE001 — trends are optional
                        logger.warning("Command center: attendance trend unavailable: %s", exc)
                except Exception as exc:  # noqa: BLE001 — metric degrades individually
                    logger.warning("Command center: attendance metric unavailable: %s", exc)

            # Finance metrics (fees.view roles only)
            if can_finance:
                try:
                    fin = await self.analytics.get_finance_overview(campus_id=campus_id)
                    coll_rate = fin["collection_percentage"]
                    outstanding = fin["total_outstanding"]
                    metrics.extend(
                        [
                            Metric(
                                key="fee_collection_rate",
                                label="Fee Collection",
                                value=coll_rate,
                                display=f"{coll_rate:.1f}%",
                                status=self._pct_status(coll_rate, 80, 50),
                                drill_down="/school-finance/dashboard",
                            ),
                            Metric(
                                key="outstanding_amount",
                                label="Outstanding Amount",
                                value=float(outstanding),
                                display=self._fmt_inr(outstanding),
                                status="warn" if outstanding > 0 else "good",
                                drill_down="/fees/dues",
                            ),
                        ]
                    )
                    # Collection trend (last 30 days)
                    try:
                        ct = await self.analytics.get_collection_trends(
                            granularity="daily", campus_id=campus_id
                        )
                        cpts = [
                            TrendPoint(label=p["date"], value=p["amount"])
                            for p in ct["trend"][-30:]
                        ]
                        if cpts:
                            trends["collection"] = cpts
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Command center: collection trend unavailable: %s", exc)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: finance metrics unavailable: %s", exc)

            # Leadership metrics: students, staff, structure, admissions, approvals
            try:
                ov = await self.analytics.get_overview(campus_id=campus_id)
                metrics.append(
                    Metric(
                        key="total_students",
                        label="Total Students",
                        value=float(ov["total_students"]),
                        display=f"{ov['total_students']:,}",
                        status="good" if ov["total_students"] > 0 else "neutral",
                        drill_down="/students",
                    )
                )
                if role in LEADERSHIP_ROLES or role == "accountant":
                    metrics.append(
                        Metric(
                            key="total_teachers",
                            label="Teachers",
                            value=float(ov["total_teachers"]),
                            display=f"{ov['total_teachers']:,}",
                            status="neutral",
                            drill_down="/teachers",
                        )
                    )
                    metrics.append(
                        Metric(
                            key="total_classes",
                            label="Classes",
                            value=float(ov["total_classes"]),
                            display=f"{ov['total_classes']:,}",
                            status="neutral",
                            drill_down="/academic/classes",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Command center: structure metrics unavailable: %s", exc)

            # Leadership-only: admissions + pending approvals
            if role in LEADERSHIP_ROLES:
                try:
                    active_admissions = await self._count_active_admissions(campus_id)
                    metrics.append(
                        Metric(
                            key="active_admissions",
                            label="Active Admissions",
                            value=float(active_admissions),
                            display=f"{active_admissions:,}",
                            status="info" if active_admissions > 0 else "neutral",
                            drill_down="/admissions",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: admissions metric unavailable: %s", exc)

                try:
                    pending = await self._count_pending_approvals(campus_id)
                    metrics.append(
                        Metric(
                            key="pending_approvals",
                            label="Pending Approvals",
                            value=float(pending),
                            display=f"{pending:,}",
                            status="warn" if pending > 0 else "good",
                            drill_down="/admin/approvals",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: approvals metric unavailable: %s", exc)

            return SchoolHealth(available=True, metrics=metrics, trends=trends)
        except Exception as exc:  # noqa: BLE001 — whole section degrades gracefully
            logger.error("Command center: school health section failed: %s", exc)
            return SchoolHealth(available=False)

    async def _build_teacher_health(
        self,
        campus_id: Optional[int],
        class_ids: Optional[list[int]],
    ) -> SchoolHealth:
        """Class-focused health for teachers (their own classes only)."""
        if not class_ids:
            return SchoolHealth(
                available=True,
                metrics=[
                    Metric(
                        key="my_classes",
                        label="My Classes",
                        value=0,
                        display="No classes assigned",
                        status="neutral",
                        drill_down="/teacher/classes",
                    )
                ],
            )

        try:
            # Today snapshot scoped to the teacher's classes
            today = datetime.date.today().isoformat()
            row = (
                await self.session.execute(
                    select(
                        func.count(AttendanceRecord.id),
                        func.sum(
                            case((AttendanceRecord.status == "present", 1), else_=0)
                        ),
                    ).where(
                        AttendanceRecord.class_id.in_(class_ids),
                        AttendanceRecord.attendance_date == today,
                    )
                )
            ).one()
            total, present = row
            total = total or 0
            present = present or 0
            today_pct = (present / total * 100) if total else 0.0

            metrics = [
                Metric(
                    key="my_classes",
                    label="My Classes",
                    value=float(len(class_ids)),
                    display=f"{len(class_ids)}",
                    status="neutral",
                    drill_down="/teacher/classes",
                ),
                Metric(
                    key="today_attendance",
                    label="Today's Attendance",
                    value=round(today_pct, 1),
                    display=f"{today_pct:.0f}%",
                    status=self._pct_status(today_pct, 90, 75),
                    drill_down="/attendance/daily",
                ),
            ]
            return SchoolHealth(available=True, metrics=metrics)
        except Exception as exc:  # noqa: BLE001
            logger.error("Command center: teacher health failed: %s", exc)
            return SchoolHealth(available=False)

    # ------------------------------------------------------------------
    # B. Needs Attention — deterministic, actionable alerts
    # ------------------------------------------------------------------

    async def _build_attention(
        self,
        role: str,
        campus_id: Optional[int],
        class_ids: Optional[list[int]],
        can_finance: bool,
        can_attendance: bool,
        is_leadership: bool,
        can_operations: bool,
    ) -> NeedsAttention:
        try:
            alerts: list[Alert] = []

            if role == "teacher":
                return await self._build_teacher_attention(campus_id, class_ids)

            # 1. Low attendance (attendance.view roles)
            if can_attendance:
                try:
                    low = await self.analytics.get_low_attendance_students(
                        threshold=75, campus_id=campus_id, min_records=5
                    )
                    n = len(low)
                    if n > 0:
                        alerts.append(
                            Alert(
                                id="low-attendance",
                                severity="critical" if n >= 10 else "warning",
                                category="attendance",
                                title=f"{n} students below 75% attendance",
                                message="Students are flagged after 5+ recorded days.",
                                count=n,
                                action_label="View students",
                                drill_down="/attendance-intelligence/dashboard",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: low attendance alert unavailable: %s", exc)

            # 2. Overdue fees (fees.view roles)
            if can_finance:
                try:
                    overdue = await self._overdue_fees(campus_id)
                    if overdue["count"] > 0:
                        alerts.append(
                            Alert(
                                id="overdue-fees",
                                severity="warning",
                                category="fees",
                                title=f"{self._fmt_inr(overdue['amount'])} overdue",
                                message=(
                                    f"Across {overdue['count']} student(s) past their due date."
                                ),
                                count=overdue["count"],
                                action_label="View outstanding fees",
                                drill_down="/fees/dues",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: overdue fees alert unavailable: %s", exc)

            # 3. Admission bottlenecks (leadership)
            if is_leadership:
                try:
                    awaiting = await self._count_admissions_awaiting_review(campus_id)
                    if awaiting > 0:
                        alerts.append(
                            Alert(
                                id="admission-review",
                                severity="warning",
                                category="admissions",
                                title=f"{awaiting} applications awaiting review",
                                message="Applications waiting for document check or interview.",
                                count=awaiting,
                                action_label="Open admissions",
                                drill_down="/admissions",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: admission review alert unavailable: %s", exc)

                # 4. Missing / pending documents (leadership)
                try:
                    missing = await self._count_pending_documents(campus_id)
                    if missing > 0:
                        alerts.append(
                            Alert(
                                id="missing-documents",
                                severity="info",
                                category="documents",
                                title=f"{missing} document(s) awaiting verification",
                                message="Admission documents pending verification.",
                                count=missing,
                                action_label="Review documents",
                                drill_down="/admissions",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: documents alert unavailable: %s", exc)

                # 5. Pending approvals (leadership)
                try:
                    pending = await self._count_pending_approvals(campus_id)
                    if pending > 0:
                        alerts.append(
                            Alert(
                                id="pending-approvals",
                                severity="info",
                                category="approvals",
                                title=f"{pending} approval(s) pending",
                                message="Workflow instances waiting on the next step.",
                                count=pending,
                                action_label="Open approvals",
                                drill_down="/admin/approvals",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: approvals alert unavailable: %s", exc)

                # 6. Rollover health (leadership)
                try:
                    rollover = await self._rollover_health(campus_id)
                    if rollover:
                        alerts.append(
                            Alert(
                                id=rollover["id"],
                                severity=rollover["severity"],
                                category="rollover",
                                title=rollover["title"],
                                message=rollover["message"],
                                count=rollover.get("count"),
                                action_label=rollover["action_label"],
                                drill_down=rollover["drill_down"],
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: rollover alert unavailable: %s", exc)

            # 6b. Risk engine: high/critical open findings (staff-facing)
            try:
                risk = await self._risk_summary(campus_id, role)
                if risk and risk["severe"] > 0:
                    alerts.append(
                        Alert(
                            id="risk-findings",
                            severity="warning" if risk["critical"] == 0 else "critical",
                            category="risk",
                            title=f"{risk['severe']} high/critical risk finding(s) open",
                            message=risk["message"],
                            count=risk["severe"],
                            action_label="Open Risk Center",
                            drill_down="/risk",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Command center: risk alert unavailable: %s", exc)

            # 7. Job failures (operations/admin)
            if can_operations:
                try:
                    failed = await self._count_failed_jobs(campus_id)
                    if failed > 0:
                        alerts.append(
                            Alert(
                                id="job-failures",
                                severity="warning",
                                category="jobs",
                                title=f"{failed} failed job(s)",
                                message="Background jobs failed and may need a retry.",
                                count=failed,
                                action_label="View jobs",
                                drill_down="/operations",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: jobs alert unavailable: %s", exc)

            return NeedsAttention(available=True, alerts=alerts)
        except Exception as exc:  # noqa: BLE001
            logger.error("Command center: needs-attention section failed: %s", exc)
            return NeedsAttention(available=False)

    async def _build_teacher_attention(
        self,
        campus_id: Optional[int],
        class_ids: Optional[list[int]],
    ) -> NeedsAttention:
        if not class_ids:
            return NeedsAttention(available=True, alerts=[])
        try:
            alerts: list[Alert] = []
            today = datetime.date.today().isoformat()
            row = (
                await self.session.execute(
                    select(
                        func.count(AttendanceRecord.id),
                        func.sum(
                            case((AttendanceRecord.status == "absent", 1), else_=0)
                        ),
                    ).where(
                        AttendanceRecord.class_id.in_(class_ids),
                        AttendanceRecord.attendance_date == today,
                    )
                )
            ).one()
            total, absent = row
            total = total or 0
            absent = absent or 0
            if absent > 0:
                alerts.append(
                    Alert(
                        id="teacher-today-absent",
                        severity="warning" if absent > 3 else "info",
                        category="attendance",
                        title=f"{absent} absent today in your classes",
                        message=f"Out of {total} attendance records recorded today.",
                        count=absent,
                        action_label="View attendance",
                        drill_down="/attendance/daily",
                    )
                )
            return NeedsAttention(available=True, alerts=alerts)
        except Exception as exc:  # noqa: BLE001
            logger.error("Command center: teacher attention failed: %s", exc)
            return NeedsAttention(available=False)

    # ------------------------------------------------------------------
    # C. Today — operational events
    # ------------------------------------------------------------------

    async def _build_today(
        self,
        role: str,
        campus_id: Optional[int],
        class_ids: Optional[list[int]],
        can_finance: bool,
        can_attendance: bool,
        is_leadership: bool,
    ) -> TodaySection:
        try:
            events: list[TodayEvent] = []
            today = datetime.date.today().isoformat()
            start_of_day = datetime.datetime.combine(
                datetime.date.today(), datetime.time.min, tzinfo=timezone.utc
            )

            # Attendance today (attendance.view roles)
            if can_attendance:
                try:
                    scope = (
                        [AttendanceRecord.class_id.in_(class_ids)]
                        if class_ids
                        else ([AttendanceRecord.campus_id == campus_id] if campus_id else [])
                    )
                    row = (
                        await self.session.execute(
                            select(
                                func.count(AttendanceRecord.id),
                                func.sum(
                                    case((AttendanceRecord.status == "present", 1), else_=0)
                                ),
                                func.sum(
                                    case((AttendanceRecord.status == "absent", 1), else_=0)
                                ),
                            ).where(
                                AttendanceRecord.attendance_date == today,
                                *scope,
                            )
                        )
                    ).one()
                    total, present, absent = (row[0] or 0), (row[1] or 0), (row[2] or 0)
                    if total > 0:
                        events.append(
                            TodayEvent(
                                id="today-attendance",
                                type="attendance",
                                title=f"{total} attendance records",
                                description=f"{present} present · {absent} absent",
                                time=today,
                                drill_down="/attendance/daily",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: today attendance unavailable: %s", exc)

            # Payments today (fees.view roles)
            if can_finance:
                try:
                    row = (
                        await self.session.execute(
                            select(
                                func.count(Payment.id),
                                func.coalesce(func.sum(Payment.amount), 0),
                            ).where(
                                Payment.payment_date == today,
                                *(
                                    [Payment.campus_id == campus_id]
                                    if campus_id
                                    else []
                                ),
                            )
                        )
                    ).one()
                    count, amount = (row[0] or 0), (row[1] or 0)
                    if count > 0:
                        events.append(
                            TodayEvent(
                                id="today-payments",
                                type="payment",
                                title=f"{count} payment(s) collected",
                                description=self._fmt_inr(amount),
                                time=today,
                                drill_down="/fees/payments",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: today payments unavailable: %s", exc)

            # Admissions today (leadership)
            if is_leadership:
                try:
                    q = select(func.count(AdmissionApplication.id)).where(
                        AdmissionApplication.created_at >= start_of_day
                    )
                    if campus_id is not None:
                        q = q.where(AdmissionApplication.campus_id == campus_id)
                    count = (await self.session.execute(q)).scalar() or 0
                    if count > 0:
                        events.append(
                            TodayEvent(
                                id="today-admissions",
                                type="admission",
                                title=f"{count} new application(s)",
                                description="Admission applications created today",
                                time=today,
                                drill_down="/admissions",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: today admissions unavailable: %s", exc)

                # Approvals actioned today (leadership)
                try:
                    count = await self._count_approval_actions_today(campus_id, start_of_day)
                    if count > 0:
                        events.append(
                            TodayEvent(
                                id="today-approvals",
                                type="approval",
                                title=f"{count} approval action(s)",
                                description="Workflow approvals performed today",
                                time=today,
                                drill_down="/admin/approvals",
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Command center: today approvals unavailable: %s", exc)

            # Leave active today (all staff-facing roles)
            try:
                q = select(func.count(LeaveRequest.id)).where(
                    LeaveRequest.start_date <= today,
                    LeaveRequest.end_date >= today,
                )
                if campus_id is not None:
                    q = q.where(LeaveRequest.campus_id == campus_id)
                count = (await self.session.execute(q)).scalar() or 0
                if count > 0:
                    events.append(
                        TodayEvent(
                            id="today-leave",
                            type="leave",
                            title=f"{count} on leave today",
                            description="Staff members with approved/active leave",
                            time=today,
                            drill_down="/leave",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Command center: today leave unavailable: %s", exc)

            # Announcements today (staff-facing roles)
            try:
                q = select(func.count(CommunicationMessage.id)).where(
                    CommunicationMessage.created_at >= start_of_day
                )
                if campus_id is not None:
                    q = q.where(CommunicationMessage.campus_id == campus_id)
                count = (await self.session.execute(q)).scalar() or 0
                if count > 0:
                    events.append(
                        TodayEvent(
                            id="today-announcements",
                            type="announcement",
                            title=f"{count} announcement(s) sent",
                            description="Messages broadcast to parents & students",
                            time=today,
                            drill_down="/communications",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Command center: today announcements unavailable: %s", exc)

            return TodaySection(available=True, events=events)
        except Exception as exc:  # noqa: BLE001
            logger.error("Command center: today section failed: %s", exc)
            return TodaySection(available=False)

    # ------------------------------------------------------------------
    # D. Quick actions
    # ------------------------------------------------------------------

    def _build_quick_actions(self, role: str) -> list[dict]:
        return [
            a for a in _QUICK_ACTIONS if role in a["roles"]
        ]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def _resolve_teacher_classes(self, user) -> Optional[list[int]]:
        """Find the teacher record matching the user, then their classes."""
        try:
            if not getattr(user, "email", None):
                return None
            t = (
                await self.session.execute(
                    select(Teacher).where(Teacher.email == user.email)
                )
            ).scalar_one_or_none()
            if t is None:
                return None
            rows = (
                await self.session.execute(
                    select(TeacherAssignment.class_id).where(
                        TeacherAssignment.teacher_id == t.id,
                        TeacherAssignment.status == "active",
                    )
                )
            ).all()
            return [r[0] for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Command center: teacher resolution failed: %s", exc)
            return None

    async def _active_year_name(self, campus_id: Optional[int]) -> Optional[str]:
        try:
            q = select(AcademicYear.name).where(AcademicYear.status == "active")
            if campus_id is not None:
                q = q.where(AcademicYear.campus_id == campus_id)
            return (await self.session.execute(q.limit(1))).scalar_one_or_none()
        except Exception:  # noqa: BLE001
            return None

    async def _count_active_admissions(self, campus_id: Optional[int]) -> int:
        terminal = {
            "enrolled",
            "student_created",
            "rejected",
        }
        active = [s for s in ADMISSION_STATUS_FLOW if s not in terminal]
        q = select(func.count(AdmissionApplication.id)).where(
            AdmissionApplication.status.in_(active)
        )
        if campus_id is not None:
            q = q.where(AdmissionApplication.campus_id == campus_id)
        return (await self.session.execute(q)).scalar() or 0

    async def _count_admissions_awaiting_review(self, campus_id: Optional[int]) -> int:
        awaiting = {"application_submitted", "documents_uploaded", "verified"}
        q = select(func.count(AdmissionApplication.id)).where(
            AdmissionApplication.status.in_(awaiting)
        )
        if campus_id is not None:
            q = q.where(AdmissionApplication.campus_id == campus_id)
        return (await self.session.execute(q)).scalar() or 0

    async def _count_pending_documents(self, campus_id: Optional[int]) -> int:
        q = (
            select(func.count(AdmissionDocument.id))
            .join(
                AdmissionApplication,
                AdmissionDocument.application_id == AdmissionApplication.id,
            )
            .where(AdmissionDocument.verification_status == "pending")
        )
        if campus_id is not None:
            q = q.where(AdmissionApplication.campus_id == campus_id)
        return (await self.session.execute(q)).scalar() or 0

    async def _count_pending_approvals(self, campus_id: Optional[int]) -> int:
        q = select(func.count(WorkflowInstance.id)).where(
            WorkflowInstance.status == "active"
        )
        if campus_id is not None:
            q = q.where(WorkflowInstance.campus_id == campus_id)
        return (await self.session.execute(q)).scalar() or 0

    async def _overdue_fees(self, campus_id: Optional[int]) -> dict:
        today = datetime.date.today().isoformat()
        q = (
            select(
                func.count(func.distinct(FeeDue.student_id)),
                func.coalesce(
                    func.sum(FeeDue.original_amount - FeeDue.amount_paid), 0
                ),
            )
            .where(
                FeeDue.due_date.isnot(None),
                FeeDue.due_date < today,
                FeeDue.amount_paid < FeeDue.original_amount,
            )
        )
        if campus_id is not None:
            q = q.where(FeeDue.campus_id == campus_id)
        row = (await self.session.execute(q)).one()
        return {"count": row[0] or 0, "amount": row[1] or 0}

    async def _rollover_health(self, campus_id: Optional[int]) -> Optional[dict]:
        """Deterministic rollover-health check: is the next academic year ready?

        Returns an alert dict when the next year is not set up:
          - the active year has already ended (blocking — run rollover now), or
          - the active year ends within ``ROLLOVER_WINDOW_DAYS`` and no upcoming
            year is planned yet (proactive warning).

        Returns ``None`` when a future-dated year already exists (healthy) or
        when there is nothing to flag (no active year / no end date).
        """
        today = datetime.date.today()
        # Soonest-ending active year drives the alert (deterministic ordering).
        q = (
            select(AcademicYear)
            .where(AcademicYear.status == "active")
            .order_by(AcademicYear.end_date.asc())
        )
        if campus_id is not None:
            q = q.where(AcademicYear.campus_id == campus_id)
        year = (await self.session.execute(q.limit(1))).scalar_one_or_none()
        if year is None or year.end_date is None:
            return None

        # A future-dated (next) year already exists → healthy, nothing to flag.
        q_next = select(func.count(AcademicYear.id)).where(
            AcademicYear.start_date > today
        )
        if campus_id is not None:
            q_next = q_next.where(AcademicYear.campus_id == campus_id)
        next_years = (await self.session.execute(q_next)).scalar() or 0
        if next_years > 0:
            return None

        days_left = (year.end_date - today).days
        if year.end_date < today:
            return {
                "id": "rollover-issue",
                "severity": "critical",
                "title": f"Academic year '{year.name}' has ended",
                "message": "Run rollover to create the next academic year.",
                "count": abs(days_left),
                "action_label": "Go to rollover",
                "drill_down": "/operations/rollover",
            }
        if days_left <= ROLLOVER_WINDOW_DAYS:
            if days_left == 0:
                ends_in = "ends today"
            elif days_left == 1:
                ends_in = "ends tomorrow"
            else:
                ends_in = f"ends in {days_left} days"
            return {
                "id": "rollover-next-year",
                "severity": "warning",
                "title": "Next academic year not set up",
                "message": (
                    f"'{year.name}' {ends_in}. "
                    "Plan the next academic year before it ends."
                ),
                "count": days_left,
                "action_label": "Plan next year",
                "drill_down": "/academic/years",
            }
        return None

    async def _count_failed_jobs(self, campus_id: Optional[int]) -> int:
        q = select(func.count(Job.id)).where(Job.status == "failed")
        if campus_id is not None:
            q = q.where(Job.campus_id == campus_id)
        return (await self.session.execute(q)).scalar() or 0

    async def _risk_summary(self, campus_id: Optional[int], role: str) -> Optional[dict]:
        """Aggregate open high/critical risk findings for the alert."""
        # Financial categories hidden from roles without fees.view
        if role in ("teacher", "staff", "student", "parent"):
            allowed = {"attendance", "academic", "documents", "operational"}
        else:
            allowed = None  # leadership/accountant see all
        q = select(
            RiskFinding.category,
            RiskFinding.severity,
            func.count(RiskFinding.id),
        ).where(
            RiskFinding.campus_id == campus_id,
            RiskFinding.status == "open",
            RiskFinding.severity.in_(["high", "critical"]),
        )
        if allowed is not None:
            q = q.where(RiskFinding.category.in_(allowed))
        q = q.group_by(RiskFinding.category, RiskFinding.severity)
        rows = (await self.session.execute(q)).all()
        if not rows:
            return None
        severe = sum(r[2] for r in rows)
        critical = sum(r[2] for r in rows if r[1] == "critical")
        by_cat = {r[0]: r[2] for r in rows}
        top = max(by_cat, key=by_cat.get)
        return {
            "severe": severe,
            "critical": critical,
            "message": f"Most in: {top} ({by_cat[top]} finding(s)).",
        }

    async def _count_approval_actions_today(
        self, campus_id: Optional[int], start_of_day: datetime.datetime
    ) -> int:
        q = (
            select(func.count(ApprovalHistory.id))
            .join(WorkflowInstance, ApprovalHistory.instance_id == WorkflowInstance.id)
            .where(ApprovalHistory.created_at >= start_of_day)
        )
        if campus_id is not None:
            q = q.where(WorkflowInstance.campus_id == campus_id)
        return (await self.session.execute(q)).scalar() or 0

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pct_status(value: float, good: float, warn: float) -> str:
        if value >= good:
            return "good"
        if value >= warn:
            return "warn"
        return "critical"

    @staticmethod
    def _fmt_inr(amount: int) -> str:
        """Compact Indian-style currency formatting (₹12.4L, ₹85K, ₹9,500).

        Amounts are stored as minor units (paise), so convert to rupees
        before applying the L/K thresholds.
        """
        rupees = amount / 100
        if rupees >= 100_000:
            return f"₹{rupees / 100_000:.1f}L"
        if rupees >= 1_000:
            return f"₹{rupees / 1_000:.0f}K"
        return f"₹{rupees:.0f}"
