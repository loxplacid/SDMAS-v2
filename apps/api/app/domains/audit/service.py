from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.actors import (
    ActorType,
    AuditActor,
    UNKNOWN,
)
from app.domains.audit.models import AuditLog
from app.domains.audit.repository import AuditLogRepository
from app.domains.audit.utils import safe_details
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)

#: Outcome values for the ``result`` field.
RESULT_SUCCESS = "SUCCESS"
RESULT_FAILURE = "FAILURE"
RESULT_SKIPPED = "SKIPPED"


class AuditService:
    """Records and queries immutable audit log entries.

    The service enforces the canonical audit-event contract:

    * every entry carries an explicit, typed actor (never ``0``)
    * sensitive fields (passwords, tokens) are stripped before storage
    * semantically meaningful actions are used (CREATE, VERIFY, …)
    * transactional by default: the entry shares the caller's session
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = AuditLogRepository(session, tenant)

    async def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        actor: AuditActor | None = None,
        user_id: int | None = None,
        username: str | None = None,
        details: dict[str, Any] | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        result: str | None = None,
        failure_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        campus_id: int | None = None,
        tenant_id: int | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        event_id: str | None = None,
        commit: bool = False,
    ) -> AuditLog:
        """Record a single audit log entry.

        Actor resolution precedence:

        1. ``actor`` — explicit :class:`AuditActor` (preferred).
        2. ``user_id``/``username`` — legacy user actor (mapped to
           ``ActorType.USER``).
        3. No actor — the entry is recorded as an explicit
           ``ActorType.SYSTEM`` actor labelled ``"unattributed"``.  An
           unattributed *human-looking* action is never fabricated; the
           caller must supply a real actor for human actions.

        Args:
            action: Semantic action (see ``audit.constants``).
            resource_type: Domain entity name (e.g. ``student``).
            resource_id: Primary key of the affected resource.
            actor: Explicit typed actor (see ``audit.actors``).
            user_id/username: Legacy actor fields (mapped to a USER actor).
            details: JSON-serializable dict with event specifics.
            before_state/after_state: Structured JSON state snapshots.
            result: SUCCESS / FAILURE / SKIPPED.
            failure_reason: Human-readable failure detail (no secrets).
            metadata: Free-form JSON metadata (no secrets).
            ip_address/user_agent: Network origin.
            campus_id/tenant_id: Tenant scope.
            request_id/correlation_id: End-to-end trace ids.
            event_id: Stable event id (auto-generated when omitted).
            commit: When True, commit the session after insert.

        Returns:
            The persisted ``AuditLog`` entry.
        """
        # Resolve the explicit actor.
        actor_type, actor_id = self._resolve_actor(actor, user_id, username)

        # Never store raw secrets in any payload column.
        details = safe_details(details)
        metadata = safe_details(metadata)
        before_state = safe_details(before_state)
        after_state = safe_details(after_state)

        # Merge trace context when available.
        if correlation_id is None:
            correlation_id = _current_correlation_id()
        if request_id is None:
            request_id = correlation_id

        entry = AuditLog(
            event_id=event_id or uuid.uuid4().hex,
            user_id=user_id,
            username=username,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action.upper(),
            resource_type=resource_type.lower(),
            resource_id=str(resource_id) if resource_id is not None else None,
            before_state=json.dumps(before_state) if before_state else None,
            after_state=json.dumps(after_state) if after_state else None,
            result=result or RESULT_SUCCESS,
            failure_reason=failure_reason,
            details=json.dumps(details) if details is not None else None,
            metadata_json=json.dumps(metadata) if metadata else None,
            ip_address=ip_address,
            user_agent=user_agent,
            campus_id=campus_id if campus_id is not None else (
                self.tenant.campus_id if self.tenant else None
            ),
            tenant_id=tenant_id if tenant_id is not None else (
                self.tenant.institution_id if self.tenant else None
            ),
            request_id=request_id,
            correlation_id=correlation_id,
        )
        created = await self.repo.create(entry)
        # Tamper-evident chain (TASK 13): append the chain entry covering
        # this event.  Deliberately **non-fatal** — the audit event itself
        # must never be lost because chaining failed; failures are logged
        # and the verifier reports such rows as uncovered.
        try:
            from app.platform.cryptography.service import AuditChainService

            chain = AuditChainService(self.session, self.tenant)
            await chain.append_for_audit(created)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "audit chain append failed for audit_log_id=%s (non-fatal)",
                created.id,
            )
        if commit:
            await self.session.commit()
        logger.debug(
            "Audit: %s %s[%s] by %s:%s",
            entry.action, resource_type, resource_id,
            actor_type, actor_id or username,
        )
        return created

    @staticmethod
    def _resolve_actor(
        actor: AuditActor | None,
        user_id: int | None,
        username: str | None,
    ) -> tuple[str, str | None]:
        """Map the caller-supplied actor to ``(actor_type, actor_id)``.

        An explicit actor wins.  Legacy ``user_id`` implies a USER actor.
        When neither is provided the actor is the explicit SYSTEM actor
        with label ``"unattributed"`` — a deliberate, truthful marker
        rather than a synthetic ``0`` user id.
        """
        if actor is not None:
            return actor.actor_type.value, actor.actor_id
        if user_id is not None:
            return ActorType.USER.value, str(user_id)
        if username is not None:
            return ActorType.USER.value, username
        return ActorType.SYSTEM.value, UNKNOWN

    async def get_entry(self, entry_id: int) -> AuditLog:
        """Retrieve a single audit entry by ID."""
        return await self.repo.get_by_id(entry_id)

    async def list_entries(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        campus_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        result: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AuditLog], int]:
        """Query audit log entries with optional filters.

        Returns:
            ``(entries, total_count)`` tuple ordered by most recent first.
        """
        return await self.repo.list(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            campus_id=campus_id,
            start_date=start_date,
            end_date=end_date,
            actor_type=actor_type,
            actor_id=actor_id,
            result=result,
            skip=skip,
            limit=limit,
        )


def _current_correlation_id() -> str | None:
    """Read the request-scoped correlation id if set."""
    try:
        from app.domains.events.context import get_correlation_id

        return get_correlation_id()
    except Exception:
        return None
