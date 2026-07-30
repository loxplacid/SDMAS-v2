"""Push notification service using the Expo Push API.

Architecture:
  Mobile (Expo) ───expo-notifications──→ FCM/APNs ──→ Device
       │                                       ↑
       │ Register token                        │
       ▼                                       │
  Backend ─────POST exp.host/--/api/v2/push/send──┘

The Expo Push API is an HTTP endpoint that accepts Expo push tokens
and delivers the notification through FCM (Android) or APNs (iOS).
No Firebase Admin SDK or Google credentials are needed on the backend.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import DeviceToken
from app.domains.notifications.schemas import PushTicketResponse

logger = logging.getLogger(__name__)

EXPO_PUSH_API = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_API_TIMEOUT = 10  # seconds


async def send_push_via_expo(
    push_tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> list[PushTicketResponse]:
    """Send a push notification via the Expo Push API.

    Args:
        push_tokens: List of Expo push tokens (e.g.
            "ExponentPushToken[xxxxxxxxxx]").
        title: Notification title.
        body: Notification body text.
        data: Optional JSON-serializable payload.

    Returns:
        A list of ticket responses from the Expo API, one per token.
    """
    if not push_tokens:
        logger.debug("No push tokens to send to — skipping push notification.")
        return []

    messages = [
        {
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "priority": "high",
            "data": data or {},
        }
        for token in push_tokens
    ]

    try:
        import httpx

        async with httpx.AsyncClient(timeout=EXPO_PUSH_API_TIMEOUT) as client:
            response = await client.post(
                EXPO_PUSH_API,
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                content=json.dumps(messages),
            )

        if response.is_error:
            logger.error(
                "Expo Push API returned error %s: %s",
                response.status_code,
                response.text,
            )
            return []

        result = response.json()
        tickets = result.get("data", [])
        logger.info(
            "Sent %d push notification(s), received %d ticket(s)",
            len(messages),
            len(tickets),
        )

        # Log any errors
        for i, ticket in enumerate(tickets):
            if ticket.get("status") == "error":
                logger.error(
                    "Push notification error for token %d: %s",
                    i,
                    ticket.get("message", "unknown error"),
                )

        return [PushTicketResponse(**t) for t in tickets]

    except ImportError:
        logger.warning(
        "httpx not installed — cannot send push notifications. "
        "Install with: uv add httpx"
        )
        return []
    except asyncio.TimeoutError:
        logger.error("Expo Push API request timed out after %ds", EXPO_PUSH_API_TIMEOUT)
        return []
    except Exception as exc:
        logger.exception("Failed to send push notification: %s", exc)
        return []
