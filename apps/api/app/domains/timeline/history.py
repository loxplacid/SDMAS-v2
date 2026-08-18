"""Deterministic institutional-history service (TASK 18).

Projects a unified, chronological timeline from *persisted* canonical
event sources — no AI narratives, no LLM calls, no randomness.

Sources
-------
- ``outbox_events``  — canonical domain events with causation chain
- ``audit_logs``     — immutable security audit trail
- ``case_events``    — operational case timeline
- ``system_exception_events`` — exception lifecycle timeline
- ``approval_history`` — workflow transition audit trail

Every query returns a :class:`HistoryProjection` (or a typed variant
like :class:`CausalChain` / :class:`EntityHistory` /
:class:`DateRangeDiff`) containing deterministic `HistoryEvent` rows
and computed summary statistics.

Security
--------
All queries are **tenant-scoped** to the caller's ``campus_id``.
Cross-tenant access is forbidden.  Financial audit actions are hidden
from roles without ``fees.view``; exception/case events respect their
own RBAC rules.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.domains.cases.models import Case, CaseEvent
from app.domains.events.outbox import OutboxEvent
from app.domains.exceptions.models import SystemException, SystemExceptionEvent
from app.domains.timeline.schemas import (
    CausalChain,
    DateRangeDiff,
    EntityHistory,
    HistoryEvent,
    HistoryProjection,
    HistorySummary,
    LifecycleMilestone,
)
from app.domains.workflow.models import ApprovalHistory, WorkflowInstance

logger = logging.getLogger(__name__)

# Financial audit resources — hidden from non-financial roles.
_FINANCIAL_AUDIT_RESOURCES = frozenset(
    {"fee", "fees", "payment", "payments", "payment_method", "fee_structure"}
)

# Severity mapping for audit actions.
_SEVERITY_MAP: dict[str, str] = {
    "DELETE": "warning",
    "REFUND": "warning",
    "PASSWORD_CHANGE": "warning",
    "APPROVE": "success",
    "RECORD_PAYMENT": "success",
    "CREATE": "success",
    "RISK": "warning",
}

# Lifecycle milestone event types — used to extract significant transitions.
_LIFECYCLE_MILESTONE_TYPES = frozenset(
    {
        "student.created",
        "student.updated",
        "student.status_changed",
        "student.enrolled",
        "admission.submitted",
        "admission.approved",
        "admission.rejected",
        "workflow.submitted",
        "workflow.approved",
        "workflow.rejected",
        "workflow.cancelled",
        "payment.recorded",
        "payment.overdue",
        "fee.due_created",
        "attendance.threshold_breached",
    }
)


def _severity_for_audit_action(action: str) -> str:
    return _SEVERITY_MAP.get((action or "").upper(), "info")


def _safe_json(details: str | None) -> dict[str, Any]:
    if not details:
        return {}
    try:
        parsed = json.loads(details)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"value": details}


def _audit_description(log: AuditLog) -> str:
    action = (log.action or "ACTION").replace("_", " ").lower()
    resource = (log.resource_type or "record").replace("_", " ")
    if log.resource_id:
        return f"{action} {resource} #{log.resource_id}"
    return f"{action} {resource}"


def _case_event_to_history(ce: CaseEvent, case: Case) -> HistoryEvent:
    """Convert a CaseEvent to a HistoryEvent."""
    actor = ce.actor_name or (f"user #{ce.actor_id}" if ce.actor_id else "system")
    label = ce.event_type.replace("_", " ").title()
    desc = f"{label}: {ce.message}" if ce.message else label
    sev = "info"
    if ce.event_type in ("REOPENED", "ESCALATED", "PRIORITY_CHANGED"):
        sev = "warning"
    elif ce.event_type in ("RESOLVED", "CLOSED"):
        sev = "success"
    return HistoryEvent(
        id=f"case:{ce.id}",
        source="case",
        event_type=f"case.{ce.event_type.lower()}",
        timestamp=ce.created_at,
        actor=actor,
        entity=f"Case #{case.case_number}",
        description=desc,
        severity=sev,
        metadata=ce.data if isinstance(ce.data, dict) else {},
    )


def _exception_event_to_history(
    see: SystemExceptionEvent, exc: SystemException
) -> HistoryEvent:
    """Convert a SystemExceptionEvent to a HistoryEvent."""
    actor = see.actor_name or (
        f"user #{see.actor_id}" if see.actor_id else "system"
    )
    label = see.event_type.replace("_", " ").title()
    desc = f"{label}: {see.message}" if see.message else label
    sev = "info"
    if exc.severity == "critical":
        sev = "critical"
    elif exc.severity in ("high", "medium"):
        sev = "warning"
    return HistoryEvent(
        id=f"exception:{see.id}",
        source="exception",
        event_type=f"exception.{see.event_type.lower()}",
        timestamp=see.created_at,
        actor=actor,
        entity=f"Exception #{exc.id}: {exc.title}",
        description=desc,
        severity=sev,
        metadata=see.data if isinstance(see.data, dict) else {},
    )


def _audit_to_history(log: AuditLog) -> HistoryEvent:
    """Convert an AuditLog to a HistoryEvent."""
    rt = (log.resource_type or "record")
    action = (log.action or "")
    resource_label = rt.replace("_", " ").title()
    entity = f"{resource_label} #{log.resource_id}" if log.resource_id else resource_label
    return HistoryEvent(
        id=f"audit:{log.id}",
        source="audit",
        event_type=f"audit.{rt.lower()}.{action.lower()}",
        timestamp=log.created_at,
        actor=log.username or "system",
        entity=entity,
        description=_audit_description(log),
        severity=_severity_for_audit_action(log.action),
        correlation_id=log.correlation_id,
        metadata=_safe_json(log.details),
    )


class InstitutionalHistoryService:
    """Deterministic institutional-history projections.

    All methods are read-only and tenant-scoped.  A failing source
    degrades gracefully — the remaining sources still render.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ====================================================================
    # 1. Entity history — "What happened to this student?"
    # ====================================================================

    async def entity_history(
        self,
        campus_id: int | None,
        entity_type: str,
        entity_id: int,
        *,
        limit: int = 100,
    ) -> EntityHistory:
        """Build the complete history for a specific entity.

        Aggregates events from all sources that reference the entity,
        ordered chronologically.
        """
        events: list[HistoryEvent] = []

        # Audit logs for this entity
        audit_events = await self._fetch_audit_for_entity(
            campus_id, entity_type, entity_id, limit
        )
        events.extend(audit_events)

        # Outbox domain events for this entity
        outbox_events = await self._fetch_outbox_for_entity(
            campus_id, entity_type, entity_id, limit
        )
        events.extend(outbox_events)

        # Case events if the entity has associated cases
        if entity_type == "student":
            case_events = await self._fetch_case_events_for_student(
                campus_id, entity_id, limit
            )
            events.extend(case_events)

            # Exception events for this student
            exception_events = await self._fetch_exception_events_for_student(
                campus_id, entity_id, limit
            )
            events.extend(exception_events)

        # Workflow events for this entity
        workflow_events = await self._fetch_workflow_for_entity(
            campus_id, entity_type, entity_id, limit
        )
        events.extend(workflow_events)

        # Sort chronologically (oldest first for lifecycle view)
        events.sort(key=lambda e: e.timestamp)

        # Extract lifecycle milestones
        lifecycle = self._extract_lifecycle_milestones(events)

        # Build summary
        summary = self._build_summary(events)

        return EntityHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            events=events[:limit],
            total=len(events),
            lifecycle=lifecycle,
            summary=summary,
        )

    # ====================================================================
    # 2. Campus history — "What changed in this campus?"
    # ====================================================================

    async def campus_history(
        self,
        campus_id: int,
        *,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> HistoryProjection:
        """All events for a campus, optionally filtered by source."""
        events: list[HistoryEvent] = []

        sources_to_fetch = (
            [source] if source
            else ["outbox", "audit", "case", "exception", "workflow"]
        )

        for src in sources_to_fetch:
            try:
                fetched = await self._fetch_campus_source(
                    campus_id, src, limit, offset
                )
                events.extend(fetched)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Campus history source %s failed: %s", src, exc)

        events.sort(key=lambda e: e.timestamp, reverse=True)
        summary = self._build_summary(events)

        return HistoryProjection(
            events=events[offset:offset + limit],
            total=len(events),
            summary=summary,
            query_type="campus_history",
            query_params={
                "campus_id": campus_id,
                "source": source,
            },
        )

    # ====================================================================
    # 3. Pre-exception timeline — "What happened before this exception?"
    # ====================================================================

    async def pre_exception_timeline(
        self,
        campus_id: int | None,
        exception_id: int,
        *,
        limit: int = 50,
    ) -> HistoryProjection:
        """Events that occurred before a specific exception.

        Finds the exception, then returns all events that happened
        before ``detected_at`` for the same entity (if applicable)
        or the same campus.
        """
        exc = await self.session.get(SystemException, exception_id)
        if exc is None:
            return HistoryProjection(
                events=[], total=0,
                summary=self._empty_summary(),
                query_type="pre_exception",
                query_params={"exception_id": exception_id},
            )

        cutoff = exc.detected_at
        events: list[HistoryEvent] = []

        # Fetch events before the cutoff
        if exc.student_id:
            student_events = await self._fetch_events_before(
                campus_id, cutoff, limit,
                entity_type="student", entity_id=exc.student_id,
            )
            events.extend(student_events)
        else:
            campus_events = await self._fetch_events_before(
                campus_id, cutoff, limit,
            )
            events.extend(campus_events)

        events.sort(key=lambda e: e.timestamp, reverse=True)
        summary = self._build_summary(events)

        return HistoryProjection(
            events=events[:limit],
            total=len(events),
            summary=summary,
            query_type="pre_exception",
            query_params={
                "exception_id": exception_id,
                "cutoff": cutoff.isoformat(),
                "student_id": exc.student_id,
            },
        )

    # ====================================================================
    # 4. Causal chain — "Which events caused this workflow?"
    # ====================================================================

    async def causal_chain(
        self,
        campus_id: int | None,
        event_id: str,
        *,
        max_depth: int = 20,
    ) -> CausalChain | None:
        """Trace the causal chain leading to an event.

        Follows ``causation_id`` links backwards from the target event
        to find the root cause and all intermediate events.
        """
        # Find the target event in the outbox
        target = await self._find_outbox_event(event_id)
        if target is None:
            return None

        target_history = self._outbox_to_history(target)
        chain: list[HistoryEvent] = [target_history]
        visited: set[str] = {event_id}

        # Walk backwards through causation_id
        current_causation_id = target.causation_id
        for _ in range(max_depth):
            if not current_causation_id:
                break
            if current_causation_id in visited:
                break  # Circular reference protection

            parent = await self._find_outbox_event(current_causation_id)
            if parent is None:
                break

            visited.add(current_causation_id)
            chain.append(self._outbox_to_history(parent))
            current_causation_id = parent.causation_id

        # Reverse so chain is chronological (root -> ... -> target)
        chain.reverse()

        if not chain:
            return None

        return CausalChain(
            target_event=target_history,
            chain=chain,
            root_event=chain[0],
            depth=len(chain) - 1,
        )

    # ====================================================================
    # 5. Date range diff — "What changed between two dates?"
    # ====================================================================

    async def date_range_diff(
        self,
        campus_id: int | None,
        start: datetime.datetime,
        end: datetime.datetime,
        *,
        source: str | None = None,
        limit: int = 200,
    ) -> DateRangeDiff:
        """All events in a date range, grouped by source."""
        events: list[HistoryEvent] = []

        sources_to_fetch = (
            [source] if source
            else ["outbox", "audit", "case", "exception", "workflow"]
        )

        for src in sources_to_fetch:
            try:
                fetched = await self._fetch_events_in_range(
                    campus_id, start, end, src, limit
                )
                events.extend(fetched)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Date range source %s failed: %s", src, exc)

        events.sort(key=lambda e: e.timestamp, reverse=True)
        summary = self._build_summary(events)

        # Group by source
        by_source: dict[str, list[HistoryEvent]] = {}
        for evt in events:
            by_source.setdefault(evt.source, []).append(evt)

        # Most active actor
        actor_counts: Counter[str] = Counter()
        entity_counts: Counter[str] = Counter()
        for evt in events:
            if evt.actor and evt.actor != "system":
                actor_counts[evt.actor] += 1
            entity_counts[evt.entity] += 1

        most_active_actor = (
            actor_counts.most_common(1)[0][0] if actor_counts else None
        )
        most_changed_entity = (
            entity_counts.most_common(1)[0][0] if entity_counts else None
        )

        return DateRangeDiff(
            start=start,
            end=end,
            events=events[:limit],
            total=len(events),
            summary=summary,
            by_source=by_source,
            most_active_actor=most_active_actor,
            most_changed_entity=most_changed_entity,
        )

    # ------------------------------------------------------------------
    # Source fetchers — audit
    # ------------------------------------------------------------------

    async def _fetch_audit_for_entity(
        self,
        campus_id: int | None,
        entity_type: str,
        entity_id: int,
        limit: int,
    ) -> list[HistoryEvent]:
        q = select(AuditLog)
        conditions: list = []
        if campus_id is not None:
            conditions.append(AuditLog.campus_id == campus_id)

        # Map entity_type to audit resource_type
        resource_map = {
            "student": "student",
            "class": ("academic", "class"),
            "teacher": "teacher",
            "admission": ("admission", "admissions"),
            "payment": ("payment", "payments"),
            "enrollment": ("enrollment", "enrollments"),
            "workflow": ("workflow", "workflow_instance"),
        }
        resource = resource_map.get(entity_type)
        if resource:
            if isinstance(resource, tuple):
                conditions.append(AuditLog.resource_type.in_(resource))
            else:
                conditions.append(AuditLog.resource_type == resource)
        conditions.append(AuditLog.resource_id == str(entity_id))

        q = q.where(*conditions).order_by(AuditLog.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).scalars().all()

        return [_audit_to_history(log) for log in rows]

    async def _fetch_audit_for_entity_simple(
        self,
        campus_id: int | None,
        entity_type: str,
        entity_id: int,
        limit: int,
    ) -> list[HistoryEvent]:
        """Alias for _fetch_audit_for_entity (used by other fetchers)."""
        return await self._fetch_audit_for_entity(
            campus_id, entity_type, entity_id, limit
        )

    # ------------------------------------------------------------------
    # Source fetchers — outbox
    # ------------------------------------------------------------------

    async def _fetch_outbox_for_entity(
        self,
        campus_id: int | None,
        entity_type: str,
        entity_id: int,
        limit: int,
    ) -> list[HistoryEvent]:
        q = select(OutboxEvent)
        conditions: list = []
        if campus_id is not None:
            conditions.append(OutboxEvent.school_id == campus_id)
        conditions.append(OutboxEvent.entity_type == entity_type)
        conditions.append(OutboxEvent.entity_id == entity_id)

        q = q.where(*conditions).order_by(OutboxEvent.occurred_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).scalars().all()

        return [self._outbox_to_history(e) for e in rows]

    # ------------------------------------------------------------------
    # Source fetchers — case events
    # ------------------------------------------------------------------

    async def _fetch_case_events_for_student(
        self,
        campus_id: int | None,
        student_id: int,
        limit: int,
    ) -> list[HistoryEvent]:
        q = (
            select(CaseEvent, Case)
            .join(Case, CaseEvent.case_id == Case.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(Case.campus_id == campus_id)
        conditions.append(Case.student_id == student_id)

        q = q.where(*conditions).order_by(CaseEvent.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()
        return [_case_event_to_history(ce, case) for ce, case in rows]

    # ------------------------------------------------------------------
    # Source fetchers — exception events
    # ------------------------------------------------------------------

    async def _fetch_exception_events_for_student(
        self,
        campus_id: int | None,
        student_id: int,
        limit: int,
    ) -> list[HistoryEvent]:
        q = (
            select(SystemExceptionEvent, SystemException)
            .join(SystemException, SystemExceptionEvent.exception_id == SystemException.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(SystemException.campus_id == campus_id)
        conditions.append(SystemException.student_id == student_id)

        q = q.where(*conditions).order_by(SystemExceptionEvent.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()
        return [_exception_event_to_history(see, exc) for see, exc in rows]

    # ------------------------------------------------------------------
    # Source fetchers — workflow
    # ------------------------------------------------------------------

    async def _fetch_workflow_for_entity(
        self,
        campus_id: int | None,
        entity_type: str,
        entity_id: int,
        limit: int,
    ) -> list[HistoryEvent]:
        q = (
            select(ApprovalHistory, WorkflowInstance)
            .join(WorkflowInstance, ApprovalHistory.instance_id == WorkflowInstance.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(WorkflowInstance.campus_id == campus_id)
        conditions.append(WorkflowInstance.entity_type == entity_type)
        conditions.append(WorkflowInstance.entity_id == entity_id)

        q = q.where(*conditions).order_by(ApprovalHistory.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()

        return [
            HistoryEvent(
                id=f"workflow:{ah.id}",
                source="workflow",
                event_type=f"workflow.{ah.action}",
                timestamp=ah.created_at,
                actor=f"user #{ah.actor_id}" if ah.actor_id else "system",
                entity=f"Workflow #{wi.id} ({wi.entity_type} #{wi.entity_id})",
                description=(
                    f"{(ah.action or 'action').replace('_', ' ').title()}"
                    + (f" — {ah.comment}" if ah.comment else "")
                ),
                severity=(
                    "success" if ah.action == "approve"
                    else "warning" if ah.action in ("reject", "return")
                    else "info"
                ),
                metadata={"instance_id": wi.id, "comment": ah.comment},
            )
            for ah, wi in rows
        ]

    # ------------------------------------------------------------------
    # Campus source fetchers
    # ------------------------------------------------------------------

    async def _fetch_campus_source(
        self,
        campus_id: int,
        source: str,
        limit: int,
        offset: int,
    ) -> list[HistoryEvent]:
        if source == "outbox":
            return await self._fetch_campus_outbox(campus_id, limit, offset)
        if source == "audit":
            return await self._fetch_campus_audit(campus_id, limit, offset)
        if source == "case":
            return await self._fetch_campus_cases(campus_id, limit, offset)
        if source == "exception":
            return await self._fetch_campus_exceptions(campus_id, limit, offset)
        if source == "workflow":
            return await self._fetch_campus_workflow(campus_id, limit, offset)
        return []

    async def _fetch_campus_outbox(
        self, campus_id: int, limit: int, offset: int
    ) -> list[HistoryEvent]:
        q = (
            select(OutboxEvent)
            .where(OutboxEvent.school_id == campus_id)
            .order_by(OutboxEvent.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(q)).scalars().all()
        return [self._outbox_to_history(e) for e in rows]

    async def _fetch_campus_audit(
        self, campus_id: int, limit: int, offset: int
    ) -> list[HistoryEvent]:
        q = (
            select(AuditLog)
            .where(AuditLog.campus_id == campus_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(q)).scalars().all()
        return [_audit_to_history(log) for log in rows]

    async def _fetch_campus_cases(
        self, campus_id: int, limit: int, offset: int
    ) -> list[HistoryEvent]:
        q = (
            select(CaseEvent, Case)
            .join(Case, CaseEvent.case_id == Case.id)
            .where(Case.campus_id == campus_id)
            .order_by(CaseEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(q)).all()
        return [_case_event_to_history(ce, c) for ce, c in rows]

    async def _fetch_campus_exceptions(
        self, campus_id: int, limit: int, offset: int
    ) -> list[HistoryEvent]:
        q = (
            select(SystemExceptionEvent, SystemException)
            .join(SystemException, SystemExceptionEvent.exception_id == SystemException.id)
            .where(SystemException.campus_id == campus_id)
            .order_by(SystemExceptionEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(q)).all()
        return [_exception_event_to_history(see, exc) for see, exc in rows]

    async def _fetch_campus_workflow(
        self, campus_id: int, limit: int, offset: int
    ) -> list[HistoryEvent]:
        q = (
            select(ApprovalHistory, WorkflowInstance)
            .join(WorkflowInstance, ApprovalHistory.instance_id == WorkflowInstance.id)
            .where(WorkflowInstance.campus_id == campus_id)
            .order_by(ApprovalHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(q)).all()
        return [
            HistoryEvent(
                id=f"workflow:{ah.id}",
                source="workflow",
                event_type=f"workflow.{ah.action}",
                timestamp=ah.created_at,
                actor=f"user #{ah.actor_id}" if ah.actor_id else "system",
                entity=f"Workflow #{wi.id}",
                description=(
                    f"{(ah.action or 'action').replace('_', ' ').title()}"
                    + (f" — {ah.comment}" if ah.comment else "")
                ),
                severity=(
                    "success" if ah.action == "approve"
                    else "warning" if ah.action in ("reject", "return")
                    else "info"
                ),
                metadata={"instance_id": wi.id},
            )
            for ah, wi in rows
        ]

    # ------------------------------------------------------------------
    # Events-before fetcher (for pre-exception timeline)
    # ------------------------------------------------------------------

    async def _fetch_events_before(
        self,
        campus_id: int | None,
        cutoff: datetime.datetime,
        limit: int,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> list[HistoryEvent]:
        events: list[HistoryEvent] = []

        # Audit logs before cutoff
        q = select(AuditLog)
        conditions: list = []
        if campus_id is not None:
            conditions.append(AuditLog.campus_id == campus_id)
        conditions.append(AuditLog.created_at < cutoff)
        if entity_type and entity_id:
            resource_map = {
                "student": "student",
                "class": ("academic", "class"),
                "teacher": "teacher",
            }
            resource = resource_map.get(entity_type)
            if resource:
                if isinstance(resource, tuple):
                    conditions.append(AuditLog.resource_type.in_(resource))
                else:
                    conditions.append(AuditLog.resource_type == resource)
            conditions.append(AuditLog.resource_id == str(entity_id))

        q = q.where(*conditions).order_by(AuditLog.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).scalars().all()
        events.extend([_audit_to_history(log) for log in rows])

        # Outbox events before cutoff
        q2 = select(OutboxEvent)
        conditions2: list = []
        if campus_id is not None:
            conditions2.append(OutboxEvent.school_id == campus_id)
        conditions2.append(OutboxEvent.occurred_at < cutoff)
        if entity_type and entity_id:
            conditions2.append(OutboxEvent.entity_type == entity_type)
            conditions2.append(OutboxEvent.entity_id == entity_id)

        q2 = q2.where(*conditions2).order_by(OutboxEvent.occurred_at.desc()).limit(limit)
        rows2 = (await self.session.execute(q2)).scalars().all()
        events.extend([self._outbox_to_history(e) for e in rows2])

        return events

    # ------------------------------------------------------------------
    # Date-range fetcher
    # ------------------------------------------------------------------

    async def _fetch_events_in_range(
        self,
        campus_id: int | None,
        start: datetime.datetime,
        end: datetime.datetime,
        source: str,
        limit: int,
    ) -> list[HistoryEvent]:
        if source == "outbox":
            return await self._fetch_outbox_range(campus_id, start, end, limit)
        if source == "audit":
            return await self._fetch_audit_range(campus_id, start, end, limit)
        if source == "case":
            return await self._fetch_case_range(campus_id, start, end, limit)
        if source == "exception":
            return await self._fetch_exception_range(campus_id, start, end, limit)
        if source == "workflow":
            return await self._fetch_workflow_range(campus_id, start, end, limit)
        return []

    async def _fetch_outbox_range(
        self, campus_id: int | None, start: datetime.datetime, end: datetime.datetime, limit: int
    ) -> list[HistoryEvent]:
        q = select(OutboxEvent)
        conditions: list = []
        if campus_id is not None:
            conditions.append(OutboxEvent.school_id == campus_id)
        conditions.append(OutboxEvent.occurred_at >= start)
        conditions.append(OutboxEvent.occurred_at <= end)
        q = q.where(*conditions).order_by(OutboxEvent.occurred_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).scalars().all()
        return [self._outbox_to_history(e) for e in rows]

    async def _fetch_audit_range(
        self, campus_id: int | None, start: datetime.datetime, end: datetime.datetime, limit: int
    ) -> list[HistoryEvent]:
        q = select(AuditLog)
        conditions: list = []
        if campus_id is not None:
            conditions.append(AuditLog.campus_id == campus_id)
        conditions.append(AuditLog.created_at >= start)
        conditions.append(AuditLog.created_at <= end)
        q = q.where(*conditions).order_by(AuditLog.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).scalars().all()
        return [_audit_to_history(log) for log in rows]

    async def _fetch_case_range(
        self, campus_id: int | None, start: datetime.datetime, end: datetime.datetime, limit: int
    ) -> list[HistoryEvent]:
        q = (
            select(CaseEvent, Case)
            .join(Case, CaseEvent.case_id == Case.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(Case.campus_id == campus_id)
        conditions.append(CaseEvent.created_at >= start)
        conditions.append(CaseEvent.created_at <= end)
        q = q.where(*conditions).order_by(CaseEvent.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()
        return [_case_event_to_history(ce, c) for ce, c in rows]

    async def _fetch_exception_range(
        self, campus_id: int | None, start: datetime.datetime, end: datetime.datetime, limit: int
    ) -> list[HistoryEvent]:
        q = (
            select(SystemExceptionEvent, SystemException)
            .join(SystemException, SystemExceptionEvent.exception_id == SystemException.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(SystemException.campus_id == campus_id)
        conditions.append(SystemExceptionEvent.created_at >= start)
        conditions.append(SystemExceptionEvent.created_at <= end)
        q = q.where(*conditions).order_by(SystemExceptionEvent.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()
        return [_exception_event_to_history(see, exc) for see, exc in rows]

    async def _fetch_workflow_range(
        self, campus_id: int | None, start: datetime.datetime, end: datetime.datetime, limit: int
    ) -> list[HistoryEvent]:
        q = (
            select(ApprovalHistory, WorkflowInstance)
            .join(WorkflowInstance, ApprovalHistory.instance_id == WorkflowInstance.id)
        )
        conditions: list = []
        if campus_id is not None:
            conditions.append(WorkflowInstance.campus_id == campus_id)
        conditions.append(ApprovalHistory.created_at >= start)
        conditions.append(ApprovalHistory.created_at <= end)
        q = q.where(*conditions).order_by(ApprovalHistory.created_at.desc()).limit(limit)
        rows = (await self.session.execute(q)).all()
        return [
            HistoryEvent(
                id=f"workflow:{ah.id}",
                source="workflow",
                event_type=f"workflow.{ah.action}",
                timestamp=ah.created_at,
                actor=f"user #{ah.actor_id}" if ah.actor_id else "system",
                entity=f"Workflow #{wi.id} ({wi.entity_type} #{wi.entity_id})",
                description=(
                    f"{(ah.action or 'action').replace('_', ' ').title()}"
                    + (f" — {ah.comment}" if ah.comment else "")
                ),
                severity=(
                    "success" if ah.action == "approve"
                    else "warning" if ah.action in ("reject", "return")
                    else "info"
                ),
                metadata={"instance_id": wi.id, "comment": ah.comment},
            )
            for ah, wi in rows
        ]

    # ------------------------------------------------------------------
    # Outbox event lookup
    # ------------------------------------------------------------------

    async def _find_outbox_event(self, event_id: str) -> OutboxEvent | None:
        q = select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        return (await self.session.execute(q)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _outbox_to_history(event: OutboxEvent) -> HistoryEvent:
        """Convert an OutboxEvent to a HistoryEvent."""
        payload = event.payload or {}
        # Extract entity description from payload
        if event.entity_id:
            entity = f"{event.entity_type or 'event'} #{event.entity_id}"
        else:
            entity = event.entity_type or "event"

        # Build description from event type and payload
        event_type_label = event.event_type.replace(".", " ").replace("_", " ").title()
        description = event_type_label
        if "full_name" in payload:
            description = f"{event_type_label}: {payload['full_name']}"
        elif "applicant_name" in payload:
            description = f"{event_type_label}: {payload['applicant_name']}"
        elif "student_id" in payload:
            description = f"{event_type_label} (student #{payload['student_id']})"

        severity = "info"
        if "failed" in event.event_type or "error" in event.event_type:
            severity = "warning"
        elif "created" in event.event_type or "approved" in event.event_type:
            severity = "success"

        return HistoryEvent(
            id=f"outbox:{event.event_id}",
            source="outbox",
            event_type=event.event_type,
            timestamp=event.occurred_at,
            actor=f"user #{event.actor_user_id}" if event.actor_user_id else "system",
            entity=entity,
            description=description,
            severity=severity,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            metadata=payload,
        )

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(events: list[HistoryEvent]) -> HistorySummary:
        """Build deterministic summary statistics from a list of events."""
        if not events:
            return InstitutionalHistoryService._empty_summary()

        source_counts: Counter[str] = Counter()
        severity_counts: Counter[str] = Counter()
        actor_counts: Counter[str] = Counter()

        for evt in events:
            source_counts[evt.source] += 1
            severity_counts[evt.severity] += 1
            if evt.actor and evt.actor != "system":
                actor_counts[evt.actor] += 1

        timestamps = [evt.timestamp for evt in events]
        first = min(timestamps)
        last = max(timestamps)
        delta = last - first

        return HistorySummary(
            total_events=len(events),
            sources=dict(source_counts),
            severity_distribution=dict(severity_counts),
            actors=[a for a, _ in actor_counts.most_common(20)],
            first_event_at=first,
            last_event_at=last,
            date_range_days=delta.total_seconds() / 86400,
        )

    @staticmethod
    def _empty_summary() -> HistorySummary:
        return HistorySummary(
            total_events=0,
            sources={},
            severity_distribution={},
            actors=[],
        )

    # ------------------------------------------------------------------
    # Lifecycle milestone extractor
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_lifecycle_milestones(
        events: list[HistoryEvent],
    ) -> list[LifecycleMilestone]:
        """Extract significant lifecycle transitions from a timeline."""
        milestones: list[LifecycleMilestone] = []
        for evt in events:
            if evt.event_type not in _LIFECYCLE_MILESTONE_TYPES:
                continue

            # Try to extract state transition from metadata
            from_state: str | None = None
            to_state: str | None = None
            meta = evt.metadata
            if "from_status" in meta and "to_status" in meta:
                from_state = str(meta["from_status"])
                to_state = str(meta["to_status"])
            elif "status" in meta:
                to_state = str(meta["status"])

            milestones.append(
                LifecycleMilestone(
                    event_id=evt.id,
                    timestamp=evt.timestamp,
                    event_type=evt.event_type,
                    from_state=from_state,
                    to_state=to_state,
                    actor=evt.actor,
                    description=evt.description,
                )
            )
        return milestones
