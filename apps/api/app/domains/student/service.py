from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import (
    EMAIL_REGEX,
    VALID_STATUSES,
    StudentCreate,
    StudentUpdate,
)


class StudentService:
    def __init__(self, repository: StudentRepository) -> None:
        self.repository = repository

    async def create_student(self, data: StudentCreate) -> Student:
        existing = await self.repository.get_by_student_number(data.student_number)
        if existing is not None:
            raise ConflictError(
                f"Student with number {data.student_number} already exists"
            )

        student = Student(
            first_name=data.first_name,
            last_name=data.last_name,
            student_number=data.student_number,
            email=data.email,
            date_of_birth=data.date_of_birth,
            status="active",
        )
        try:
            return await self.repository.create(student)
        except IntegrityError:
            raise ConflictError(
                f"Student with number {data.student_number} already exists"
            )

    async def get_student(self, student_id: int) -> Student:
        return await self.repository.get_by_id(student_id)

    async def find_by_student_number(self, student_number: str) -> Student:
        student = await self.repository.get_by_student_number(student_number)
        if student is None:
            raise NotFoundError(
                f"Student with number {student_number} not found"
            )
        return student

    async def update_student(
        self, student_id: int, data: StudentUpdate
    ) -> Student:
        student = await self.repository.get_by_id(student_id)

        if data.first_name is not None:
            student.first_name = data.first_name
        if data.last_name is not None:
            student.last_name = data.last_name
        if data.email is not None:
            student.email = data.email
        if data.status is not None:
            student.status = data.status
        if data.date_of_birth is not None:
            student.date_of_birth = data.date_of_birth

        try:
            return await self.repository.update(student)
        except IntegrityError:
            raise ConflictError("Duplicate student number")

    async def delete_student(self, student_id: int) -> None:
        student = await self.repository.get_by_id(student_id)
        await self.repository.delete(student)

    async def deactivate_student(self, student_id: int) -> Student:
        student = await self.repository.get_by_id(student_id)
        if student.status == "inactive":
            raise ConflictError(
                f"Student with id {student_id} is already inactive"
            )
        student.status = "inactive"
        return await self.repository.update(student)

    async def reactivate_student(self, student_id: int) -> Student:
        student = await self.repository.get_by_id(student_id)
        if student.status == "active":
            raise ConflictError(
                f"Student with id {student_id} is already active"
            )
        student.status = "active"
        return await self.repository.update(student)

    async def list_students(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Student], int]:
        if status is not None and status not in VALID_STATUSES:
            raise ValidationError(f"Invalid status filter: {status}")
        return await self.repository.list(status=status, skip=skip, limit=limit)

    async def search_students(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Student], int]:
        if not query or not query.strip():
            raise ValidationError("Search query is required")
        return await self.repository.search(query.strip().lower(), skip=skip, limit=limit)