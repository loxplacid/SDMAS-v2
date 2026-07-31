"""Notification preferences — per-user opt-in/out for event types and channels.

Each user can decide which event categories they want to receive, and
through which channels (in-app, email, SMS, push).
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base as DeclarativeBase

# ---------------------------------------------------------------------------
# Default channel constants
# ---------------------------------------------------------------------------

CHANNEL_IN_APP = "in_app"
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
CHANNEL_PUSH = "push"

ALL_CHANNELS = frozenset({CHANNEL_IN_APP, CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PUSH})
DEFAULT_CHANNELS = frozenset({CHANNEL_IN_APP})

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class NotificationPreference(DeclarativeBase):
    """Per-user notification preference for a specific event category."""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CHANNEL_IN_APP
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationPreference id={self.id} "
            f"user_id={self.user_id} "
            f"event_type={self.event_type} "
            f"channel={self.channel} "
            f"enabled={self.enabled}>"
        )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class NotificationPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_user(
        self, user_id: int
    ) -> Sequence[NotificationPreference]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(NotificationPreference)
            .where(NotificationPreference.user_id == user_id)
            .order_by(NotificationPreference.event_type)
        )
        return list(result.scalars().all())

    async def find_by_user_and_event(
        self, user_id: int, event_type: str
    ) -> Sequence[NotificationPreference]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type,
            )
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        user_id: int,
        event_type: str,
        channel: str,
        enabled: bool,
    ) -> NotificationPreference:
        from sqlalchemy import select

        result = await self.session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type,
                NotificationPreference.channel == channel,
            )
        )
        pref = result.scalar_one_or_none()

        if pref is not None:
            pref.enabled = enabled
        else:
            pref = NotificationPreference(
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                enabled=enabled,
            )
            self.session.add(pref)

        await self.session.flush()
        return pref

    async def set_all_for_user(
        self,
        user_id: int,
        preferences: list[dict],
    ) -> Sequence[NotificationPreference]:
        """Bulk upsert preferences for a user."""
        results: list[NotificationPreference] = []
        for pref in preferences:
            p = await self.upsert(
                user_id=user_id,
                event_type=pref["event_type"],
                channel=pref.get("channel", CHANNEL_IN_APP),
                enabled=pref.get("enabled", True),
            )
            results.append(p)
        return results


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class NotificationPreferenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationPreferenceRepository(session)

    async def get_preferences(self, user_id: int) -> list[dict]:
        prefs = await self.repo.find_by_user(user_id)
        return [
            {
                "id": p.id,
                "user_id": p.user_id,
                "event_type": p.event_type,
                "channel": p.channel,
                "enabled": p.enabled,
            }
            for p in prefs
        ]

    async def is_enabled(
        self, user_id: int, event_type: str, channel: str = CHANNEL_IN_APP
    ) -> bool:
        """Check if a user has a notification type enabled for a channel.

        Returns ``True`` when no explicit preference exists (opt-in by
        default for in-app; other channels require explicit opt-in).
        """
        prefs = await self.repo.find_by_user_and_event(user_id, event_type)
        for p in prefs:
            if p.channel == channel:
                return p.enabled

        # Default: in-app is opt-in by default, others require opt-in
        if channel == CHANNEL_IN_APP:
            return True
        return False

    async def update_preference(
        self, user_id: int, event_type: str, channel: str, enabled: bool
    ) -> dict:
        pref = await self.repo.upsert(user_id, event_type, channel, enabled)
        return {
            "id": pref.id,
            "user_id": pref.user_id,
            "event_type": pref.event_type,
            "channel": pref.channel,
            "enabled": pref.enabled,
        }

    async def bulk_update(
        self, user_id: int, preferences: list[dict]
    ) -> list[dict]:
        prefs = await self.repo.set_all_for_user(user_id, preferences)
        return [
            {
                "id": p.id,
                "user_id": p.user_id,
                "event_type": p.event_type,
                "channel": p.channel,
                "enabled": p.enabled,
            }
            for p in prefs
        ]
