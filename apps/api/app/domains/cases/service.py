"""Operational Case Management — service layer.

Implements the full detect → assign → investigate → act → verify →
resolve → audit workflow on top of the P7 intelligence layer:

- ``create_case`` — manual cases and promotions from P7 findings
  (risk / data-quality), which are *referenced*, never duplicated.
- Controlled lifecycle: every transition is validated against
  ``CASE_TRANSITIONS`` and appends an immutable ``CaseEvent``.
- SLA engine: ``due_at`` from campus/global ``CaseSLAConfig`` defaults;
  derived states (ON_TRACK / DUE_SOON / OVERDUE / RESOLVED) are always
  calculated, never stored.
- Escalation: deterministic — open cases past ``escalation_after_hours``
  are escalated with an event + notification.
- Metrics/workload: DB-side aggregation for the operations dashboard.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.audit.service import AuditService
from app.domains.cases.models import (
    CASE_EVENT_ASSIGNED,
    CASE_EVENT_CLOSED,
    CASE_EVENT_COMMENT_ADDED,
    CASE_EVENT_CREATED,
    CASE_EVENT_DUE_DATE_CHANGED,
    CASE_EVENT_ESCALATED,
    CASE_EVENT_EVIDENCE_ADDED,
    CASE_EVENT_PRIORITY_CHANGED,
    CASE_EVENT_REASSIGNED,
    CASE_EVENT_REOPENED,
    CASE_EVENT_RESOLVED,
    CASE_EVENT_STATUS_CHANGED,
    CASE_EVIDENCE_KINDS,
    CASE_PRIORITIES,
    CASE_SOURCE_DATA_QUALITY,
    CASE_SOURCE_MANUAL,
    CASE_SOURCE_RISK_FINDING,
    CASE_STATUS_CLOSED,
    CASE_STATUS_OPEN,
    CASE_STATUS_RESOLVED,
    CASE_TERMINAL_STATUSES,
    CASE_TRANSITIONS,
    CASE_TYPES,
    CASE_VALID_SOURCES,
    CASE_VALID_STATUSES,
    Case,
    CaseComment,
    CaseEvent,
    CaseEvidence,
    CaseSLAConfig,
)

logger = logging.getLogger(__name__)

#: Roles that may view/work cases.
CASE_ROLES = {"admin", "principal", "staff"}

#: Roles that may resolve/close/reassign/escalate cases.
CASE_LEAD_ROLES = {"admin", "principal"}

#: Default SLA (hours) when no config row exists — conservative fallback.
DEFAULT_SLA_HOURS = {
    "critical": 4.0,
    "high": 24.0,
    "medium": 72.0,
    "low": 168.0,
}

#: Default escalation multiplier over the SLA when no config row exists.
DEFAULT_ESCALATION_MULTIPLIER = 2.0

#: Severity ordering used in queue sorting.
PRIORITY_RANK = case(
    (Case.priority == "critical", 0),
    (Case.priority == "high", 1),
    (Case.priority == "medium", 2),
    (Case.priority == "low", 3),
    else_=4,
)

#: How close to the deadline "due soon" begins (fraction of after_hours).
DUE_SOON_FRACTION = 0.25


def _aware_utc(value: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """Normalise naive DB datetimes (SQLite) to UTC-aware for comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value


class CaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # SLA helpers
    # ------------------------------------------------------------------

    async def _sla_for(
        self,
        campus_id: Optional[int],
        case_type: str,
        priority: str,
    ) -> CaseSLAConfig | None:
        """Effective SLA config: campus override, else global default row."""
        if campus_id is not None:
            row = (
                await self.session.execute(
                    select(CaseSLAConfig).where(
                        CaseSLAConfig.campus_id == campus_id,
                        CaseSLAConfig.case_type == case_type,
                        CaseSLAConfig.priority == priority,
                        CaseSLAConfig.enabled.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if row is not None:
                return row
        return (
            await self.session.execute(
                select(CaseSLAConfig).where(
                    CaseSLAConfig.campus_id.is_(None),
                    CaseSLAConfig.case_type == case_type,
                    CaseSLAConfig.priority == priority,
                    CaseSLAConfig.enabled.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def _compute_due_at(
        self,
        campus_id: Optional[int],
        case_type: str,
        priority: str,
        created_at: Optional[datetime.datetime] = None,
    ) -> Optional[datetime.datetime]:
        """Deadline from the SLA config, falling back to priority defaults."""
        created_at = created_at or datetime.datetime.now(datetime.timezone.utc)
        sla = await self._sla_for(campus_id, case_type, priority)
        hours = sla.after_hours if sla and sla.after_hours else DEFAULT_SLA_HOURS.get(priority)
        if hours is None:
            return None
        return created_at + datetime.timedelta(hours=hours)

    async def _escalation_hours_for(
        self, campus_id: Optional[int], case_type: str, priority: str
    ) -> Optional[float]:
        sla = await self._sla_for(campus_id, case_type, priority)
        if sla is None:
            hours = DEFAULT_SLA_HOURS.get(priority)
            return hours * DEFAULT_ESCALATION_MULTIPLIER if hours else None
        if sla.escalation_after_hours is not None:
            return sla.escalation_after_hours
        return (
            sla.after_hours * DEFAULT_ESCALATION_MULTIPLIER
            if sla.after_hours
            else None
        )

    @staticmethod
    def sla_state(
        case: Case, now: Optional[datetime.datetime] = None
    ) -> str:
        """Derived SLA state — never stored, always calculated."""
        if case.status in CASE_TERMINAL_STATUSES:
            return "RESOLVED"
        if case.due_at is None:
            return "ON_TRACK"
        now = now or datetime.datetime.now(datetime.timezone.utc)
        due_at = _aware_utc(case.due_at) or case.due_at
        created = _aware_utc(case.created_at) or case.created_at or due_at
        if due_at < now:
            return "OVERDUE"
        # DUE_SOON when within the last 25% of the window (or <6h away).
        total = max((due_at - created).total_seconds(), 1.0)
        remaining = (due_at - now).total_seconds()
        if remaining <= max(total * DUE_SOON_FRACTION, 6 * 3600):
            return "DUE_SOON"
        return "ON_TRACK"

    # ------------------------------------------------------------------
    # Event + audit plumbing
    # ------------------------------------------------------------------

    async def _next_seq(self, case_id: int) -> int:
        row = (
            await self.session.execute(
                select(func.coalesce(func.max(CaseEvent.event_seq), 0)).where(
                    CaseEvent.case_id == case_id
                )
            )
        ).scalar_one()
        return (row or 0) + 1

    async def _add_event(
        self,
        case: Case,
        event_type: str,
        *,
        actor_id: Optional[int] = None,
        actor_name: Optional[str] = None,
        message: str = "",
        data: Optional[dict] = None,
    ) -> CaseEvent:
        seq = await self._next_seq(case.id)
        event = CaseEvent(
            case_id=case.id,
            event_seq=seq,
            event_type=event_type,
            actor_id=actor_id,
            actor_name=actor_name,
            message=message,
            data=data,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def _audit(
        self,
        action: str,
        resource_id: str,
        user_id: Optional[int],
        details: dict,
        campus_id: Optional[int],
    ) -> None:
        await AuditService(self.session).record(
            user_id=user_id,
            username=None,
            action=action,
            resource_type="case",
            resource_id=resource_id,
            details=details,
            campus_id=campus_id,
        )
        await self.session.flush()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def _get_case(
        self, case_id: int, campus_id: Optional[int]
    ) -> Case:
        q = select(Case).where(Case.id == case_id)
        if campus_id is not None:
            q = q.where(Case.campus_id == campus_id)
        case = (await self.session.execute(q)).scalar_one_or_none()
        if case is None:
            raise NotFoundError("Case not found")
        return case

    async def get_case_detail(
        self, case_id: int, campus_id: Optional[int]
    ) -> dict[str, Any]:
        case = await self._get_case(case_id, campus_id)
        events = (
            (
                await self.session.execute(
                    select(CaseEvent)
                    .where(CaseEvent.case_id == case.id)
                    .order_by(CaseEvent.event_seq.asc())
                )
            )
            .scalars()
            .all()
        )
        comments = (
            (
                await self.session.execute(
                    select(CaseComment)
                    .where(CaseComment.case_id == case.id)
                    .order_by(CaseComment.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        evidence = (
            (
                await self.session.execute(
                    select(CaseEvidence)
                    .where(CaseEvidence.case_id == case.id)
                    .order_by(CaseEvidence.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        assignee_name = None
        if case.assigned_to is not None:
            assignee_name = await self._user_name(case.assigned_to)
        return {
            "case": case,
            "events": events,
            "comments": comments,
            "evidence": evidence,
            "assignee_name": assignee_name,
            "sla_state": self.sla_state(case),
        }

    async def _user_name(self, user_id: int) -> Optional[str]:
        from app.domains.auth.models import User

        u = await self.session.get(User, user_id)
        return u.display_name if u else None

    async def list_cases(
        self,
        campus_id: Optional[int],
        *,
        view: str = "all",
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        case_type: Optional[str] = None,
        assignee_id: Optional[int] = None,
        source_type: Optional[str] = None,
        overdue_only: bool = False,
        due_soon_only: bool = False,
        search: Optional[str] = None,
        sort: str = "updated",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Case], int]:
        """Database-side work-queue query — never loads the full table.

        ``view`` shortcuts: my / unassigned / open / overdue / due_soon /
        resolved / all.
        """
        base = []
        if campus_id is not None:
            base.append(Case.campus_id == campus_id)

        if view == "my":
            if user_id is None:
                return [], 0
            base.append(Case.assigned_to == user_id)
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
        elif view == "unassigned":
            base.append(Case.assigned_to.is_(None))
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
        elif view == "open":
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
        elif view == "overdue":
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
            base.append(Case.due_at.isnot(None))
            base.append(Case.due_at < datetime.datetime.now(datetime.timezone.utc))
        elif view == "due_soon":
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
            base.append(Case.due_at.isnot(None))
            base.append(Case.due_at >= datetime.datetime.now(datetime.timezone.utc))
        elif view == "resolved":
            base.append(Case.status.in_(CASE_TERMINAL_STATUSES))

        if status is not None:
            if status not in CASE_VALID_STATUSES:
                return [], 0
            base.append(Case.status == status)
        if priority is not None:
            if priority not in CASE_PRIORITIES:
                return [], 0
            base.append(Case.priority == priority)
        if case_type is not None:
            if case_type not in CASE_TYPES:
                return [], 0
            base.append(Case.case_type == case_type)
        if assignee_id is not None:
            base.append(Case.assigned_to == assignee_id)
        if source_type is not None:
            if source_type not in CASE_VALID_SOURCES:
                return [], 0
            base.append(Case.source_type == source_type)
        if overdue_only:
            base.append(Case.due_at.isnot(None))
            base.append(Case.due_at < datetime.datetime.now(datetime.timezone.utc))
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
        if due_soon_only:
            base.append(Case.due_at.isnot(None))
            base.append(Case.due_at >= datetime.datetime.now(datetime.timezone.utc))
            base.append(Case.status.notin_(CASE_TERMINAL_STATUSES))
        if search:
            needle = f"%{search.strip()}%"
            base.append(
                (Case.case_number.ilike(needle))
                | (Case.title.ilike(needle))
            )

        total = (
            await self.session.execute(
                select(func.count(Case.id)).where(*base)
            )
        ).scalar() or 0

        order = {
            "priority": (PRIORITY_RANK.asc(), Case.created_at.desc()),
            "due": (Case.due_at.asc().nullslast(), Case.created_at.desc()),
            "created": (Case.created_at.desc(),),
            "updated": (Case.updated_at.desc(),),
        }.get(sort, (Case.updated_at.desc(),))

        q = (
            select(Case)
            .where(*base)
            .order_by(*order)
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.session.execute(q)).scalars().all()
        return rows, total

    async def get_overview(
        self, campus_id: Optional[int], user_id: Optional[int]
    ) -> dict[str, Any]:
        """Counts for the work-queue view chips + operations dashboard."""
        now = datetime.datetime.now(datetime.timezone.utc)
        open_base = [Case.status.notin_(CASE_TERMINAL_STATUSES)]
        if campus_id is not None:
            open_base.append(Case.campus_id == campus_id)

        by_status = (
            await self.session.execute(
                select(Case.status, func.count(Case.id))
                .where(
                    *([Case.campus_id == campus_id] if campus_id is not None else []),
                    Case.status.in_(CASE_VALID_STATUSES),
                )
                .group_by(Case.status)
            )
        ).all()
        status_counts = {s: n for s, n in by_status}
        open_total = sum(
            n for s, n in by_status if s not in CASE_TERMINAL_STATUSES
        )

        critical = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base, Case.priority == "critical"
                )
            )
        ).scalar() or 0
        overdue = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base,
                    Case.due_at.isnot(None),
                    Case.due_at < now,
                )
            )
        ).scalar() or 0
        due_today = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base,
                    Case.due_at.isnot(None),
                    Case.due_at <= now + datetime.timedelta(hours=24),
                )
            )
        ).scalar() or 0
        my_open = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base, Case.assigned_to == user_id
                )
            )
        ).scalar() or 0
        unassigned = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base, Case.assigned_to.is_(None)
                )
            )
        ).scalar() or 0

        return {
            "open": open_total,
            "critical": critical,
            "overdue": overdue,
            "due_today": due_today,
            "my_open": my_open,
            "unassigned": unassigned,
            "by_status": status_counts,
            "generated_at": now.isoformat(),
        }

    async def get_metrics(
        self, campus_id: Optional[int]
    ) -> dict[str, Any]:
        """Operational workflow metrics, all computed from real case data."""
        now = datetime.datetime.now(datetime.timezone.utc)
        open_base = [Case.status.notin_(CASE_TERMINAL_STATUSES)]
        campus_base = (
            [Case.campus_id == campus_id] if campus_id is not None else []
        )

        open_total = (
            await self.session.execute(
                select(func.count(Case.id)).where(*open_base, *campus_base)
            )
        ).scalar() or 0
        critical = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base, *campus_base, Case.priority == "critical"
                )
            )
        ).scalar() or 0
        overdue = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base, *campus_base,
                    Case.due_at.isnot(None), Case.due_at < now,
                )
            )
        ).scalar() or 0
        due_today = (
            await self.session.execute(
                select(func.count(Case.id)).where(
                    *open_base, *campus_base,
                    Case.due_at.isnot(None),
                    Case.due_at <= now + datetime.timedelta(hours=24),
                )
            )
        ).scalar() or 0

        by_type = dict(
            (
                await self.session.execute(
                    select(Case.case_type, func.count(Case.id))
                    .where(*open_base, *campus_base)
                    .group_by(Case.case_type)
                )
            ).all()
        )
        by_priority = dict(
            (
                await self.session.execute(
                    select(Case.priority, func.count(Case.id))
                    .where(*open_base, *campus_base)
                    .group_by(Case.priority)
                )
            ).all()
        )

        # Resolution times (hours) from resolved/closed cases.
        rows = (
            await self.session.execute(
                select(
                    (func.julianday(Case.resolved_at) - func.julianday(Case.created_at)) * 24
                ).where(
                    *campus_base,
                    Case.resolved_at.isnot(None),
                    Case.created_at.isnot(None),
                )
            )
        ).scalars().all()
        if rows:
            avg = sum(rows) / len(rows)
            sorted_ = sorted(rows)
            mid = len(sorted_) // 2
            median = (
                sorted_[mid]
                if len(sorted_) % 2
                else (sorted_[mid - 1] + sorted_[mid]) / 2
            )
            avg_resolution_hours = round(avg, 2)
            median_resolution_hours = round(median, 2)
            resolution_rate = round(
                len(rows) / max(open_total + len(rows), 1) * 100, 1
            )
        else:
            avg_resolution_hours = None
            median_resolution_hours = None
            resolution_rate = None

        # SLA compliance: resolved-on-time / resolved.
        on_time = 0
        for c_id, created, resolved, due in (
            await self.session.execute(
                select(Case.id, Case.created_at, Case.resolved_at, Case.due_at).where(
                    *campus_base,
                    Case.resolved_at.isnot(None),
                )
            )
        ).all():
            if due is not None and resolved is not None and due >= resolved:
                on_time += 1
        sla_compliance = (
            round(on_time / len(rows) * 100, 1) if rows else None
        )

        return {
            "open": open_total,
            "critical": critical,
            "overdue": overdue,
            "due_today": due_today,
            "by_type": by_type,
            "by_priority": by_priority,
            "avg_resolution_hours": avg_resolution_hours,
            "median_resolution_hours": median_resolution_hours,
            "resolution_rate": resolution_rate,
            "sla_compliance": sla_compliance,
            "generated_at": now.isoformat(),
        }

    async def get_workload(
        self, campus_id: Optional[int]
    ) -> list[dict[str, Any]]:
        """Open-case workload per assignee (admin decision support)."""

        now = datetime.datetime.now(datetime.timezone.utc)
        scope = [Case.status.notin_(CASE_TERMINAL_STATUSES)]
        if campus_id is not None:
            scope.append(Case.campus_id == campus_id)
        rows = (
            await self.session.execute(
                select(Case.assigned_to, func.count(Case.id))
                .where(*scope, Case.assigned_to.isnot(None))
                .group_by(Case.assigned_to)
            )
        ).all()

        result = []
        for assignee_id, count in rows:
            critical = (
                await self.session.execute(
                    select(func.count(Case.id)).where(
                        *scope,
                        Case.assigned_to == assignee_id,
                        Case.priority == "critical",
                    )
                )
            ).scalar() or 0
            overdue = (
                await self.session.execute(
                    select(func.count(Case.id)).where(
                        *scope,
                        Case.assigned_to == assignee_id,
                        Case.due_at.isnot(None),
                        Case.due_at < now,
                    )
                )
            ).scalar() or 0
            name = await self._user_name(assignee_id)
            result.append(
                {
                    "assignee_id": assignee_id,
                    "assignee_name": name,
                    "open_cases": count,
                    "critical_cases": critical,
                    "overdue_cases": overdue,
                }
            )
        result.sort(key=lambda r: (r["overdue_cases"], r["critical_cases"]), reverse=True)
        return result

    async def list_assignable_users(
        self, campus_id: Optional[int], current_role: str
    ) -> list[dict[str, Any]]:
        """Users the current actor may assign cases to (same campus, staff+)."""
        from app.domains.auth.models import User

        q = select(User.id, User.display_name, User.role).where(
            User.is_active.is_(True),
            User.role.in_(["admin", "principal", "staff", "accountant"]),
        )
        if campus_id is not None:
            q = q.where(User.campus_id == campus_id)
        rows = (await self.session.execute(q)).all()
        return [
            {"id": uid, "name": name, "role": role} for uid, name, role in rows
        ]

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    async def _generate_case_number(self) -> str:
        """Deterministic next case number (DMAS-XXXXXX)."""
        row = (
            await self.session.execute(
                select(func.max(Case.id))
            )
        ).scalar_one()
        return f"DMAS-{(row or 0) + 1:06d}"

    async def create_case(
        self,
        *,
        campus_id: Optional[int],
        actor_user_id: Optional[int],
        actor_name: Optional[str],
        title: str,
        description: Optional[str] = None,
        case_type: str = "administrative",
        priority: Optional[str] = None,
        source_type: str = CASE_SOURCE_MANUAL,
        source_id: Optional[int] = None,
        student_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        due_at: Optional[datetime.datetime] = None,
    ) -> Case:
        if not title or not title.strip():
            raise ValidationError("A case title is required")
        if case_type not in CASE_TYPES:
            raise ValidationError(f"Invalid case type: {case_type}")
        priority = priority or "medium"
        if priority not in CASE_PRIORITIES:
            raise ValidationError(f"Invalid priority: {priority}")
        if source_type not in CASE_VALID_SOURCES:
            raise ValidationError(f"Invalid source: {source_type}")
        if source_type != CASE_SOURCE_MANUAL:
            if source_id is None:
                raise ValidationError("source_id is required for a referenced case")
            await self._validate_source(campus_id, source_type, source_id)
            if priority == "medium":
                priority = await self._source_priority(
                    campus_id, source_type, source_id, priority
                )

        now = datetime.datetime.now(datetime.timezone.utc)
        due_at = due_at or await self._compute_due_at(
            campus_id, case_type, priority, created_at=now
        )

        case = Case(
            case_number=await self._generate_case_number(),
            campus_id=campus_id,
            title=title.strip(),
            description=description,
            case_type=case_type,
            priority=priority,
            original_priority=priority,
            status=CASE_STATUS_OPEN,
            source_type=source_type,
            source_id=source_id,
            student_id=student_id,
            created_by=actor_user_id,
            assigned_to=assigned_to,
            assigned_at=now if assigned_to else None,
            due_at=due_at,
            version=1,
        )
        self.session.add(case)
        await self.session.flush()

        if assigned_to:
            target_name = await self._user_name(assigned_to)
            await self._add_event(
                case,
                CASE_EVENT_ASSIGNED,
                actor_id=actor_user_id,
                actor_name=actor_name,
                message=f"Assigned to {target_name or assigned_to}",
                data={"assignee": assigned_to},
            )

        await self._add_event(
            case,
            CASE_EVENT_CREATED,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message="Case created",
            data={
                "case_type": case_type,
                "priority": priority,
                "source_type": source_type,
                "source_id": source_id,
            },
        )
        await self._audit(
            "CREATE",
            str(case.id),
            actor_user_id,
            {"case_number": case.case_number, "case_type": case_type, "source": source_type},
            campus_id,
        )
        if assigned_to:
            await self._notify_assignment(case, assigned_to, actor_name or "A colleague")
        return case

    async def _validate_source(
        self,
        campus_id: Optional[int],
        source_type: str,
        source_id: int,
    ) -> None:
        if source_type == CASE_SOURCE_RISK_FINDING:
            from app.domains.risk.models import RiskFinding

            q = select(RiskFinding.id).where(RiskFinding.id == source_id)
            if campus_id is not None:
                q = q.where(RiskFinding.campus_id == campus_id)
            if (await self.session.execute(q)).scalar_one_or_none() is None:
                raise ValidationError("Referenced risk finding does not exist")
        elif source_type == CASE_SOURCE_DATA_QUALITY:
            from app.domains.data_quality.models import DataQualityFinding

            q = select(DataQualityFinding.id).where(
                DataQualityFinding.id == source_id
            )
            if campus_id is not None:
                q = q.where(DataQualityFinding.campus_id == campus_id)
            if (await self.session.execute(q)).scalar_one_or_none() is None:
                raise ValidationError(
                    "Referenced data-quality finding does not exist"
                )

    async def _source_priority(
        self,
        campus_id: Optional[int],
        source_type: str,
        source_id: int,
        fallback: str,
    ) -> str:
        """Seed case priority from the P7 finding severity."""
        try:
            if source_type == CASE_SOURCE_RISK_FINDING:
                from app.domains.risk.models import RiskFinding

                q = select(RiskFinding.severity).where(RiskFinding.id == source_id)
                if campus_id is not None:
                    q = q.where(RiskFinding.campus_id == campus_id)
                severity = (await self.session.execute(q)).scalar_one_or_none()
            elif source_type == CASE_SOURCE_DATA_QUALITY:
                from app.domains.data_quality.models import DataQualityFinding

                q = select(DataQualityFinding.severity).where(
                    DataQualityFinding.id == source_id
                )
                if campus_id is not None:
                    q = q.where(DataQualityFinding.campus_id == campus_id)
                severity = (await self.session.execute(q)).scalar_one_or_none()
            else:
                return fallback
            return severity if severity in CASE_PRIORITIES else fallback
        except Exception:  # noqa: BLE001 — never block creation on enrichment
            return fallback

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    async def transition_status(
        self,
        case_id: int,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        new_status: str,
        reason: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Case:
        case = await self._get_case(case_id, campus_id)
        if new_status not in CASE_VALID_STATUSES:
            raise ValidationError(f"Invalid status: {new_status}")
        if new_status == case.status:
            raise ValidationError("Case is already in this status")
        if new_status not in CASE_TRANSITIONS.get(case.status, set()):
            raise ValidationError(
                f"Transition {case.status} -> {new_status} is not allowed"
            )
        if new_status == CASE_STATUS_CLOSED and case.status != CASE_STATUS_RESOLVED:
            raise ValidationError(
                "A case must be resolved before it can be closed"
            )
        self._bump_version(case, version)

        previous = case.status
        now = datetime.datetime.now(datetime.timezone.utc)
        case.status = new_status
        if new_status == CASE_STATUS_RESOLVED:
            case.resolved_at = now
            case.resolved_by = actor_user_id
            case.resolved_reason = reason
        elif new_status == CASE_STATUS_OPEN and previous in CASE_TERMINAL_STATUSES:
            # Reopen clears resolution bookkeeping.
            case.resolved_at = None
            case.resolved_by = None
            case.resolved_reason = None
        if new_status == CASE_STATUS_CLOSED:
            case.closed_at = now
            case.closed_by = actor_user_id
        await self.session.flush()

        event_type = {
            CASE_STATUS_RESOLVED: CASE_EVENT_RESOLVED,
            CASE_STATUS_CLOSED: CASE_EVENT_CLOSED,
        }.get(new_status, CASE_EVENT_STATUS_CHANGED)
        if (
            new_status == CASE_STATUS_OPEN
            and previous in CASE_TERMINAL_STATUSES
        ):
            event_type = CASE_EVENT_REOPENED

        await self._add_event(
            case,
            event_type,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message=reason or f"Status changed: {previous} → {new_status}",
            data={"from": previous, "to": new_status},
        )
        await self._audit(
            "UPDATE",
            str(case.id),
            actor_user_id,
            {"action": "status_change", "from": previous, "to": new_status, "reason": reason},
            campus_id,
        )
        return case

    async def assign_case(
        self,
        case_id: int,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        assignee_id: int,
        reason: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Case:
        case = await self._get_case(case_id, campus_id)
        assignable = {u["id"] for u in await self.list_assignable_users(campus_id, "admin")}
        if assignee_id not in assignable:
            raise ValidationError(
                "Assignee must be an active staff member of this school"
            )
        self._bump_version(case, version)

        previous = case.assigned_to
        target_name = await self._user_name(assignee_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        case.assigned_to = assignee_id
        case.assigned_at = now
        await self.session.flush()

        if previous is None:
            event_type = CASE_EVENT_ASSIGNED
            message = f"Assigned to {target_name or assignee_id}"
        else:
            event_type = CASE_EVENT_REASSIGNED
            prev_name = await self._user_name(previous)
            message = (
                f"Reassigned from {prev_name or previous} to "
                f"{target_name or assignee_id}"
            )
        if reason:
            message = f"{message} — {reason}"

        await self._add_event(
            case,
            event_type,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message=message,
            data={"from": previous, "to": assignee_id},
        )
        await self._audit(
            "UPDATE",
            str(case.id),
            actor_user_id,
            {"action": "assign", "from": previous, "to": assignee_id, "reason": reason},
            campus_id,
        )
        if previous != assignee_id:
            await self._notify_assignment(
                case, assignee_id, actor_name or "A colleague"
            )
        return case

    async def change_priority(
        self,
        case_id: int,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        new_priority: str,
        reason: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Case:
        if new_priority not in CASE_PRIORITIES:
            raise ValidationError(f"Invalid priority: {new_priority}")
        case = await self._get_case(case_id, campus_id)
        if new_priority == case.priority:
            raise ValidationError("Priority is already set to this value")
        self._bump_version(case, version)

        previous = case.priority
        case.priority = new_priority
        await self.session.flush()

        await self._add_event(
            case,
            CASE_EVENT_PRIORITY_CHANGED,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message=f"Priority changed: {previous} → {new_priority}",
            data={"from": previous, "to": new_priority, "reason": reason},
        )
        await self._audit(
            "UPDATE",
            str(case.id),
            actor_user_id,
            {"action": "priority_change", "from": previous, "to": new_priority, "reason": reason},
            campus_id,
        )
        return case

    async def set_due_date(
        self,
        case_id: int,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        due_at: Optional[datetime.datetime],
        reason: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Case:
        case = await self._get_case(case_id, campus_id)
        self._bump_version(case, version)

        previous = case.due_at
        case.due_at = due_at
        await self.session.flush()

        await self._add_event(
            case,
            CASE_EVENT_DUE_DATE_CHANGED,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message=(
                f"Deadline set to {due_at.isoformat()}" if due_at else "Deadline cleared"
            ),
            data={"from": previous.isoformat() if previous else None,
                  "to": due_at.isoformat() if due_at else None},
        )
        await self._audit(
            "UPDATE",
            str(case.id),
            actor_user_id,
            {"action": "due_date_change", "reason": reason},
            campus_id,
        )
        return case

    # ------------------------------------------------------------------
    # Comments + evidence
    # ------------------------------------------------------------------

    async def add_comment(
        self,
        case_id: int,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        body: str,
    ) -> CaseComment:
        if not body or not body.strip():
            raise ValidationError("Comment body is required")
        case = await self._get_case(case_id, campus_id)
        comment = CaseComment(
            case_id=case.id,
            author_id=actor_user_id,
            author_name=actor_name,
            body=body.strip(),
        )
        self.session.add(comment)
        await self.session.flush()

        await self._add_event(
            case,
            CASE_EVENT_COMMENT_ADDED,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message="Comment added",
            data={"comment_id": comment.id},
        )
        await self._audit(
            "COMMENT",
            str(case.id),
            actor_user_id,
            {"comment_id": comment.id},
            campus_id,
        )
        return comment

    async def add_evidence(
        self,
        case_id: int,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        *,
        kind: str,
        title: str,
        summary: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> CaseEvidence:
        if kind not in CASE_EVIDENCE_KINDS:
            raise ValidationError(f"Invalid evidence kind: {kind}")
        if not title or not title.strip():
            raise ValidationError("Evidence title is required")
        case = await self._get_case(case_id, campus_id)
        evidence = CaseEvidence(
            case_id=case.id,
            kind=kind,
            title=title.strip(),
            summary=summary,
            reference_type=reference_type,
            reference_id=reference_id,
            data=metadata,
            added_by=actor_user_id,
        )
        self.session.add(evidence)
        await self.session.flush()

        await self._add_event(
            case,
            CASE_EVENT_EVIDENCE_ADDED,
            actor_id=actor_user_id,
            actor_name=actor_name,
            message=f"Evidence added: {evidence.title}",
            data={"evidence_id": evidence.id, "kind": kind},
        )
        await self._audit(
            "ATTACH",
            str(case.id),
            actor_user_id,
            {"evidence_id": evidence.id, "kind": kind, "title": evidence.title},
            campus_id,
        )
        return evidence

    # ------------------------------------------------------------------
    # Bulk operations (audited per case)
    # ------------------------------------------------------------------

    async def bulk_assign(
        self,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        case_ids: list[int],
        assignee_id: int,
    ) -> dict[str, Any]:
        updated = []
        for cid in case_ids:
            try:
                case = await self.assign_case(
                    cid, campus_id, actor_user_id, actor_name, assignee_id
                )
                updated.append(case.id)
            except (NotFoundError, ValidationError):
                continue
        return {"updated": updated, "skipped": len(case_ids) - len(updated)}

    async def bulk_priority(
        self,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        case_ids: list[int],
        priority: str,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        updated = []
        for cid in case_ids:
            try:
                case = await self.change_priority(
                    cid, campus_id, actor_user_id, actor_name, priority, reason
                )
                updated.append(case.id)
            except (NotFoundError, ValidationError):
                continue
        return {"updated": updated, "skipped": len(case_ids) - len(updated)}

    async def bulk_status(
        self,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        case_ids: list[int],
        status: str,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        updated = []
        for cid in case_ids:
            try:
                case = await self.transition_status(
                    cid, campus_id, actor_user_id, actor_name, status, reason
                )
                updated.append(case.id)
            except (NotFoundError, ValidationError):
                continue
        return {"updated": updated, "skipped": len(case_ids) - len(updated)}

    async def bulk_set_due_date(
        self,
        campus_id: Optional[int],
        actor_user_id: int,
        actor_name: Optional[str],
        case_ids: list[int],
        due_at: Optional[datetime.datetime],
    ) -> dict[str, Any]:
        updated = []
        for cid in case_ids:
            try:
                case = await self.set_due_date(
                    cid, campus_id, actor_user_id, actor_name, due_at
                )
                updated.append(case.id)
            except (NotFoundError, ValidationError):
                continue
        return {"updated": updated, "skipped": len(case_ids) - len(updated)}

    # ------------------------------------------------------------------
    # Escalation (deterministic, configured)
    # ------------------------------------------------------------------

    async def run_escalation(
        self,
        campus_id: Optional[int],
        actor_user_id: Optional[int] = None,
        actor_name: Optional[str] = None,
        now: Optional[datetime.datetime] = None,
    ) -> dict[str, Any]:
        """Escalate open cases past their configured escalation deadline.

        Deterministic rule: status not terminal, ``due_at`` present, and
        ``now - due_at >= escalation_after_hours``.  Escalated cases get an
        ESCALATED event and a notification to leadership.  Idempotent — an
        already-escalated case is never re-notified.
        """
        now = now or datetime.datetime.now(datetime.timezone.utc)
        # Escalation only fires once ``now >= due_at + escalation_after_hours``
        # (and the multiplier is >= 1), so any future-due case can never
        # escalate — bounding the platform-wide scan to due/past-due rows.
        base = [
            Case.status.notin_(CASE_TERMINAL_STATUSES),
            Case.due_at.isnot(None),
            Case.due_at <= now,
        ]
        if campus_id is not None:
            base.append(Case.campus_id == campus_id)
        cases = (
            (await self.session.execute(select(Case).where(*base))).scalars().all()
        )

        escalated = []
        for item in cases:
            if item.due_at is None:
                continue
            # Per-case campus config (the scheduler scope is platform-wide).
            esc_hours = await self._escalation_hours_for(
                item.campus_id, item.case_type, item.priority
            )
            if esc_hours is None:
                continue
            if item.escalated_at is not None:
                continue  # already escalated — never re-notify
            due_at = _aware_utc(item.due_at) or item.due_at
            threshold = due_at + datetime.timedelta(hours=esc_hours)
            if now < threshold:
                continue
            item.escalated_at = now
            await self.session.flush()
            await self._add_event(
                item,
                CASE_EVENT_ESCALATED,
                actor_id=actor_user_id,
                actor_name=actor_name or "System",
                message="Case escalated — past the escalation deadline",
                data={"escalation_after_hours": esc_hours},
            )
            await self._audit(
                "ESCALATE",
                str(item.id),
                actor_user_id,
                {"escalation_after_hours": esc_hours},
                # Scope the audit record to the case's own campus even when
                # run from the platform scheduler (campus_id=None).
                item.campus_id,
            )
            await self._notify_escalation(item, campus_id)
            escalated.append(item.id)
        return {"escalated": escalated, "count": len(escalated)}

    # ------------------------------------------------------------------
    # Notifications (reuses the existing notification system)
    # ------------------------------------------------------------------

    async def _notify_assignment(
        self, case: Case, assignee_id: int, actor_name: str
    ) -> None:
        try:
            from app.domains.notifications.service import NotificationService

            svc = NotificationService(self.session)
            await svc.create_notification(
                user_id=assignee_id,
                type="case_assigned",
                title=f"Case {case.case_number} assigned to you",
                message=f"{actor_name} assigned you {case.title} ({case.case_type}).",
                data={"case_id": case.id, "case_number": case.case_number},
            )
            await self.session.flush()
        except Exception:  # noqa: BLE001 — notifications are best-effort
            return

    async def _notify_escalation(
        self, case: Case, campus_id: Optional[int]
    ) -> None:
        try:
            from app.domains.auth.models import User
            from app.domains.notifications.service import NotificationService

            # Always notify leadership of the case's own campus — when this
            # runs from the platform-level scheduler (campus_id=None) the
            # caller's scope must not leak notifications across campuses.
            target_campus = case.campus_id if case.campus_id is not None else campus_id
            q = select(User.id).where(
                User.is_active.is_(True),
                User.role.in_(["admin", "principal"]),
            )
            if target_campus is not None:
                q = q.where(User.campus_id == target_campus)
            target_ids = [r[0] for r in (await self.session.execute(q)).all()]
            if not target_ids:
                return
            svc = NotificationService(self.session)
            for uid in target_ids:
                await svc.create_notification(
                    user_id=uid,
                    type="case_escalated",
                    title=f"Case {case.case_number} escalated",
                    message=(
                        f"{case.title} is past its escalation deadline and "
                        "requires attention."
                    ),
                    data={"case_id": case.id, "case_number": case.case_number},
                )
            await self.session.flush()
        except Exception:  # noqa: BLE001 — notifications are best-effort
            return

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    @staticmethod
    def _bump_version(case: Case, expected_version: Optional[int]) -> None:
        """Optimistic-lock guard for targeted updates (concurrent edits)."""
        if expected_version is not None and case.version != expected_version:
            raise ValidationError(
                "This case was modified by someone else. Reload and retry."
            )
        case.version += 1
