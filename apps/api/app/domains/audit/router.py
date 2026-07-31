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
) -> Page[AuditLogResponse]:
    """List audit log entries with optional filters.

    Requires ``admin`` role.
    """
    skip = (page - 1) * size
    svc = AuditService(session)
    items, total = await svc.list_entries(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        campus_id=campus_id,
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
) -> AuditLogResponse:
    """Retrieve a single audit log entry by ID.

    Requires ``admin`` role.
    """
    svc = AuditService(session)
    entry = await svc.get_entry(entry_id)
    return AuditLogResponse.model_validate(entry)
