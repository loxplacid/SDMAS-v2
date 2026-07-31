"""In-process SSE (Server-Sent Events) manager for real-time notification delivery.

Maintains a set of ``asyncio.Queue`` objects per user, one per connected
client.  When a notification is created, the ``InAppChannel`` publishes
the new unread count to all queues for that user, and the SSE endpoint
streams those events to the browser.

This replaces the 30-second polling in the frontend with push-based delivery.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages per-user SSE subscriber queues."""

    def __init__(self) -> None:
        self._queues: dict[int, set[asyncio.Queue[str]]] = defaultdict(set)

    def subscribe(self, user_id: int) -> asyncio.Queue[str]:
        """Register a new SSE client for a user and return its queue."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues[user_id].add(queue)
        logger.debug("SSE subscribe: user_id=%d (total=%d)", user_id, len(self._queues[user_id]))
        return queue

    def unsubscribe(self, user_id: int, queue: asyncio.Queue[str]) -> None:
        """Remove a client queue when the SSE connection closes."""
        self._queues[user_id].discard(queue)
        if not self._queues[user_id]:
            del self._queues[user_id]
        logger.debug("SSE unsubscribe: user_id=%d", user_id)

    async def publish(self, user_id: int, event: str, data: str) -> None:
        """Push an SSE event to all connected clients for a user."""
        queues = self._queues.get(user_id)
        if not queues:
            return
        payload = f"event: {event}\ndata: {data}\n\n"
        for queue in list(queues):
            try:
                await queue.put(payload)
            except Exception:
                logger.warning("Failed to publish SSE to user %d", user_id, exc_info=True)

    @property
    def active_connections(self) -> int:
        return sum(len(q) for q in self._queues.values())


sse_manager: SSEManager = SSEManager()
