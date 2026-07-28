from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.student.models import Student


class StudentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, student_id: int) -> Student:
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    async def get_by_student_number(self, student_number: str) -> Student | None:
        result = await self.session.execute(
            select(Student).where(Student.student_number == student_number)
        )
        return result.scalar_one_or_none()

    async def exists_by_student_number(self, student_number: str) -> bool:
        result = await self.session.execute(
            select(func.count(Student.id)).where(
                Student.student_number == student_number
            )
        )
        return (result.scalar() or 0) > 0

    async def list(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Student], int]:
        query = select(Student)
        count_query = select(func.count(Student.id))

        if status is not None:
            query = query.where(Student.status == status)
            count_query = count_query.where(Student.status == status)

        query = query.offset(skip).limit(limit).order_by(Student.id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        students = result.scalars().all()

        return students, total

    async def search(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Student], int]:
        like_term = f"%{query}%"
        where_clause = (
            Student.first_name.ilike(like_term)
            | Student.last_name.ilike(like_term)
            | Student.student_number.ilike(like_term)
            | Student.email.ilike(like_term)
        )
        stmt = (
            select(Student)
            .where(where_clause)
            .order_by(Student.id)
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count(Student.id)).where(where_clause)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        result = await self.session.execute(stmt)
        students = result.scalars().all()

        return students, total

    async def create(self, student: Student) -> Student:
        self.session.add(student)
        await self.session.flush()
        return student

    async def update(self, student: Student) -> Student:
        await self.session.flush()
        return student

    async def delete(self, student: Student) -> None:
        await self.session.delete(student)