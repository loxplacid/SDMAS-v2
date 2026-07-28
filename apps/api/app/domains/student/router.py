from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import (
    StudentCreate,
    StudentResponse,
    StudentUpdate,
)
from app.domains.student.service import StudentService
from app.infrastructure.database import get_session

router = APIRouter(prefix="/students", tags=["students"])


async def get_student_service(
    session: AsyncSession = Depends(get_session),
) -> StudentService:
    return StudentService(StudentRepository(session))


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    data: StudentCreate,
    service: StudentService = Depends(get_student_service),
) -> StudentResponse:
    student = await service.create_student(data)
    return StudentResponse.model_validate(student)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    service: StudentService = Depends(get_student_service),
) -> StudentResponse:
    student = await service.get_student(student_id)
    return StudentResponse.model_validate(student)


@router.get("", response_model=Page[StudentResponse])
async def list_students(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by student status"
    ),
    search: Optional[str] = Query(
        default=None, description="Search across name, number, email"
    ),
    service: StudentService = Depends(get_student_service),
) -> Page[StudentResponse]:
    if search:
        students, total = await service.search_students(
            query=search,
            skip=pagination.offset,
            limit=pagination.limit,
        )
    else:
        students, total = await service.list_students(
            status=status_filter,
            skip=pagination.offset,
            limit=pagination.limit,
        )

    items = [StudentResponse.model_validate(s) for s in students]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    data: StudentUpdate,
    service: StudentService = Depends(get_student_service),
) -> StudentResponse:
    student = await service.update_student(student_id, data)
    return StudentResponse.model_validate(student)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    service: StudentService = Depends(get_student_service),
) -> None:
    await service.delete_student(student_id)