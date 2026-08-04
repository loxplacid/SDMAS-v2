from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.constants import STUDENT, UPDATE
from app.domains.audit.service import AuditService
from app.domains.audit.utils import safe_details
from app.domains.events import publish_event
from app.domains.events.context import get_actor_user_id
from app.domains.events.events import StudentStatusChangedEvent
from app.domains.student.models import (
    ALLOWED_LIFECYCLE_TRANSITIONS,
    Student,
    StudentLifecycleEvent,
)
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import (
    LifecycleEventOut,
    LifecycleStateOut,
)
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


class StudentLifecycleService:
    """Deterministic, auditable student lifecycle state machine.

    Every transition is validated against ``ALLOWED_LIFECYCLE_TRANSITIONS``
    and persisted as an immutable ``StudentLifecycleEvent`` row *before*
    ``Student.status`` is updated.  No predictive/AI logic — purely
    rule-based with a full, tenant-scoped audit trail.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.student_repo = StudentRepository(session, tenant)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_state(self, student_id: int) -> LifecycleStateOut:
        """Current status + allowed transitions + recent history."""
        student = await self.student_repo.get_by_id(student_id)
        events, _ = await self._query_events(student_id, skip=0, limit=5)
        return LifecycleStateOut(
            student_id=student.id,
            current_status=student.status,
            allowed_transitions=sorted(
                ALLOWED_LIFECYCLE_TRANSITIONS.get(student.status, set())
            ),
            recent_events=list(events),
        )

    async def list_events(
        self,
        student_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[LifecycleEventOut], int]:
        """Paginated lifecycle history for a student (newest first)."""
        await self.student_repo.get_by_id(student_id)  # 404 if unknown
        events, total = await self._query_events(student_id, skip, limit)
        return events, total

    async def _query_events(
        self,
        student_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[LifecycleEventOut], int]:
        """Shared event query (used by both list_events and get_state).

        Queries run through the tenant-scoped repository so lifecycle
        history can never escape the tenant boundary, even when called
        directly (not just via a tenant-guarded router).
        """
        stmt = (
            self.student_repo.scoped_query(StudentLifecycleEvent)
            .where(StudentLifecycleEvent.student_id == student_id)
            # Deterministic order: newest first; id tie-breaks transitions
            # recorded within the same microsecond (SQLite timestamp ties).
            .order_by(
                StudentLifecycleEvent.created_at.desc(),
                StudentLifecycleEvent.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        count_stmt = self.student_repo.scoped_count(StudentLifecycleEvent).where(
            StudentLifecycleEvent.student_id == student_id
        )
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        rows = result.scalars().all()
        total = count_result.scalar() or 0
        return [LifecycleEventOut.model_validate(r) for r in rows], total

    # ------------------------------------------------------------------
    # Transition
    # ------------------------------------------------------------------

    async def transition(
        self,
        student_id: int,
        to_status: str,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        actor_username: Optional[str] = None,
    ) -> LifecycleStateOut:
        """Validate + apply a lifecycle transition with full audit trail."""
        student = await self.student_repo.get_by_id(student_id)
        from_status = student.status

        if to_status == from_status:
            raise ConflictError(
                f"Student {student_id} is already in status '{from_status}'"
            )

        allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise ValidationError(
                f"Invalid transition '{from_status}' -> '{to_status}'. "
                f"Allowed: {sorted(allowed) or 'none (terminal status)'}"
            )

        # Atomic optimistic guard: only apply the transition if the row is
        # still in the status we validated against.  Concurrent transitions
        # from the same status (double-click, two staff members) cannot both
        # succeed — the second one sees rowcount 0 and fails loudly.
        result = await self.session.execute(
            update(Student)
            .where(Student.id == student_id, Student.status == from_status)
            .values(status=to_status)
            # Sync the identity map via the explicit assignment below instead
            # of letting SQLAlchemy evaluate-sync (keeps the guarded write the
            # authoritative one; the flush below is idempotent).
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise ConflictError(
                f"Student {student_id} status changed concurrently — expected "
                f"'{from_status}', retry the transition"
            )

        # Record the immutable lifecycle event *only after* the guard passes,
        # so a rejected (concurrent) transition never leaves an event behind.
        event = StudentLifecycleEvent(
            student_id=student_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor_id=(
                actor_user_id
                if actor_user_id is not None
                else get_actor_user_id()
            ),
            campus_id=student.campus_id,
        )
        self.session.add(event)
        # Keep the identity-mapped instance in sync with the database.
        student.status = to_status
        await self.session.flush()

        # Synchronous audit entry (source of truth) — best-effort.
        try:
            await AuditService(self.session).record(
                user_id=event.actor_id,
                username=actor_username,
                action=UPDATE,
                resource_type=STUDENT,
                resource_id=str(student_id),
                details=safe_details(
                    {
                        "lifecycle": {
                            "from": from_status,
                            "to": to_status,
                            "reason": reason,
                        }
                    }
                ),
            )
            await self.session.flush()
        except Exception:  # noqa: BLE001 — audit must not break the transition
            logger.warning("Failed to write lifecycle audit entry (non-fatal)", exc_info=True)

        # Domain event for subscribers (non-fatal).
        try:
            await publish_event(
                StudentStatusChangedEvent(
                    student_id=student_id,
                    from_status=from_status,
                    to_status=to_status,
                ),
                session=self.session,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Failed to publish StudentStatusChangedEvent (non-fatal)", exc_info=True)

        return await self.get_state(student_id)
