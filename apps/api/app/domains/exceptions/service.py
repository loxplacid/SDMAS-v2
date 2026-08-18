"""Universal Exception Management — application service.

Provides the full exception lifecycle:

- ``create`` — create an exception from any source (data quality, risk,
  finance, migration, manual).  Deduplicated by the
  ``(campus_id, source_domain, source_type, source_id)`` unique constraint.
- ``acknowledge`` / ``start`` / ``resolve`` / ``close`` / ``reopen`` —
  controlled status transitions, each recorded as an immutable event.
- ``assign`` / ``update_severity`` / ``set_due_date`` / ``set_root_cause`` —
  targeted mutations with optimistic concurrency.
- ``add_evidence`` — attach deterministic evidence snapshots.
- ``link_case`` / ``link_workflow`` — connect to human-action or structured
  workflow systems.
- ``list`` / ``get`` / ``metrics`` — tenant-scoped reads.

Every mutation writes an immutable :class:`SystemExceptionEvent` and an
audit log entry (via the audit domain service when available).
"""

from __future__ import annotations

import datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.service import AuditService
from app.domains.exceptions.models import (
    EXCEPTION_EVENT_ASSIGNED,
    EXCEPTION_EVENT_CASE_LINKED,
    EXCEPTION_EVENT_CREATED,
    EXCEPTION_EVENT_DUE_DATE_CHANGED,
    EXCEPTION_EVENT_EVIDENCE_ADDED,
    EXCEPTION_EVENT_REASSIGNED,
    EXCEPTION_EVENT_ROOT_CAUSE_SET,
    EXCEPTION_EVENT_SEVERITY_CHANGED,
    EXCEPTION_EVENT_WORKFLOW_LINKED,
    EXCEPTION_SEVERITIES,
    EXCEPTION_STATUS_ACKNOWLEDGED,
    EXCEPTION_STATUS_CLOSED,
    EXCEPTION_STATUS_IN_PROGRESS,
    EXCEPTION_STATUS_OPEN,
    EXCEPTION_STATUS_RESOLVED,
    EXCEPTION_TRANSITIONS,
    EXCEPTION_TYPES,
    ExceptionSLAConfig,
    SystemException,
    SystemExceptionEvent,
)
from app.domains.exceptions.repository import ExceptionRepository
from app.multi_tenant.models import TenantContext

#: Default SLA deadlines by severity (hours) — used when no campus-specific
#: ``ExceptionSLAConfig`` row exists.  Keep in sync with the config table.
DEFAULT_SLA_HOURS: dict[str, int] = {
    "critical": 24,
    "high": 48,
    "medium": 120,
    "low": 240,
    "info": 240,
}

#: Allowed resolution types.
RESOLUTION_TYPES = frozenset({"fixed", "accepted_risk", "false_positive", "duplicate", "no_action"})


