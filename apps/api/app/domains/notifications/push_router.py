from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.notifications.schemas import (
    DeviceTokenRegisterRequest,
    DeviceTokenResponse,
    PushSendRequest,
)
from app.domains.notifications.device_token_service import DeviceTokenService
from app.domains.notifications.push_service import send_push_via_expo
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/notifications", tags=["push"])


# ---------------------------------------------------------------------------
# Device Token Management
# ---------------------------------------------------------------------------


@router.post(
    "/device-tokens",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_device_token(
    data: DeviceTokenRegisterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DeviceTokenResponse:
    """Register a push notification device token for the authenticated user."""
    svc = DeviceTokenService(session, tenant)
    dt = await svc.register_token(
        user_id=current_user.id,
        token=data.token,
        platform=data.platform,
    )
    return DeviceTokenResponse.model_validate(dt)


@router.delete(
    "/device-tokens/{token:path}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unregister_device_token(
    token: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    """Remove a registered device token."""
    svc = DeviceTokenService(session, tenant)
    await svc.unregister_token(token)


@router.delete(
    "/device-tokens",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unregister_all_device_tokens(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    """Remove all device tokens for the authenticated user (logout)."""
    svc = DeviceTokenService(session, tenant)
    await svc.unregister_all_for_user(current_user.id)


# ---------------------------------------------------------------------------
# Send Push Notification (admin/staff only)
# ---------------------------------------------------------------------------


@router.post(
    "/send-push",
    status_code=status.HTTP_200_OK,
)
async def send_push_notification(
    data: PushSendRequest,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "staff")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> dict:
    """Send a push notification to a specific user.

    Requires admin or staff role. The notification is delivered to all
    registered devices for the target user.
    """
    svc = DeviceTokenService(session, tenant)
    tokens = await svc.get_tokens_for_user(data.user_id)

    if not tokens:
        return {
            "sent": False,
            "message": "User has no registered device tokens",
            "recipient_count": 0,
        }

    tickets = await send_push_via_expo(
        push_tokens=tokens,
        title=data.title,
        body=data.body,
        data=data.data,
    )

    return {
        "sent": True,
        "recipient_count": len(tokens),
        "ticket_count": len(tickets),
    }
