from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.parent.schemas import (
    LinkChildRequest,
    ParentAcademicResponse,
    ParentAnnouncementsResponse,
    ParentAttendanceResponse,
    ParentCommunicationsResponse,
    ParentDashboardResponse,
    ParentDocumentsResponse,
    ParentFeesResponse,
    LinkedChild,
    ParentChildResponse,
)
from app.domains.parent.service import ParentService
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/parent", tags=["parent"])

# All parent routes require the parent role
PARENT_ONLY = require_role("parent")


async def get_parent_svc(
    session: AsyncSession = Depends(get_session),
) -> ParentService:
    return ParentService(session)


# ── Dashboard ────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=ParentDashboardResponse)
async def get_dashboard(
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentDashboardResponse:
    """Aggregated dashboard across all linked children."""
    return await svc.get_dashboard(user)


# ── Children ─────────────────────────────────────────────────────────


@router.get("/children", response_model=list[LinkedChild])
async def list_children(
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> list[LinkedChild]:
    """List all children linked to this parent."""
    return await svc.get_children(user.id)


@router.get("/children/{student_id}", response_model=ParentChildResponse)
async def get_child(
    student_id: int = Path(..., ge=1),
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentChildResponse:
    """Get detailed info about a specific linked child."""
    result = await svc.get_child_detail(user, student_id)
    return ParentChildResponse(**result)


# ── Link / Unlink ────────────────────────────────────────────────────


@router.post("/children/link", response_model=LinkedChild, status_code=status.HTTP_201_CREATED)
async def link_child(
    data: LinkChildRequest,
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> LinkedChild:
    """Link a student to this parent account."""
    guardian = await svc.link_child(user.id, data.student_id, data.relationship)
    # Return the child info
    children = await svc.get_children(user.id)
    child = next((c for c in children if c.id == data.student_id), None)
    if not child:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Student linked but could not be loaded")
    return child


@router.delete("/children/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_child(
    student_id: int = Path(..., ge=1),
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> None:
    """Unlink a student from this parent account."""
    await svc.unlink_child(user.id, student_id)


# ── Attendance ───────────────────────────────────────────────────────


@router.get(
    "/children/{student_id}/attendance",
    response_model=ParentAttendanceResponse,
)
async def get_child_attendance(
    student_id: int = Path(..., ge=1),
    days: int = Query(default=90, ge=1, le=365),
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentAttendanceResponse:
    """Get attendance data for a specific child."""
    return await svc.get_attendance(user, student_id, days=days)


# ── Fees / Payments / Receipts ───────────────────────────────────────


@router.get(
    "/children/{student_id}/fees",
    response_model=ParentFeesResponse,
)
async def get_child_fees(
    student_id: int = Path(..., ge=1),
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentFeesResponse:
    """Get fees, payments, and receipts for a specific child."""
    return await svc.get_fees(user, student_id)


# ── Academic Performance ─────────────────────────────────────────────


@router.get(
    "/children/{student_id}/academic",
    response_model=ParentAcademicResponse,
)
async def get_child_academic(
    student_id: int = Path(..., ge=1),
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentAcademicResponse:
    """Get academic performance data for a specific child."""
    return await svc.get_academic(user, student_id)


# ── Documents ────────────────────────────────────────────────────────


@router.get(
    "/children/{student_id}/documents",
    response_model=ParentDocumentsResponse,
)
async def get_child_documents(
    student_id: int = Path(..., ge=1),
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentDocumentsResponse:
    """Get documents for a specific child."""
    return await svc.get_documents(user, student_id)


# ── Announcements ────────────────────────────────────────────────────


@router.get("/announcements", response_model=ParentAnnouncementsResponse)
async def get_announcements(
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentAnnouncementsResponse:
    """Get school announcements visible to parents."""
    return await svc.get_announcements(user)


# ── Communications ───────────────────────────────────────────────────


@router.get("/communications", response_model=ParentCommunicationsResponse)
async def get_communications(
    svc: ParentService = Depends(get_parent_svc),
    user: User = Depends(PARENT_ONLY),
) -> ParentCommunicationsResponse:
    """Get communications addressed to this parent."""
    return await svc.get_communications(user)
