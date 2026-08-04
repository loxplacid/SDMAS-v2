"""CSV export endpoint for audit logs.

Provides a ``GET /api/admin/audit-logs/export`` endpoint that returns a
CSV file with the same filter parameters as the JSON list endpoint.
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.service import AuditService
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/admin/audit-logs", tags=["audit"])


@router.get("/export")
async def export_audit_logs(
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    resource_id: Optional[str] = Query(default=None),
    campus_id: Optional[int] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    actor_type: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    limit: int = Query(default=10000, ge=1, le=100000),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> StreamingResponse:
    """Export audit logs as CSV.

    Supports the same filters as the list endpoint.  Tenant-scoped
    admins can only ever export their own campus's entries — a
    client-supplied ``campus_id`` is honoured for platform callers
    only (mirrors the JSON list endpoint).  Returns a streaming CSV
    response with appropriate headers.
    """
    effective_campus = effective_campus_id(tenant, campus_id)
    svc = AuditService(session, tenant)
    items, _ = await svc.list_entries(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        campus_id=effective_campus,
        start_date=start_date,
        end_date=end_date,
        actor_type=actor_type,
        actor_id=actor_id,
        result=result,
        skip=0,
        limit=limit,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "ID",
        "Event ID",
        "Timestamp",
        "Action",
        "Resource Type",
        "Resource ID",
        "Username",
        "User ID",
        "Actor Type",
        "Actor ID",
        "Result",
        "Failure Reason",
        "Campus ID",
        "Tenant ID",
        "Correlation ID",
        "IP Address",
        "User Agent",
        "Details",
    ])

    for entry in items:
        writer.writerow([
            entry.id,
            entry.event_id or "",
            entry.created_at.isoformat() if entry.created_at else "",
            entry.action,
            entry.resource_type,
            entry.resource_id or "",
            entry.username or "",
            entry.user_id or "",
            entry.actor_type or "",
            entry.actor_id or "",
            entry.result or "",
            (entry.failure_reason or "")[:500],
            entry.campus_id or "",
            entry.tenant_id or "",
            entry.correlation_id or "",
            entry.ip_address or "",
            (entry.user_agent or "")[:200],
            (entry.details or "")[:1000],
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=audit_logs.csv",
        },
    )
