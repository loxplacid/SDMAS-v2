from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.notifications.models import Notification, DeviceToken


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, notification_id: int) -> Notification:
        result = await self.session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise NotFoundError(
                f"Notification with id {notification_id} not found"
            )
        return notification

    async def create(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def find_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))

        query = (
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(Notification.id)).where(*conditions)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        return items, total

    async def count_unread(self, user_id: int) -> int:
        query = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def mark_read(self, notification_id: int) -> Notification:
        notification = await self.get_by_id(notification_id)
        notification.read_at = datetime.datetime.now(timezone.utc)
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def mark_all_read(self, user_id: int) -> int:
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        # Only SQLite returns rowcount for async; PostgreSQL via asyncpg does not.
        # This value is best-effort for tests and not relied on in production.
        return result.rowcount  # type: ignore[attr-defined]

    async def delete_by_id(self, notification_id: int) -> None:
        notification = await self.get_by_id(notification_id)
        await self.session.delete(notification)
        await self.session.flush()


class DeviceTokenRepository:
    """Repository for managing push notification device tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, device_token: DeviceToken) -> DeviceToken:
        self.session.add(device_token)
        await self.session.flush()
        return device_token

    async def find_by_token(self, token: str) -> DeviceToken | None:
        result = await self.session.execute(
            select(DeviceToken).where(DeviceToken.token == token)
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: int) -> list[DeviceToken]:
        result = await self.session.execute(
            select(DeviceToken)
            .where(DeviceToken.user_id == user_id)
            .order_by(DeviceToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_by_user(self, user_id: int) -> None:
        await self.session.execute(
            DeviceToken.__table__.delete().where(
                DeviceToken.user_id == user_id
            )
        )
        await self.session.flush()
