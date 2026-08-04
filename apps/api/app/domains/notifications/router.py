from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.notifications.schemas import (
    NotificationPreferenceBulkUpdate,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    UnreadCountResponse,
)
from app.domains.notifications.service import NotificationService
from app.domains.notifications.preferences import NotificationPreferenceService
from app.domains.notifications.sse_manager import sse_manager
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationResponse])
async def list_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    unread_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[NotificationResponse]:
    svc = NotificationService(session, tenant)
    items, total = await svc.get_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    return Page(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=max(1, (total + limit - 1) // limit),
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> UnreadCountResponse:
    svc = NotificationService(session, tenant)
    count = await svc.get_unread_count(current_user.id)
    return UnreadCountResponse(count=count)


@router.get("/events")
async def notification_events(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> StreamingResponse:
    """SSE endpoint for real-time notification updates.

    Replaces 30-second polling.  The client connects once and receives
    ``unread_count`` events whenever a new notification is created.
    A 30-second heartbeat keeps the connection alive.
    """
    queue = sse_manager.subscribe(current_user.id)

    async def event_generator() -> None:
        try:
            svc = NotificationService(session, tenant)
            count = await svc.get_unread_count(current_user.id)
            yield f"event: unread_count\ndata: {count}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield data
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_manager.unsubscribe(current_user.id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> NotificationResponse:
    svc = NotificationService(session, tenant)
    existing = await svc.repo.get_by_id(notification_id)
    if existing.user_id != current_user.id:
        # Do not leak the existence of other users' notifications.
        from app.core.exceptions import NotFoundError
        raise NotFoundError(
            f"Notification with id {notification_id} not found"
        )
    notification = await svc.mark_as_read(notification_id)
    return NotificationResponse.model_validate(notification)


@router.patch("/read-all", response_model=UnreadCountResponse)
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> UnreadCountResponse:
    svc = NotificationService(session, tenant)
    await svc.mark_all_as_read(current_user.id)
    return UnreadCountResponse(count=0)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = NotificationService(session, tenant)
    existing = await svc.repo.get_by_id(notification_id)
    if existing.user_id != current_user.id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(
            f"Notification with id {notification_id} not found"
        )
    await svc.delete_notification(notification_id)


# ---------------------------------------------------------------------------
# Notification Preferences
# ---------------------------------------------------------------------------


@router.get(
    "/preferences",
    response_model=list[NotificationPreferenceResponse],
)
async def list_preferences(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[NotificationPreferenceResponse]:
    svc = NotificationPreferenceService(session)
    prefs = await svc.get_preferences(current_user.id)
    return [NotificationPreferenceResponse.model_validate(p) for p in prefs]


@router.put(
    "/preferences",
    response_model=list[NotificationPreferenceResponse],
)
async def update_preferences(
    data: NotificationPreferenceBulkUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[NotificationPreferenceResponse]:
    svc = NotificationPreferenceService(session)
    prefs = await svc.bulk_update(
        current_user.id,
        [p.model_dump() for p in data.preferences],
    )
    return [NotificationPreferenceResponse.model_validate(p) for p in prefs]


@router.put(
    "/preferences/{event_type}",
    response_model=NotificationPreferenceResponse,
)
async def update_preference(
    event_type: str,
    data: NotificationPreferenceUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferenceResponse:
    svc = NotificationPreferenceService(session)
    pref = await svc.update_preference(
        user_id=current_user.id,
        event_type=data.event_type,
        channel=data.channel,
        enabled=data.enabled,
    )
    return NotificationPreferenceResponse.model_validate(pref)