class ExceptionService:
    """Service layer for the universal exception lifecycle."""

    def __init__(self, session: AsyncSession, tenant: TenantContext):
        self.session = session
        self.tenant = tenant
        self.repo = ExceptionRepository(session, tenant)
        self.audit = AuditService(session, tenant)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _actor(self, actor_id: int | None = None, actor_name: str | None = None) -> dict:
        """Build an actor descriptor for audit + events."""
        if actor_id is not None:
            return {"id": actor_id, "name": actor_name or f"user-{actor_id}"}
        return {"id": None, "name": actor_name or "system"}

    async def _append_event(
        self,
        exception: SystemException,
        event_type: str,
        message: str,
        actor_id: int | None,
        actor_name: str | None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record an immutable event on the exception timeline."""
        event_seq = await self.repo.get_next_event_seq(exception.id)
        event = SystemExceptionEvent(
            exception_id=exception.id,
            event_seq=event_seq,
            event_type=event_type,
            actor_id=actor_id,
            actor_name=actor_name,
            message=message,
            data=data,
        )
        await self.repo.create_event(event)
        # The event is flushed to the DB.  Callers reading the timeline
        # through ``get()``/``get_by_id`` (which refresh with
        # ``populate_existing``) will see it; we deliberately do NOT mutate
        # the in-memory collection here — on a freshly created object the
        # relationship is unloaded and touching it would trigger an async
        # lazy-load (MissingGreenlet).

    async def _audit(
        self,
        action: str,
        resource_id: str,
        actor_id: int | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an audit log entry (best-effort, never raises)."""
        try:
            await self.audit.record(
                action=action,
                resource_type="system_exception",
                resource_id=resource_id,
                user_id=actor_id,
                username=actor_id and f"user-{actor_id}" or None,
                details=details,
            )
        except Exception:  # pragma: no cover — audit is best-effort
            pass

    async def _resolve_sla_hours(self, exception_type: str, severity: str) -> int | None:
        """Resolve SLA hours: campus row > global default > built-in default."""
        stmt = (
            select(ExceptionSLAConfig)
            .where(
                ExceptionSLAConfig.exception_type == exception_type,
                ExceptionSLAConfig.severity == severity,
                ExceptionSLAConfig.enabled.is_(True),
            )
            .order_by(ExceptionSLAConfig.campus_id.is_(None))  # campus rows first
        )
        result = await self.session.execute(stmt)
        config = result.scalars().first()
        if config is not None and config.after_hours is not None:
            return int(config.after_hours)
        return DEFAULT_SLA_HOURS.get(severity)

    async def _compute_due_at(self, exception_type: str, severity: str) -> datetime.datetime | None:
        """Compute the due date from SLA hours, or None if no SLA applies."""
        hours = await self._resolve_sla_hours(exception_type, severity)
        if hours is None:
            return None
        return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        exception_type: str,
        severity: str,
        title: str,
        source_domain: str,
        source_type: str,
        description: str | None = None,
        source_id: int | None = None,
        rule_code: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        student_id: int | None = None,
        evidence: dict[str, Any] | None = None,
        owner_id: int | None = None,
        actor_id: int | None = None,
        actor_name: str | None = None,
        priority: str | None = None,
        due_at: datetime.datetime | None = None,
        campus_id: int | None = None,
    ) -> SystemException:
        """Create a new system exception.

        The ``(campus_id, source_domain, source_type, source_id)`` tuple must
        be unique — re-creating an exception for the same source record
        raises :class:`ConflictError` (callers should first check
        ``get_by_source`` or catch the conflict for idempotency).
        """
        # Validate
        if exception_type not in EXCEPTION_TYPES:
            raise ValidationError(f"Invalid exception_type: {exception_type!r}")
        if severity not in EXCEPTION_SEVERITIES:
            raise ValidationError(f"Invalid severity: {severity!r}")
        if not title or not title.strip():
            raise ValidationError("title is required")

        # Campus resolution: explicit campus_id wins, else tenant context.
        resolved_campus = campus_id if campus_id is not None else self.tenant.campus_id

        # Deduplication check (defense in depth; the DB unique constraint is
        # the backstop).
        if source_domain and source_type and source_id is not None:
            existing = await self.repo.get_by_source(source_domain, source_type, source_id)
            if existing is not None:
                raise ConflictError(
                    f"Exception already exists for source {source_domain}/{source_type}/{source_id}"
                )

        # SLA
        if due_at is None:
            due_at = await self._compute_due_at(exception_type, severity)

        exception = SystemException(
            campus_id=resolved_campus,
            exception_type=exception_type,
            severity=severity,
            title=title,
            description=description,
            source_domain=source_domain,
            source_type=source_type,
            source_id=source_id,
            rule_code=rule_code,
            entity_type=entity_type,
            entity_id=entity_id,
            student_id=student_id,
            evidence=evidence,
            owner_id=owner_id,
            priority=priority or _severity_to_priority(severity),
            due_at=due_at,
            status=EXCEPTION_STATUS_OPEN,
            created_by=actor_id,
        )
        exception = await self.repo.create(exception)
        await self.session.flush()

        # Re-read with the events collection eager-loaded: callers (and the
        # router's response serialization) must never trigger a lazy-load on
        # an async session.
        exception = await self.repo.get_by_id(exception.id)
        assert exception is not None

        await self._append_event(
            exception,
            EXCEPTION_EVENT_CREATED,
            f"Exception created (type={exception_type}, severity={severity})",
            actor_id,
            actor_name,
            data={
                "exception_type": exception_type,
                "severity": severity,
                "source_domain": source_domain,
                "source_type": source_type,
                "source_id": source_id,
                "due_at": due_at.isoformat() if due_at else None,
            },
        )
        await self._audit(
            "CREATE",
            str(exception.id),
            actor_id,
            {"exception_type": exception_type, "severity": severity},
        )
        return exception

    async def get_by_source(
        self, source_domain: str, source_type: str, source_id: int
    ) -> SystemException | None:
        """Find an exception by its source triple (idempotency helper)."""
        return await self.repo.get_by_source(source_domain, source_type, source_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, exception_id: int) -> SystemException:
        """Fetch a single exception (tenant-scoped), or raise NotFoundError."""
        exception = await self.repo.get_by_id(exception_id)
        if exception is None:
            raise NotFoundError(f"SystemException {exception_id} not found")
        return exception

    async def list(
        self,
        *,
        exception_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        student_id: int | None = None,
        owner_id: int | None = None,
        case_id: int | None = None,
        source_domain: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[SystemException], int]:
        """List exceptions with filtering and pagination."""
        return await self.repo.list_exceptions(
            exception_type=exception_type,
            severity=severity,
            status=status,
            entity_type=entity_type,
            entity_id=entity_id,
            student_id=student_id,
            owner_id=owner_id,
            case_id=case_id,
            source_domain=source_domain,
            offset=offset,
            limit=limit,
        )

    async def metrics(self) -> dict[str, Any]:
        """Return dashboard metrics for the tenant."""
        return {
            "by_status": await self.repo.count_by_status(),
            "open_by_severity": await self.repo.count_by_severity(),
            "overdue": await self.repo.count_overdue(),
        }

    async def list_for_student(
        self, student_id: int, *, include_resolved: bool = False
    ) -> Sequence[SystemException]:
        """List exceptions for a student (Student 360)."""
        return await self.repo.list_open_for_student(student_id, include_resolved=include_resolved)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    async def _transition(
        self,
        exception: SystemException,
        new_status: str,
        actor_id: int | None,
        actor_name: str | None,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> SystemException:
        """Apply a whitelisted status transition with event + audit."""
        allowed = EXCEPTION_TRANSITIONS.get(exception.status, set())
        if new_status not in allowed:
            raise ConflictError(
                f"Illegal transition {exception.status} -> {new_status} "
                f"(allowed: {sorted(allowed)})"
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        updates: dict[str, Any] = {"status": new_status}
        if new_status == EXCEPTION_STATUS_ACKNOWLEDGED:
            updates["acknowledged_at"] = now
            updates["acknowledged_by"] = actor_id
        elif new_status == EXCEPTION_STATUS_IN_PROGRESS:
            updates["in_progress_at"] = now
        elif new_status == EXCEPTION_STATUS_RESOLVED:
            updates["resolved_at"] = now
            updates["resolved_by"] = actor_id
        elif new_status == EXCEPTION_STATUS_CLOSED:
            updates["closed_at"] = now
            updates["closed_by"] = actor_id
        elif new_status == EXCEPTION_STATUS_OPEN:
            # Reopen — clear resolution fields.
            updates["resolved_at"] = None
            updates["resolved_by"] = None
            updates["closed_at"] = None
            updates["closed_by"] = None

        ok = await self.repo.update_fields(exception.id, version=exception.version, **updates)
        if not ok:
            raise ConflictError(f"Concurrent modification of SystemException {exception.id}; retry")
        exception.version += 1
        for key, value in updates.items():
            setattr(exception, key, value)

        await self._append_event(exception, new_status.upper(), message, actor_id, actor_name, data)
        await self._audit("UPDATE", str(exception.id), actor_id, {"status": new_status})
        return exception

    async def acknowledge(
        self, exception_id: int, actor_id: int | None = None, actor_name: str | None = None
    ) -> SystemException:
        exception = await self.get(exception_id)
        return await self._transition(
            exception,
            EXCEPTION_STATUS_ACKNOWLEDGED,
            actor_id,
            actor_name,
            "Exception acknowledged",
        )

    async def start(
        self, exception_id: int, actor_id: int | None = None, actor_name: str | None = None
    ) -> SystemException:
        exception = await self.get(exception_id)
        return await self._transition(
            exception,
            EXCEPTION_STATUS_IN_PROGRESS,
            actor_id,
            actor_name,
            "Work started on exception",
        )

    async def resolve(
        self,
        exception_id: int,
        *,
        resolution_type: str,
        resolution_note: str | None = None,
        root_cause: str | None = None,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        if resolution_type not in RESOLUTION_TYPES:
            raise ValidationError(
                f"Invalid resolution_type: {resolution_type!r} "
                f"(allowed: {sorted(RESOLUTION_TYPES)})"
            )
        exception = await self.get(exception_id)
        updates: dict[str, Any] = {
            "resolution_type": resolution_type,
            "resolution_note": resolution_note,
        }
        if root_cause:
            updates["root_cause"] = root_cause
        await self.repo.update_fields(exception.id, version=exception.version, **updates)
        exception.version += 1
        exception.resolution_type = resolution_type
        exception.resolution_note = resolution_note
        if root_cause:
            exception.root_cause = root_cause
        await self.session.flush()

        return await self._transition(
            exception,
            EXCEPTION_STATUS_RESOLVED,
            actor_id,
            actor_name,
            f"Exception resolved ({resolution_type})",
            {"resolution_type": resolution_type},
        )

    async def close(
        self, exception_id: int, actor_id: int | None = None, actor_name: str | None = None
    ) -> SystemException:
        exception = await self.get(exception_id)
        return await self._transition(
            exception,
            EXCEPTION_STATUS_CLOSED,
            actor_id,
            actor_name,
            "Exception closed",
        )

    async def reopen(
        self, exception_id: int, actor_id: int | None = None, actor_name: str | None = None
    ) -> SystemException:
        exception = await self.get(exception_id)
        return await self._transition(
            exception,
            EXCEPTION_STATUS_OPEN,
            actor_id,
            actor_name,
            "Exception reopened",
            {"previous_status": exception.status},
        )

    # ------------------------------------------------------------------
    # Targeted mutations
    # ------------------------------------------------------------------

    async def assign(
        self,
        exception_id: int,
        owner_id: int | None,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        exception = await self.get(exception_id)
        ok = await self.repo.update_fields(
            exception.id, version=exception.version, owner_id=owner_id
        )
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.owner_id = owner_id
        await self._append_event(
            exception,
            EXCEPTION_EVENT_ASSIGNED if owner_id else EXCEPTION_EVENT_REASSIGNED,
            f"Assigned to {owner_id}" if owner_id else "Unassigned",
            actor_id,
            actor_name,
            {"owner_id": owner_id},
        )
        await self._audit("UPDATE", str(exception.id), actor_id, {"owner_id": owner_id})
        return exception

    async def update_severity(
        self,
        exception_id: int,
        severity: str,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        if severity not in EXCEPTION_SEVERITIES:
            raise ValidationError(f"Invalid severity: {severity!r}")
        exception = await self.get(exception_id)
        old = exception.severity
        due_at = await self._compute_due_at(exception.exception_type, severity)
        ok = await self.repo.update_fields(
            exception.id,
            version=exception.version,
            severity=severity,
            due_at=due_at,
        )
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.severity = severity
        exception.due_at = due_at
        await self._append_event(
            exception,
            EXCEPTION_EVENT_SEVERITY_CHANGED,
            f"Severity changed {old} -> {severity}",
            actor_id,
            actor_name,
            {"from": old, "to": severity},
        )
        await self._audit("UPDATE", str(exception.id), actor_id, {"severity": severity})
        return exception

    async def set_due_date(
        self,
        exception_id: int,
        due_at: datetime.datetime | None,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        exception = await self.get(exception_id)
        ok = await self.repo.update_fields(exception.id, version=exception.version, due_at=due_at)
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.due_at = due_at
        await self._append_event(
            exception,
            EXCEPTION_EVENT_DUE_DATE_CHANGED,
            f"Due date set to {due_at.isoformat() if due_at else 'none'}",
            actor_id,
            actor_name,
            {"due_at": due_at.isoformat() if due_at else None},
        )
        return exception

    async def set_root_cause(
        self,
        exception_id: int,
        root_cause: str,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        exception = await self.get(exception_id)
        ok = await self.repo.update_fields(
            exception.id, version=exception.version, root_cause=root_cause
        )
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.root_cause = root_cause
        await self._append_event(
            exception,
            EXCEPTION_EVENT_ROOT_CAUSE_SET,
            "Root cause recorded",
            actor_id,
            actor_name,
        )
        return exception

    async def add_evidence(
        self,
        exception_id: int,
        evidence: dict[str, Any],
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        """Append evidence to the exception (merges into the evidence dict)."""
        exception = await self.get(exception_id)
        merged = dict(exception.evidence or {})
        merged.update(evidence)
        ok = await self.repo.update_fields(exception.id, version=exception.version, evidence=merged)
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.evidence = merged
        await self._append_event(
            exception,
            EXCEPTION_EVENT_EVIDENCE_ADDED,
            "Evidence added",
            actor_id,
            actor_name,
            {"keys": sorted(evidence.keys())},
        )
        return exception

    async def link_case(
        self,
        exception_id: int,
        case_id: int,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        exception = await self.get(exception_id)
        ok = await self.repo.update_fields(exception.id, version=exception.version, case_id=case_id)
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.case_id = case_id
        await self._append_event(
            exception,
            EXCEPTION_EVENT_CASE_LINKED,
            f"Linked to case {case_id}",
            actor_id,
            actor_name,
            {"case_id": case_id},
        )
        await self._audit("UPDATE", str(exception.id), actor_id, {"case_id": case_id})
        return exception

    async def link_workflow(
        self,
        exception_id: int,
        workflow_instance_id: int,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        exception = await self.get(exception_id)
        ok = await self.repo.update_fields(
            exception.id,
            version=exception.version,
            workflow_instance_id=workflow_instance_id,
        )
        if not ok:
            raise ConflictError(f"Concurrent modification of exception {exception.id}")
        exception.version += 1
        exception.workflow_instance_id = workflow_instance_id
        await self._append_event(
            exception,
            EXCEPTION_EVENT_WORKFLOW_LINKED,
            f"Linked to workflow instance {workflow_instance_id}",
            actor_id,
            actor_name,
            {"workflow_instance_id": workflow_instance_id},
        )
        return exception

    async def mark_verified(
        self,
        exception_id: int,
        actor_id: int | None = None,
        actor_name: str | None = None,
    ) -> SystemException:
        """Confirm the exception still exists (updates last_verified_at)."""
        exception = await self.get(exception_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.repo.update_fields(exception.id, version=exception.version, last_verified_at=now)
        exception.version += 1
        exception.last_verified_at = now
        return exception


def _severity_to_priority(severity: str) -> str:
    """Map a severity to the operational priority (same scale, sensible default)."""
    if severity in ("critical", "high"):
        return severity
    return "medium"
