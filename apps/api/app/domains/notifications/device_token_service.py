from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import DeviceToken
from app.domains.notifications.repository import DeviceTokenRepository


class DeviceTokenService:
    """Manage push notification device tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DeviceTokenRepository(session)

    async def register_token(
        self,
        user_id: int,
        token: str,
        platform: str,
    ) -> DeviceToken:
        """Register or update a device token for a user.

        If the token already exists for that user, update the platform.
        If the same token is registered for a *different* user (e.g., after
        logout/login on a shared device), reassign it.
        """
        existing = await self.repo.find_by_token(token)

        if existing:
            if existing.user_id == user_id:
                # Same user — update platform if changed
                if existing.platform != platform:
                    existing.platform = platform
                    await self.session.flush()
                return existing
            else:
                # Different user — reassign
                existing.user_id = user_id
                existing.platform = platform
                await self.session.flush()
                return existing

        # New token
        device_token = DeviceToken(
            user_id=user_id,
            token=token,
            platform=platform,
        )
        return await self.repo.create(device_token)

    async def unregister_token(self, token: str) -> None:
        """Remove a device token."""
        existing = await self.repo.find_by_token(token)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()

    async def unregister_all_for_user(self, user_id: int) -> None:
        """Remove all device tokens for a user (e.g., on logout)."""
        tokens = await self.repo.find_by_user(user_id)
        for token in tokens:
            await self.session.delete(token)
        await self.session.flush()

    async def get_tokens_for_user(self, user_id: int) -> list[str]:
        """Get all Expo push tokens for a specific user."""
        tokens = await self.repo.find_by_user(user_id)
        return [t.token for t in tokens if t.token]


