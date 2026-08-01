"""Class 360 router.

Read-only aggregated view of a class.  Protected by ``academic.view`` and
pinned to the caller's tenant (campus) so cross-campus data can never leak.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_permission
from app.domains.auth.permissions import ACADEMIC_VIEW
from app.domains.class_360.schemas import Class360Response
from app.domains.class_360.service import Class360Service
from app.domains.academic.repository import ClassRepository
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_optional_tenant
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/classes/{class_id}/360", tags=["class-360"])


async def get_360_service(
    session: AsyncSession = Depends(get_session),
) -> Class360Service:
    return Class360Service(session)


@router.get("", response_model=Class360Response)
async def get_class_360(
    class_id: int,
    service: Class360Service = Depends(get_360_service),
    tenant: TenantContext = Depends(get_optional_tenant),
    campus_id: int | None = Query(default=None),
    _user=Depends(require_permission(ACADEMIC_VIEW)),
) -> Class360Response:
    # Verify the class belongs to the caller's campus before aggregating.
    session = service.session
    cls = await ClassRepository(session).get_by_id(class_id)
    assert_tenant_scope(cls, tenant, resource="class")

    scope = effective_campus_id(tenant, campus_id)
    return await service.get_class_360(class_id, campus_id=scope)
