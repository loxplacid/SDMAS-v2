from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.student_portal.schemas import (
    StudentAnnouncementsResponse,
    StudentAssignmentsResponse,
    StudentAttendanceResponse,
    StudentDocumentsResponse,
    StudentPortalDashboardResponse,
    StudentResultsResponse,
    StudentSubjectsResponse,
    StudentTimetableResponse,
)
from app.domains.student_portal.service import StudentPortalService
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/student/portal", tags=["student-portal"])

STUDENT_ONLY = require_role("student")


async def get_portal_svc(
    session: AsyncSession = Depends(get_session),
) -> StudentPortalService:
    return StudentPortalService(session)


async def resolve_student(
    user: User = Depends(get_current_user),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> tuple[User, StudentPortalService, int]:
    """Resolve the student ID from the current user (campus-scoped)."""
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return user, svc, student.id


# ── Dashboard ────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=StudentPortalDashboardResponse)
async def get_dashboard(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentPortalDashboardResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_dashboard(student.id, student)


# ── Timetable ────────────────────────────────────────────────────────


@router.get("/timetable", response_model=StudentTimetableResponse)
async def get_timetable(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentTimetableResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_timetable(student.id)


# ── Attendance ───────────────────────────────────────────────────────


@router.get("/attendance", response_model=StudentAttendanceResponse)
async def get_attendance(
    days: int = Query(default=365, ge=1, le=365),
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentAttendanceResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_attendance(student.id, days=days)


# ── Subjects ─────────────────────────────────────────────────────────


@router.get("/subjects", response_model=StudentSubjectsResponse)
async def get_subjects(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentSubjectsResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_subjects(student.id)


# ── Academic Results ─────────────────────────────────────────────────


@router.get("/results", response_model=StudentResultsResponse)
async def get_results(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentResultsResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_results(student.id)


# ── Assignments ──────────────────────────────────────────────────────


@router.get("/assignments", response_model=StudentAssignmentsResponse)
async def get_assignments(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentAssignmentsResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_assignments(student.id)


# ── Announcements ────────────────────────────────────────────────────


@router.get("/announcements", response_model=StudentAnnouncementsResponse)
async def get_announcements(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentAnnouncementsResponse:
    return await svc.get_announcements(campus_id=user.campus_id)


# ── Documents ────────────────────────────────────────────────────────


@router.get("/documents", response_model=StudentDocumentsResponse)
async def get_documents(
    user: User = Depends(STUDENT_ONLY),
    svc: StudentPortalService = Depends(get_portal_svc),
) -> StudentDocumentsResponse:
    student = await svc.resolve_student(user.id, user.email, user.campus_id)
    return await svc.get_documents(student.id)
