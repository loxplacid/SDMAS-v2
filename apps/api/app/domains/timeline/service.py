"""Unified Operational Timeline aggregation service.

Aggregates operational events from *persisted* sources into a single
normalized, reverse-chronological timeline. No new event storage is
created — we read from tables that already exist:

- ``audit``        — AuditLog (CREATE/UPDATE/DELETE/APPROVE/RECORD_PAYMENT …)
- ``workflow``     — ApprovalHistory joined to WorkflowInstance
- ``notification`` — Notification (own + system broadcasts)
- ``fees``         — Payment
- ``academic``     — Enrollment
- ``admissions``   — AdmissionApplication (creation + status transitions)
- ``risk``         — RiskFinding (detection events)

Security
--------
- **Tenant isolation**: every source query is pinned to the caller's
  campus (``campus_id``); unscoped platform admins may pass ``None``.
- **RBAC**: financial sources (fees + audit payment/fee actions) are
  hidden from roles without ``fees.view``; admissions/approvals are
  leadership-only; notifications are limited to the caller's own rows
  plus system broadcasts; risk findings hide the finance category for
  staff/teacher.
- **Entity scoping**: ``entity_type`` + ``entity_id`` restrict the feed
  to a single student / class / teacher (used by the 360 views).

Performance
-----------
One bounded SQL query per source (rows ordered newest-first, cut at
``offset + page_size``), merged in Python — no N+1, no cross-join of
large tables. Each source is fetched defensively: a failing source
reports ``available=False`` and the rest of the timeline still renders
(graceful partial failure).
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domains.academic.models import Class, Enrollment, Teacher
from app.domains.admission.models import AdmissionApplication
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User
from app.domains.fees.models import Payment
from app.domains.notifications.models import Notification
from app.domains.risk.models import RiskFinding
from app.domains.student.models import Student
from app.domains.workflow.models import ApprovalHistory, WorkflowInstance, Workflow
from app.domains.timeline.schemas import (
    TimelineItem,
    TimelineResponse,
    TimelineSourceInfo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RBAC helpers (mirrors command-center/risk conventions)
# ---------------------------------------------------------------------------

FINANCIAL_ROLES = {"admin", "principal", "accountant"}
LEADERSHIP_ROLES = {"admin", "principal"}
AUDIT_ROLES = {"admin", "principal"}
STAFF_ROLES = {"admin", "principal", "staff", "teacher"}
ALL_STAFF_ROLES = {"admin", "principal", "accountant", "staff", "teacher"}

SOURCE_LABELS = {
    "audit": "Audit Trail",
    "workflow": "Approvals",
    "notification": "Notifications",
    "fees": "Payments",
    "academic": "Enrollments",
    "admissions": "Admissions",
    "risk": "Risk Findings",
}

# Sources visible per role (union of the per-source RBAC below).
_SOURCE_ROLES: dict[str, frozenset[str]] = {
    "audit": frozenset(AUDIT_ROLES),
    "workflow": frozenset(LEADERSHIP_ROLES),
    "notification": frozenset(ALL_STAFF_ROLES),
    "fees": frozenset(FINANCIAL_ROLES),
    "academic": frozenset(STAFF_ROLES),
    "admissions": frozenset(LEADERSHIP_ROLES),
    "risk": frozenset(STAFF_ROLES),
}

# Audit actions that carry financial meaning → hidden without fees.view.
_FINANCIAL_AUDIT_RESOURCES = frozenset(
    {"fee", "fees", "payment", "payments", "payment_method", "fee_structure"}
)
# Audit resources that are leadership-only.
_LEADERSHIP_AUDIT_RESOURCES = frozenset(
    {"admission", "admissions", "workflow", "workflow_instance", "approval"}
)


def _severity_for_action(action: str) -> str:
    action_upper = (action or "").upper()
    if action_upper in {"DELETE", "REFUND", "PASSWORD_CHANGE"}:
        return "warning"
    if action_upper in {"APPROVE", "RECORD_PAYMENT", "CREATE"}:
        return "success"
    if action_upper == "RISK":
        return "warning"
    return "info"


# ---------------------------------------------------------------------------
# Filter bundle
# ---------------------------------------------------------------------------


@dataclass
class TimelineFilters:
    entity_type: str = "school"  # school | student | class | teacher
    entity_id: Optional[int] = None
    source: Optional[str] = None  # single source key or None for all
    event_type: Optional[str] = None
    actor: Optional[str] = None
    start: Optional[datetime.datetime] = None
    end: Optional[datetime.datetime] = None
    page: int = 1
    page_size: int = 20


@dataclass
class _SourceResult:
    key: str
    items: list[TimelineItem] = field(default_factory=list)
    count: int = 0
    available: bool = True


class TimelineService:
    """Read-only aggregation of operational events for one campus."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    async def get_timeline(
        self,
        role: str,
        user_id: Optional[int],
        campus_id: Optional[int],
        filters: TimelineFilters,
    ) -> TimelineResponse:
        """Build the unified timeline for ``role`` scoped to ``campus_id``.

        Every source is queried defensively; a source that raises is
        reported as unavailable and the remaining sources still render.

        A scoped entity (student/class/teacher) must belong to the
        caller's campus — cross-tenant entity reads raise 403.
        """
        await self._assert_entity_scope(campus_id, filters)
        sources = await self._enabled_sources(role, filters)
        offset = (filters.page - 1) * filters.page_size
        need = offset + filters.page_size

        results: list[_SourceResult] = []
        for key in sources:
            result = await self._fetch_source(
                key, role, user_id, campus_id, filters, need
            )
            results.append(result)

        # Merge + sort newest-first, then slice for the requested page.
        merged: list[TimelineItem] = []
        for r in results:
            merged.extend(r.items)
        merged.sort(key=lambda i: i.timestamp, reverse=True)
        page_items = merged[offset : offset + filters.page_size]

        total = sum(r.count for r in results)
        degraded = any(not r.available for r in results)

        source_infos = [
            TimelineSourceInfo(
                key=r.key,
                label=SOURCE_LABELS.get(r.key, r.key),
                count=r.count,
                available=r.available,
            )
            for r in results
        ]

        return TimelineResponse(
            items=page_items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            sources=source_infos,
            degraded=degraded,
        )

    # ------------------------------------------------------------------
    # Entity-scope guard (IDOR prevention)
    # ------------------------------------------------------------------

    async def _assert_entity_scope(
        self, campus_id: Optional[int], filters: TimelineFilters
    ) -> None:
        """Raise 403 when a scoped entity belongs to another campus."""
        if filters.entity_type == "school" or not filters.entity_id:
            return
        model = {
            "student": Student,
            "class": Class,
            "teacher": Teacher,
        }.get(filters.entity_type)
        if model is None:
            return
        row = await self.session.get(model, filters.entity_id)
        if row is None:
            raise NotFoundError(
                f"{filters.entity_type} {filters.entity_id} not found"
            )
        if campus_id is not None and getattr(row, "campus_id", None) != campus_id:
            raise AuthorizationError(
                f"Cross-tenant access denied to {filters.entity_type} "
                f"#{filters.entity_id}"
            )

    # ------------------------------------------------------------------
    # Source resolution + dispatch
    # ------------------------------------------------------------------

    async def _enabled_sources(
        self, role: str, filters: TimelineFilters
    ) -> list[str]:
        """Ordered list of sources the role may see, honouring the
        ``source`` filter and entity scope."""
        if filters.entity_type == "student":
            all_keys = ["audit", "fees", "academic", "risk"]
        elif filters.entity_type == "class":
            all_keys = ["academic", "audit", "workflow"]
        elif filters.entity_type == "teacher":
            all_keys = ["audit", "workflow", "academic"]
        else:
            all_keys = list(SOURCE_LABELS.keys())

        enabled = [k for k in all_keys if role in _SOURCE_ROLES.get(k, set())]
        if filters.source:
            if filters.source in enabled:
                return [filters.source]
            return []
        return enabled

    async def _fetch_source(
        self,
        key: str,
        role: str,
        user_id: Optional[int],
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> _SourceResult:
        try:
            if key == "audit":
                items, count = await self._fetch_audit(
                    role, campus_id, filters, need
                )
            elif key == "workflow":
                items, count = await self._fetch_workflow(
                    campus_id, filters, need
                )
            elif key == "notification":
                items, count = await self._fetch_notifications(
                    user_id, campus_id, filters, need
                )
            elif key == "fees":
                items, count = await self._fetch_payments(
                    campus_id, filters, need
                )
            elif key == "academic":
                items, count = await self._fetch_enrollments(
                    campus_id, filters, need
                )
            elif key == "admissions":
                items, count = await self._fetch_admissions(
                    campus_id, filters, need
                )
            elif key == "risk":
                items, count = await self._fetch_risk(
                    role, campus_id, filters, need
                )
            else:  # pragma: no cover — guarded by _enabled_sources
                items, count = [], 0
            return _SourceResult(key=key, items=items, count=count)
        except Exception as exc:  # noqa: BLE001 — source degrades independently
            logger.warning("Timeline source %s failed: %s", key, exc)
            return _SourceResult(key=key, available=False)

    # ------------------------------------------------------------------
    # Per-source queries
    # ------------------------------------------------------------------

    async def _fetch_audit(
        self,
        role: str,
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = select(AuditLog)
        conditions = []
        if campus_id is not None:
            conditions.append(AuditLog.campus_id == campus_id)
        if filters.start:
            conditions.append(AuditLog.created_at >= filters.start)
        if filters.end:
            conditions.append(AuditLog.created_at <= filters.end)
        if filters.actor:
            conditions.append(AuditLog.username.ilike(f"%{filters.actor}%"))
        if filters.event_type:
            event_conditions = self._event_conditions("audit", filters.event_type, AuditLog)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)

        entity_scope = await self._audit_entity_conditions(filters)
        conditions.extend(entity_scope)

        # RBAC — financial audit actions hidden without fees.view;
        # leadership-only resources hidden from staff/teacher.
        if role not in FINANCIAL_ROLES:
            conditions.append(
                ~AuditLog.resource_type.in_(_FINANCIAL_AUDIT_RESOURCES)
            )
        if role not in LEADERSHIP_ROLES:
            conditions.append(
                ~AuditLog.resource_type.in_(_LEADERSHIP_AUDIT_RESOURCES)
            )

        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(AuditLog.created_at.desc()).limit(need)
            )
        ).scalars().all()

        items = []
        for log in rows:
            resource = log.resource_type or "record"
            items.append(
                TimelineItem(
                    id=f"audit:{log.id}",
                    event_type=f"audit.{resource}.{(log.action or '').lower()}",
                    timestamp=log.created_at,
                    actor=log.username or "system",
                    entity=f"{resource.replace('_', ' ').title()} #{log.resource_id}" if log.resource_id else resource.replace("_", " ").title(),
                    description=self._audit_description(log),
                    severity=_severity_for_action(log.action),
                    source="audit",
                    metadata=self._safe_details(log.details),
                    deep_link=self._audit_deep_link(log),
                )
            )
        return items, count

    async def _audit_entity_conditions(self, filters: TimelineFilters) -> list:
        """Pin audit rows to a student/class/teacher when scoped."""
        if filters.entity_type == "student" and filters.entity_id:
            return [
                AuditLog.resource_type == "student",
                AuditLog.resource_id == str(filters.entity_id),
            ]
        if filters.entity_type == "class" and filters.entity_id:
            return [
                AuditLog.resource_type.in_(["academic", "class"]),
                AuditLog.resource_id == str(filters.entity_id),
            ]
        if filters.entity_type == "teacher" and filters.entity_id:
            return [
                AuditLog.resource_type == "teacher",
                AuditLog.resource_id == str(filters.entity_id),
            ]
        return []

    @staticmethod
    def _safe_details(details: Optional[str]) -> dict:
        if not details:
            return {}
        try:
            parsed = json.loads(details)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"value": details}

    @staticmethod
    def _audit_description(log: AuditLog) -> str:
        action = (log.action or "ACTION").replace("_", " ").lower()
        resource = (log.resource_type or "record").replace("_", " ")
        if log.resource_id:
            return f"{action} {resource} #{log.resource_id}"
        return f"{action} {resource}"

    @staticmethod
    def _audit_deep_link(log: AuditLog) -> Optional[str]:
        rt = log.resource_type or ""
        rid = log.resource_id
        if rt == "student" and rid:
            return f"/students/{rid}/360"
        if rt == "teacher" and rid:
            return f"/teachers/{rid}/360"
        if rt in ("academic", "class") and rid:
            return f"/academic/classes/{rid}/360"
        if rt in {"fee", "fees", "payment", "payments"}:
            return "/fees/payments"
        if rt in {"admission", "admissions"}:
            return "/admissions"
        if rt in {"workflow", "workflow_instance"}:
            return "/admin/approvals"
        if rt == "attendance":
            return "/attendance/daily"
        if rt == "risk_finding":
            return "/risk"
        return None

    async def _fetch_workflow(
        self,
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = (
            select(ApprovalHistory, WorkflowInstance, Workflow.name, User.display_name)
            .join(
                WorkflowInstance,
                ApprovalHistory.instance_id == WorkflowInstance.id,
            )
            .join(Workflow, WorkflowInstance.workflow_id == Workflow.id)
            .outerjoin(User, ApprovalHistory.actor_id == User.id)
        )
        conditions = []
        if campus_id is not None:
            conditions.append(WorkflowInstance.campus_id == campus_id)
        if filters.start:
            conditions.append(ApprovalHistory.created_at >= filters.start)
        if filters.end:
            conditions.append(ApprovalHistory.created_at <= filters.end)
        if filters.actor:
            conditions.append(User.display_name.ilike(f"%{filters.actor}%"))
        if filters.event_type:
            event_conditions = self._event_conditions("workflow", filters.event_type, ApprovalHistory)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)
        if filters.entity_type == "teacher" and filters.entity_id:
            conditions.append(
                WorkflowInstance.entity_type == "teacher",
                WorkflowInstance.entity_id == filters.entity_id,
            )
        elif filters.entity_type == "class" and filters.entity_id:
            conditions.append(
                WorkflowInstance.entity_type == "class",
                WorkflowInstance.entity_id == filters.entity_id,
            )
        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(ApprovalHistory.created_at.desc()).limit(need)
            )
        ).all()

        items = []
        for history, instance, workflow_name, display_name in rows:
            action = history.action or "action"
            items.append(
                TimelineItem(
                    id=f"workflow:{history.id}",
                    event_type=f"workflow.{action}",
                    timestamp=history.created_at,
                    actor=display_name or (
                        f"user #{history.actor_id}" if history.actor_id else "system"
                    ),
                    entity=workflow_name or f"Workflow #{instance.id}",
                    description=(
                        f"{action.replace('_', ' ').title()} on "
                        f"{instance.entity_type} #{instance.entity_id}"
                        + (f" — {history.comment}" if history.comment else "")
                    ),
                    severity="success" if action == "approve" else (
                        "warning" if action in ("reject", "return") else "info"
                    ),
                    source="workflow",
                    metadata={
                        "instance_id": instance.id,
                        "entity_type": instance.entity_type,
                        "entity_id": instance.entity_id,
                        "comment": history.comment,
                    },
                    deep_link="/admin/approvals",
                )
            )
        return items, count

    async def _fetch_notifications(
        self,
        user_id: Optional[int],
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = select(Notification)
        conditions = []
        if campus_id is not None:
            conditions.append(Notification.campus_id == campus_id)
        # Own notifications + system broadcasts only.
        if user_id is not None:
            conditions.append(
                (Notification.user_id == user_id)
                | (Notification.user_id.is_(None))
            )
        if filters.start:
            conditions.append(Notification.created_at >= filters.start)
        if filters.end:
            conditions.append(Notification.created_at <= filters.end)
        if filters.event_type:
            event_conditions = self._event_conditions("notification", filters.event_type, Notification)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)
        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(Notification.created_at.desc()).limit(need)
            )
        ).scalars().all()

        items = []
        for n in rows:
            items.append(
                TimelineItem(
                    id=f"notification:{n.id}",
                    event_type=f"notification.{n.type or 'system'}",
                    timestamp=n.created_at,
                    actor="system",
                    entity=n.title,
                    description=n.message,
                    severity="info",
                    source="notification",
                    metadata=n.data if isinstance(n.data, dict) else {},
                    deep_link="/notifications",
                )
            )
        return items, count

    async def _fetch_payments(
        self,
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = select(Payment)
        conditions = []
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)
        if filters.start:
            conditions.append(Payment.created_at >= filters.start)
        if filters.end:
            conditions.append(Payment.created_at <= filters.end)
        if filters.entity_type == "student" and filters.entity_id:
            conditions.append(Payment.student_id == filters.entity_id)
        if filters.event_type:
            event_conditions = self._event_conditions("fees", filters.event_type, Payment)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)
        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(Payment.created_at.desc()).limit(need)
            )
        ).scalars().all()

        # Resolve student names in one batched query.
        student_ids = {p.student_id for p in rows}
        names = await self._student_names(student_ids)

        items = []
        for p in rows:
            name = names.get(p.student_id, f"Student #{p.student_id}")
            amount = (p.amount or 0) / 100
            items.append(
                TimelineItem(
                    id=f"fees:{p.id}",
                    event_type="fees.payment",
                    timestamp=p.created_at,
                    actor="system",
                    entity=name,
                    description=f"Payment of ₹{amount:,.0f} recorded"
                    + (f" · {p.payment_method}" if p.payment_method else ""),
                    severity="success",
                    source="fees",
                    metadata={
                        "student_id": p.student_id,
                        "amount": p.amount,
                        "method": p.payment_method,
                        "receipt": p.receipt_number,
                    },
                    deep_link=(
                        f"/students/{p.student_id}/360"
                        if p.student_id
                        else "/fees/payments"
                    ),
                )
            )
        return items, count

    async def _fetch_enrollments(
        self,
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = select(Enrollment)
        conditions = []
        if campus_id is not None:
            conditions.append(Enrollment.campus_id == campus_id)
        if filters.start:
            conditions.append(Enrollment.enrolled_at >= filters.start)
        if filters.end:
            conditions.append(Enrollment.enrolled_at <= filters.end)
        if filters.entity_type == "student" and filters.entity_id:
            conditions.append(Enrollment.student_id == filters.entity_id)
        elif filters.entity_type == "class" and filters.entity_id:
            conditions.append(Enrollment.class_id == filters.entity_id)
        if filters.event_type:
            event_conditions = self._event_conditions("academic", filters.event_type, Enrollment)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)
        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(Enrollment.enrolled_at.desc()).limit(need)
            )
        ).scalars().all()

        student_ids = {e.student_id for e in rows}
        class_ids = {e.class_id for e in rows if e.class_id}
        names = await self._student_names(student_ids)
        class_names = await self._class_names(class_ids)

        items = []
        for e in rows:
            name = names.get(e.student_id, f"Student #{e.student_id}")
            class_label = class_names.get(e.class_id) if e.class_id else None
            items.append(
                TimelineItem(
                    id=f"academic:{e.id}",
                    event_type="academic.enrolled",
                    timestamp=e.enrolled_at,
                    actor="system",
                    entity=name,
                    description=(
                        f"Enrolled in {class_label}"
                        if class_label
                        else "Enrollment recorded"
                    )
                    + f" · {e.status}",
                    severity="success" if e.status == "active" else "info",
                    source="academic",
                    metadata={
                        "student_id": e.student_id,
                        "class_id": e.class_id,
                        "academic_year_id": e.academic_year_id,
                        "status": e.status,
                    },
                    deep_link=f"/students/{e.student_id}/360",
                )
            )
        return items, count

    async def _fetch_admissions(
        self,
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = select(AdmissionApplication)
        conditions = []
        if campus_id is not None:
            conditions.append(AdmissionApplication.campus_id == campus_id)
        if filters.start:
            conditions.append(AdmissionApplication.created_at >= filters.start)
        if filters.end:
            conditions.append(AdmissionApplication.created_at <= filters.end)
        if filters.event_type:
            event_conditions = self._event_conditions("admissions", filters.event_type, AdmissionApplication)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)
        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(AdmissionApplication.created_at.desc()).limit(need)
            )
        ).scalars().all()

        items = []
        for app in rows:
            status = app.status or "inquiry"
            items.append(
                TimelineItem(
                    id=f"admissions:{app.id}",
                    event_type=f"admissions.{status}",
                    timestamp=app.created_at,
                    actor="system",
                    entity=app.applicant_name or f"Application #{app.id}",
                    description=f"Admission status → {status.replace('_', ' ')}",
                    severity=(
                        "warning" if status == "rejected" else (
                            "success"
                            if status in ("enrolled", "student_created", "fee_paid")
                            else "info"
                        )
                    ),
                    source="admissions",
                    metadata={
                        "application_id": app.id,
                        "status": status,
                        "program_id": app.program_id,
                    },
                    deep_link=f"/admissions/{app.id}",
                )
            )
        return items, count

    async def _fetch_risk(
        self,
        role: str,
        campus_id: Optional[int],
        filters: TimelineFilters,
        need: int,
    ) -> tuple[list[TimelineItem], int]:
        q = select(RiskFinding)
        conditions = []
        if campus_id is not None:
            conditions.append(RiskFinding.campus_id == campus_id)
        if filters.start:
            conditions.append(RiskFinding.detected_at >= filters.start)
        if filters.end:
            conditions.append(RiskFinding.detected_at <= filters.end)
        if filters.entity_type == "student" and filters.entity_id:
            conditions.append(RiskFinding.student_id == filters.entity_id)
        if filters.event_type:
            event_conditions = self._event_conditions("risk", filters.event_type, RiskFinding)
            if event_conditions is None:
                return [], 0
            conditions.extend(event_conditions)
        # Finance-category findings hidden from staff/teacher (RBAC).
        if role not in FINANCIAL_ROLES:
            conditions.append(RiskFinding.category != "finance")
        q = q.where(*conditions)
        count = (
            await self.session.execute(select(func.count()).select_from(q.subquery()))
        ).scalar() or 0
        rows = (
            await self.session.execute(
                q.order_by(RiskFinding.detected_at.desc()).limit(need)
            )
        ).scalars().all()

        student_ids = {f.student_id for f in rows if f.student_id}
        names = await self._student_names(student_ids)

        items = []
        for f in rows:
            name = (
                names.get(f.student_id, f"Student #{f.student_id}")
                if f.student_id
                else f"{f.entity_type} #{f.entity_id}"
            )
            items.append(
                TimelineItem(
                    id=f"risk:{f.id}",
                    event_type=f"risk.{f.category}",
                    timestamp=f.detected_at,
                    actor="risk-engine",
                    entity=name,
                    description=f"{f.reason} — recommended: {f.recommended_action}",
                    severity=(
                        "critical" if f.severity == "critical" else (
                            "warning"
                            if f.severity == "high"
                            else "info"
                        )
                    ),
                    source="risk",
                    metadata={
                        "rule_code": f.rule_code,
                        "category": f.category,
                        "score": f.score,
                        "status": f.status,
                    },
                    deep_link=(
                        f"/students/{f.student_id}/360"
                        if f.student_id
                        else "/risk"
                    ),
                )
            )
        return items, count

    # ------------------------------------------------------------------
    # Event-type filter helper
    # ------------------------------------------------------------------

    @staticmethod
    def _event_conditions(
        source: str, event_type: str, model
    ) -> Optional[list]:
        """Translate an ``event_type`` filter into per-source SQL conditions.

        Event types are source-prefixed (``audit.student.create``,
        ``fees.payment``, ``workflow.approve`` …). Returns ``None`` when
        the event type cannot belong to ``source`` (the source is then
        excluded); returns ``[]`` for source-level wildcard matches.
        """
        prefix = f"{source}."
        if event_type == source:
            return []
        if not event_type.startswith(prefix):
            return None
        suffix = event_type[len(prefix):]

        if source == "audit":
            # audit.{resource}.{action} — action is stored uppercase.
            parts = suffix.split(".")
            resource = parts[0]
            conditions = [model.resource_type == resource]
            if len(parts) >= 2 and parts[1]:
                conditions.append(func.lower(model.action) == parts[1].lower())
            return conditions
        if source == "workflow":
            return [func.lower(model.action) == suffix.lower()] if suffix else []
        if source == "notification":
            return [model.type == suffix] if suffix else []
        if source == "fees":
            # fees.payment is the only payment event type.
            return [] if suffix == "payment" else None
        if source == "academic":
            # academic.enrolled is the only enrollment event type.
            return [] if suffix == "enrolled" else None
        if source == "admissions":
            return [model.status == suffix] if suffix else []
        if source == "risk":
            return [model.category == suffix] if suffix else []
        return None

    # ------------------------------------------------------------------
    # Small batched lookup helpers
    # ------------------------------------------------------------------

    async def _student_names(
        self, student_ids: set[int]
    ) -> dict[int, str]:
        if not student_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Student.id, Student.first_name, Student.last_name).where(
                    Student.id.in_(student_ids)
                )
            )
        ).all()
        return {
            r[0]: f"{r[1]} {r[2]}".strip() or f"Student #{r[0]}" for r in rows
        }

    async def _class_names(self, class_ids: set[int]) -> dict[int, str]:
        if not class_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Class.id, Class.name).where(Class.id.in_(class_ids))
            )
        ).all()
        return {r[0]: r[1] for r in rows}
