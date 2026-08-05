"""Notification channel abstractions.

Each channel implements the ``NotificationChannel`` protocol so that
handlers dispatch messages without knowing the delivery mechanism.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.repository import UserRepository
from app.domains.notifications.email_service import send_email
from app.domains.notifications.models import Notification
from app.domains.notifications.push_service import send_push_via_expo
from app.domains.notifications.repository import NotificationRepository, DeviceTokenRepository
from app.domains.notifications.sse_manager import sse_manager
from app.multi_tenant.models import platform_context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel message type
# ---------------------------------------------------------------------------


class ChannelMessage:
    """A structured message to be delivered through a notification channel."""

    __slots__ = ("user_id", "event_type", "title", "message", "data", "tenant_id", "event_key")

    def __init__(
        self,
        user_id: int,
        event_type: str,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
        tenant_id: int | None = None,
        event_key: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.event_type = event_type
        self.title = title
        self.message = message
        self.data = data
        self.tenant_id = tenant_id
        self.event_key = event_key


# ---------------------------------------------------------------------------
# Channel interface
# ---------------------------------------------------------------------------


class NotificationChannel(Protocol):
    """Protocol for a notification delivery channel."""

    async def deliver(self, msg: ChannelMessage) -> bool: ...


# ---------------------------------------------------------------------------
# In-App Channel
# ---------------------------------------------------------------------------


class InAppChannel:
    """Delivers notifications as in-app Notification records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Notification delivery is a platform-level operation (events fire
        # for users across every campus), so the repository is constructed
        # with an explicit platform context — tenant=None would fail closed.
        self.repo = NotificationRepository(session, platform_context())

    async def deliver(self, msg: ChannelMessage) -> bool:
        try:
            # DB-level dedup: skip when an unread notification for the same
            # business event already exists for this user. The in-memory
            # dispatcher dedup only covers one process lifetime; this guard
            # survives restarts and duplicate publishes.
            if msg.event_key:
                if await self.repo.exists_unread_by_event_key(
                    msg.user_id, msg.event_key
                ):
                    logger.debug(
                        "Skipping duplicate notification event_key=%s for user %s",
                        msg.event_key,
                        msg.user_id,
                    )
                    return False

            notification = Notification(
                user_id=msg.user_id,
                type=msg.event_type,
                title=msg.title,
                message=msg.message,
                data=msg.data,
                event_key=msg.event_key,
            )
            await self.repo.create(notification)
            count = await self.repo.count_unread(msg.user_id)
            await sse_manager.publish(msg.user_id, "unread_count", str(count))
            return True
        except Exception:
            logger.warning(
                "In-app notification delivery failed for user %s",
                msg.user_id,
                exc_info=True,
            )
            return False


# ---------------------------------------------------------------------------
# Push Channel
# ---------------------------------------------------------------------------


class PushChannel:
    """Delivers push notifications to the user's registered devices."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Platform-level delivery (devices across every campus) — explicit
        # platform context, never implicit tenant=None.
        self.token_repo = DeviceTokenRepository(session, platform_context())

    async def deliver(self, msg: ChannelMessage) -> bool:
        try:
            tokens = await self.token_repo.find_by_user(msg.user_id)
            push_tokens = [t.token for t in tokens if t.token]
            if not push_tokens:
                logger.debug(
                    "No device tokens for user %s — skipping push",
                    msg.user_id,
                )
                return False

            tickets = await send_push_via_expo(
                push_tokens=push_tokens,
                title=msg.title,
                body=msg.message,
                data=msg.data,
            )
            return len(tickets) > 0
        except Exception:
            logger.warning(
                "Push notification delivery failed for user %s",
                msg.user_id,
                exc_info=True,
            )
            return False


# ---------------------------------------------------------------------------
# Email Channel (SendGrid via httpx)
# ---------------------------------------------------------------------------


class EmailChannel:
    """Delivers notifications via email using SendGrid.

    Looks up the user's email address from the database, then sends
    a formatted HTML email via the SendGrid API.

    Falls back to logging when:
    - No SendGrid API key is configured (soft pass)
    - The user's email cannot be resolved
    - The SendGrid API returns an error
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def deliver(self, msg: ChannelMessage) -> bool:
        try:
            user = await self.user_repo.get_by_id(msg.user_id)
            if not user or not user.email:
                logger.warning(
                    "Cannot send email for user %d — no email address",
                    msg.user_id,
                )
                return False

            return await send_email(
                to_email=user.email,
                to_name=user.display_name or None,
                subject=msg.title,
                plain_body=msg.message,
            )
        except Exception:
            logger.warning(
                "Email delivery failed for user %s",
                msg.user_id,
                exc_info=True,
            )
            return False


# ---------------------------------------------------------------------------
# SMS Channel (placeholder — kept for future Twilio/AWS SNS integration)
# ---------------------------------------------------------------------------


class SMSChannel:
    """Delivers notifications via SMS.

    Currently a placeholder that logs the message. Real integration
    requires an SMS provider (Twilio, AWS SNS, etc.).
    """

    async def deliver(self, msg: ChannelMessage) -> bool:
        logger.info(
            "[SMS] To user %d: %s — %s",
            msg.user_id,
            msg.title,
            msg.message,
        )
        # TODO: Implement SMS delivery via configured provider
        return True


# ---------------------------------------------------------------------------
# Channel factory
# ---------------------------------------------------------------------------

CHANNEL_MAP: dict[str, type] = {
    "in_app": InAppChannel,
    "push": PushChannel,
    "email": EmailChannel,
    "sms": SMSChannel,
}


def get_channel(name: str, session: AsyncSession) -> NotificationChannel:
    """Return a channel instance by name."""
    cls = CHANNEL_MAP.get(name)
    if cls is None:
        raise ValueError(f"Unknown notification channel: {name}")

    # SMS channel is still session-free (placeholder);
    # Email channel now needs a session to look up user emails.
    if cls is SMSChannel:
        return cls()  # type: ignore[return-value]
    return cls(session)  # type: ignore[return-value]
