from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page
from app.domains.audit.schemas import AuditLogResponse
from app.domains.audit.service import AuditService
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_optional_tenant
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/admin/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogResponse])
async def list_audit_logs(
    user_id: Optional[int] = Query(default=None, description="Filter by actor user ID"),
    action: Optional[str] = Query(default=None, description="Filter by action (CREATE, UPDATE, DELETE)"),
    resource_type: Optional[str] = Query(default=None, description="Filter by resource type (e.g. student)"),
    resource_id: Optional[str] = Query(default=None, description="Filter by resource ID"),
    campus_id: Optional[int] = Query(default=None, description="Filter by campus"),
    start_date: Optional[str] = Query(default=None, description="ISO date lower bound (inclusive)"),
    end_date: Optional[str] = Query(default=None, description="ISO date upper bound (inclusive)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> Page[AuditLogResponse]:
    """List audit log entries with optional filters.

    Requires ``admin`` role. Tenant-scoped admins only ever see
    entries for their own campus; a client-supplied ``campus_id``
    filter is ignored for scoped admins.
    """
    effective_campus = effective_campus_id(tenant, campus_id)
    skip = (page - 1) * size
    svc = AuditService(session)
    items, total = await svc.list_entries(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        campus_id=effective_campus,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=size,
    )
    return Page(
        items=[AuditLogResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        size=size,
        pages=max(1, (total + size - 1) // size),
    )


@router.get("/{entry_id}", response_model=AuditLogResponse)
async def get_audit_log(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> AuditLogResponse:
    """Retrieve a single audit log entry by ID.

    Requires ``admin`` role. Tenant-scoped admins cannot read entries
    from other campuses.
    """
    svc = AuditService(session)
    entry = await svc.get_entry(entry_id)
    assert_tenant_scope(entry, tenant, resource="audit entry")
    return AuditLogResponse.model_validate(entry)
