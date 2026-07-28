from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.attendance.models import AttendanceRecord


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, record_id: int) -> AttendanceRecord:
        result = await self.session.execute(
            select(AttendanceRecord).where(AttendanceRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError(f"Attendance record with id {record_id} not found")
        return record

    async def create(self, record: AttendanceRecord) -> AttendanceRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def update(self, record: AttendanceRecord) -> AttendanceRecord:
        await self.session.flush()
        return record

    async def find_by_student_and_date_range(
        self,
        student_id: int,
        start_date: str,
        end_date: str,
    ) -> Sequence[AttendanceRecord]:
        result = await self.session.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
            .order_by(AttendanceRecord.attendance_date)
        )
        return result.scalars().all()

    async def find_by_section_and_date(
        self,
        section_id: int,
        date: str,
    ) -> Sequence[AttendanceRecord]:
        result = await self.session.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.section_id == section_id,
                AttendanceRecord.attendance_date == date,
            )
            .order_by(AttendanceRecord.attendance_date)
        )
        return result.scalars().all()

    async def find_by_section_and_date_range(
        self,
        section_id: int,
        start_date: str,
        end_date: str,
    ) -> Sequence[AttendanceRecord]:
        result = await self.session.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.section_id == section_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
            .order_by(AttendanceRecord.attendance_date)
        )
        return result.scalars().all()

    async def find_by_student_and_filters(
        self,
        student_id: int,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AttendanceRecord], int]:
        conditions = [AttendanceRecord.student_id == student_id]
        count_conditions = [AttendanceRecord.student_id == student_id]

        if academic_year_id is not None:
            conditions.append(
                AttendanceRecord.academic_year_id == academic_year_id
            )
            count_conditions.append(
                AttendanceRecord.academic_year_id == academic_year_id
            )
        if class_id is not None:
            conditions.append(AttendanceRecord.class_id == class_id)
            count_conditions.append(AttendanceRecord.class_id == class_id)
        if section_id is not None:
            conditions.append(AttendanceRecord.section_id == section_id)
            count_conditions.append(AttendanceRecord.section_id == section_id)
        if status is not None:
            conditions.append(AttendanceRecord.status == status)
            count_conditions.append(AttendanceRecord.status == status)
        if start_date is not None:
            conditions.append(AttendanceRecord.attendance_date >= start_date)
            count_conditions.append(
                AttendanceRecord.attendance_date >= start_date
            )
        if end_date is not None:
            conditions.append(AttendanceRecord.attendance_date <= end_date)
            count_conditions.append(
                AttendanceRecord.attendance_date <= end_date
            )

        count_result = await self.session.execute(
            select(func.count(AttendanceRecord.id)).where(
                and_(*count_conditions)
            )
        )
        total = count_result.scalar() or 0

        query = (
            select(AttendanceRecord)
            .where(and_(*conditions))
            .order_by(AttendanceRecord.attendance_date)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        records = result.scalars().all()

        return records, total

    async def find_duplicate(
        self,
        student_id: int,
        date: str,
        section_id: int,
    ) -> AttendanceRecord | None:
        result = await self.session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date == date,
                AttendanceRecord.section_id == section_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        student_id: Optional[int] = None,
        section_id: Optional[int] = None,
        status: Optional[str] = None,
        attendance_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AttendanceRecord], int]:
        query = select(AttendanceRecord)
        count_query = select(func.count(AttendanceRecord.id))

        if student_id is not None:
            query = query.where(AttendanceRecord.student_id == student_id)
            count_query = count_query.where(
                AttendanceRecord.student_id == student_id
            )
        if section_id is not None:
            query = query.where(AttendanceRecord.section_id == section_id)
            count_query = count_query.where(
                AttendanceRecord.section_id == section_id
            )
        if status is not None:
            query = query.where(AttendanceRecord.status == status)
            count_query = count_query.where(
                AttendanceRecord.status == status
            )
        if attendance_date is not None:
            query = query.where(
                AttendanceRecord.attendance_date == attendance_date
            )
            count_query = count_query.where(
                AttendanceRecord.attendance_date == attendance_date
            )

        query = query.offset(skip).limit(limit).order_by(AttendanceRecord.attendance_date, AttendanceRecord.id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        records = result.scalars().all()

        return records, total