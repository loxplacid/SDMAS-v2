"""School Command Center router — single aggregated overview endpoint."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_role
from app.domains.auth.models import User
from app.domains.command_center.schemas import CommandCenterOverview
from app.domains.command_center.service import CommandCenterService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/command-center", tags=["command-center"])


async def get_command_center_service(
    session: AsyncSession = Depends(get_session),
) -> CommandCenterService:
    return CommandCenterService(session)


@router.get("/overview", response_model=CommandCenterOverview)
async def get_command_center_overview(
    current_user: User = Depends(
        require_role("admin", "principal", "accountant", "staff", "teacher")
    ),
    tenant: TenantContext = Depends(require_tenant_context),
    service: CommandCenterService = Depends(get_command_center_service),
) -> CommandCenterOverview:
    """Aggregated School Command Center overview.

    One request powers the entire leadership landing page: school
    health, deterministic alerts, today's operational events, quick
    actions, and recent activity. Each section degrades independently
    (``available`` flag) so the page still renders when a single data
    source fails.
    """
    campus_id: Optional[int] = effective_campus_id(tenant, None)
    return await service.get_overview(
        role=current_user.role,
        user=current_user,
        campus_id=campus_id,
    )
