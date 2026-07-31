from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import get_current_user, require_permission
from app.domains.student_360.schemas import Student360Response
from app.domains.student_360.service import Student360Service
from app.infrastructure.database import get_session

router = APIRouter(prefix="/students/{student_id}/360", tags=["student-360"])


async def get_360_service(
    session: AsyncSession = Depends(get_session),
) -> Student360Service:
    return Student360Service(session)


@router.get("", response_model=Student360Response)
async def get_student_360(
    student_id: int,
    service: Student360Service = Depends(get_360_service),
    _user=Depends(require_permission("students.view")),
) -> Student360Response:
    return await service.get_student_360(student_id)
