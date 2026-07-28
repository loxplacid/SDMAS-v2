from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.notifications.schemas import (
    NotificationResponse,
    UnreadCountResponse,
)
from app.domains.notifications.service import NotificationService
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationResponse])
async def list_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    unread_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Page[NotificationResponse]:
    svc = NotificationService(session)
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
) -> UnreadCountResponse:
    svc = NotificationService(session)
    count = await svc.get_unread_count(current_user.id)
    return UnreadCountResponse(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> NotificationResponse:
    svc = NotificationService(session)
    notification = await svc.mark_as_read(notification_id)
    return NotificationResponse.model_validate(notification)


@router.patch("/read-all", response_model=UnreadCountResponse)
async def mark_all_notifications_read(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    svc = NotificationService(session)
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
) -> None:
    svc = NotificationService(session)
    await svc.delete_notification(notification_id)
