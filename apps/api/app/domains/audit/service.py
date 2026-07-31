from __future__ import annotations

import json
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.domains.audit.repository import AuditLogRepository

logger = logging.getLogger(__name__)


class AuditService:
    """Records and queries immutable audit log entries.

    The service is intentionally thin -- most complexity lives in the
    middleware layer that calls ``record`` automatically.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AuditLogRepository(session)

    async def record(
        self,
        *,
        user_id: int | None = None,
        username: str | None = None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        campus_id: int | None = None,
    ) -> AuditLog:
        """Record a single audit log entry.

        Args:
            user_id: ID of the user who performed the action.
            username: Denormalized username for stability.
            action: ``CREATE``, ``UPDATE``, ``DELETE``, or custom.
            resource_type: Domain entity name (e.g. ``student``).
            resource_id: Primary key of the affected resource.
            details: Optional JSON-serializable dict with before/after.
            ip_address: Client IP address.
            user_agent: Client User-Agent header.
            campus_id: Tenant context.

        Returns:
            The persisted ``AuditLog`` entry.
        """
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action.upper(),
            resource_type=resource_type.lower(),
            resource_id=str(resource_id) if resource_id is not None else None,
            details=json.dumps(details) if details is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
            campus_id=campus_id,
        )
        created = await self.repo.create(entry)
        logger.debug(
            "Audit: %s %s[%s] by user %s",
            action, resource_type, resource_id, username,
        )
        return created

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
            skip=skip,
            limit=limit,
        )
