from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment


# ---------------------------------------------------------------------------
# FeeTypeRepository
# ---------------------------------------------------------------------------


class FeeTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, type_id: int) -> FeeType:
        result = await self.session.execute(
            select(FeeType).where(FeeType.id == type_id)
        )
        ft = result.scalar_one_or_none()
        if ft is None:
            raise NotFoundError(f"Fee type with id {type_id} not found")
        return ft

    async def get_by_name(self, name: str) -> FeeType | None:
        result = await self.session.execute(
            select(FeeType).where(FeeType.name == name)
        )
        return result.scalar_one_or_none()

    async def exists_by_name(self, name: str) -> bool:
        result = await self.session.execute(
            select(func.count(FeeType.id)).where(FeeType.name == name)
        )
        return (result.scalar() or 0) > 0

    async def list(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeType], int]:
        query = select(FeeType)
        count_query = select(func.count(FeeType.id))

        if status is not None:
            query = query.where(FeeType.status == status)
            count_query = count_query.where(FeeType.status == status)
        if campus_id is not None:
            query = query.where(FeeType.campus_id == campus_id)
            count_query = count_query.where(FeeType.campus_id == campus_id)

        query = query.offset(skip).limit(limit).order_by(FeeType.name)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, fee_type: FeeType) -> FeeType:
        self.session.add(fee_type)
        await self.session.flush()
        return fee_type

    async def update(self, fee_type: FeeType) -> FeeType:
        await self.session.flush()
        return fee_type

    async def delete(self, fee_type: FeeType) -> None:
        await self.session.delete(fee_type)


# ---------------------------------------------------------------------------
# FeeStructureRepository
# ---------------------------------------------------------------------------


class FeeStructureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, structure_id: int) -> FeeStructure:
        result = await self.session.execute(
            select(FeeStructure).where(FeeStructure.id == structure_id)
        )
        fs = result.scalar_one_or_none()
        if fs is None:
            raise NotFoundError(f"Fee structure with id {structure_id} not found")
        return fs

    async def get_by_year_class_type(
        self, academic_year_id: int, class_id: int, fee_type_id: int
    ) -> FeeStructure | None:
        result = await self.session.execute(
            select(FeeStructure).where(
                FeeStructure.academic_year_id == academic_year_id,
                FeeStructure.class_id == class_id,
                FeeStructure.fee_type_id == fee_type_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        fee_type_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeStructure], int]:
        query = select(FeeStructure)
        count_query = select(func.count(FeeStructure.id))

        if academic_year_id is not None:
            query = query.where(
                FeeStructure.academic_year_id == academic_year_id
            )
            count_query = count_query.where(
                FeeStructure.academic_year_id == academic_year_id
            )
        if class_id is not None:
            query = query.where(FeeStructure.class_id == class_id)
            count_query = count_query.where(
                FeeStructure.class_id == class_id
            )
        if fee_type_id is not None:
            query = query.where(FeeStructure.fee_type_id == fee_type_id)
            count_query = count_query.where(
                FeeStructure.fee_type_id == fee_type_id
            )
        if status is not None:
            query = query.where(FeeStructure.status == status)
            count_query = count_query.where(
                FeeStructure.status == status
            )
        if campus_id is not None:
            query = query.where(FeeStructure.campus_id == campus_id)
            count_query = count_query.where(
                FeeStructure.campus_id == campus_id
            )

        query = query.offset(skip).limit(limit).order_by(FeeStructure.id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, structure: FeeStructure) -> FeeStructure:
        self.session.add(structure)
        await self.session.flush()
        return structure

    async def update(self, structure: FeeStructure) -> FeeStructure:
        await self.session.flush()
        return structure


# ---------------------------------------------------------------------------
# FeeDueRepository
# ---------------------------------------------------------------------------


class FeeDueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, due_id: int) -> FeeDue:
        result = await self.session.execute(
            select(FeeDue).where(FeeDue.id == due_id)
        )
        due = result.scalar_one_or_none()
        if due is None:
            raise NotFoundError(f"Fee due with id {due_id} not found")
        return due

    async def get_by_id_for_update(self, due_id: int) -> FeeDue:
        result = await self.session.execute(
            select(FeeDue)
            .where(FeeDue.id == due_id)
            .with_for_update()
        )
        due = result.scalar_one_or_none()
        if due is None:
            raise NotFoundError(f"Fee due with id {due_id} not found")
        return due

    async def get_by_student_and_structure(
        self, student_id: int, fee_structure_id: int
    ) -> FeeDue | None:
        result = await self.session.execute(
            select(FeeDue).where(
                FeeDue.student_id == student_id,
                FeeDue.fee_structure_id == fee_structure_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        student_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[FeeDue], int]:
        query = select(FeeDue)
        count_query = select(func.count(FeeDue.id))

        if student_id is not None:
            query = query.where(FeeDue.student_id == student_id)
            count_query = count_query.where(
                FeeDue.student_id == student_id
            )
        if academic_year_id is not None:
            query = query.where(
                FeeDue.academic_year_id == academic_year_id
            )
            count_query = count_query.where(
                FeeDue.academic_year_id == academic_year_id
            )
        if status is not None:
            query = query.where(FeeDue.status == status)
            count_query = count_query.where(FeeDue.status == status)
        if campus_id is not None:
            query = query.where(FeeDue.campus_id == campus_id)
            count_query = count_query.where(FeeDue.campus_id == campus_id)

        query = query.offset(skip).limit(limit).order_by(FeeDue.id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def find_by_student(
        self,
        student_id: int,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Sequence[FeeDue]:
        conditions = [FeeDue.student_id == student_id]
        if academic_year_id is not None:
            conditions.append(
                FeeDue.academic_year_id == academic_year_id
            )
        if status is not None:
            conditions.append(FeeDue.status == status)

        result = await self.session.execute(
            select(FeeDue)
            .where(and_(*conditions))
            .order_by(FeeDue.created_at)
        )
        return result.scalars().all()

    async def find_by_academic_year(
        self, academic_year_id: int
    ) -> Sequence[FeeDue]:
        result = await self.session.execute(
            select(FeeDue)
            .where(FeeDue.academic_year_id == academic_year_id)
            .order_by(FeeDue.id)
        )
        return result.scalars().all()

    async def create(self, due: FeeDue) -> FeeDue:
        self.session.add(due)
        await self.session.flush()
        return due

    async def update(self, due: FeeDue) -> FeeDue:
        await self.session.flush()
        return due


# ---------------------------------------------------------------------------
# PaymentRepository
# ---------------------------------------------------------------------------


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, payment_id: int) -> Payment:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            raise NotFoundError(f"Payment with id {payment_id} not found")
        return payment

    async def get_by_receipt_number(
        self, receipt_number: str
    ) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(
                Payment.receipt_number == receipt_number
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        student_id: Optional[int] = None,
        fee_due_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Payment], int]:
        query = select(Payment)
        count_query = select(func.count(Payment.id))

        if student_id is not None:
            query = query.where(Payment.student_id == student_id)
            count_query = count_query.where(
                Payment.student_id == student_id
            )
        if fee_due_id is not None:
            query = query.where(Payment.fee_due_id == fee_due_id)
            count_query = count_query.where(
                Payment.fee_due_id == fee_due_id
            )
        if campus_id is not None:
            query = query.where(Payment.campus_id == campus_id)
            count_query = count_query.where(
                Payment.campus_id == campus_id
            )

        query = query.offset(skip).limit(limit).order_by(Payment.created_at)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def find_by_student(
        self, student_id: int
    ) -> Sequence[Payment]:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.student_id == student_id)
            .order_by(Payment.payment_date)
        )
        return result.scalars().all()

    async def find_by_fee_due(
        self, fee_due_id: int
    ) -> Sequence[Payment]:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.fee_due_id == fee_due_id)
            .order_by(Payment.payment_date)
        )
        return result.scalars().all()

    async def find_by_date_range(
        self,
        start_date: str,
        end_date: str,
        campus_id: Optional[int] = None,
    ) -> Sequence[Payment]:
        conditions = [
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
        ]
        if campus_id is not None:
            conditions.append(Payment.campus_id == campus_id)
        result = await self.session.execute(
            select(Payment)
            .where(*conditions)
            .order_by(Payment.payment_date)
        )
        return result.scalars().all()

    async def create(self, payment: Payment) -> Payment:
        self.session.add(payment)
        await self.session.flush()
        return payment