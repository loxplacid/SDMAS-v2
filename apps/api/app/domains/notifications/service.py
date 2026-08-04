from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import Notification
from app.domains.notifications.repository import NotificationRepository
from app.multi_tenant.models import TenantContext


class NotificationService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = NotificationRepository(session, tenant)

    async def create_notification(
        self,
        user_id: int,
        type: str,
        title: str,
        message: str,
        data: Optional[dict] = None,
    ) -> Notification:
        import datetime
        from datetime import timezone

        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=data,
            read_at=None,
            created_at=datetime.datetime.now(timezone.utc),
        )
        return await self.repo.create(notification)

    async def get_user_notifications(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        return await self.repo.find_by_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            unread_only=unread_only,
        )

    async def get_unread_count(self, user_id: int) -> int:
        return await self.repo.count_unread(user_id)

    async def mark_as_read(self, notification_id: int) -> Notification:
        return await self.repo.mark_read(notification_id)

    async def mark_all_as_read(self, user_id: int) -> int:
        return await self.repo.mark_all_read(user_id)

    async def delete_notification(self, notification_id: int) -> None:
        await self.repo.delete_by_id(notification_id)
