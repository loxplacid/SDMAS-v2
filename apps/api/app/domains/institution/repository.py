from __future__ import annotations

from typing import Generic, Optional, TypeVar

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.institution.models import (
    Institution,
    Campus,
    School,
    Department,
    Program,
    Branch,
    Semester,
)

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic CRUD repository for hierarchy entities."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def create(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_id(self, entity_id: int) -> T:
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            name = self.model.__name__
            raise NotFoundError(f"{name} with id {entity_id} not found")
        return entity

    async def list(
        self,
        parent_column: str | None = None,
        parent_id: int | None = None,
        status: Optional[str] = None,
        ids: list[int] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list, int]:
        conditions = []
        if parent_column and parent_id is not None:
            conditions.append(
                getattr(self.model, parent_column) == parent_id
            )
        if status:
            conditions.append(self.model.status == status)  # type: ignore[attr-defined]
        if ids is not None:
            # ``ids=[]`` (an empty allowed set) must still filter to zero
            # rows — never fall through to an unscoped query.
            conditions.append(self.model.id.in_(ids))  # type: ignore[attr-defined]

        query = select(self.model)
        if conditions:
            query = query.where(*conditions)
        query = query.order_by(self.model.name).offset(skip).limit(limit)  # type: ignore[attr-defined]

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(self.model.id))  # type: ignore[attr-defined]
        if conditions:
            count_query = count_query.where(*conditions)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        return items, total

    async def update(self, entity_id: int, **kwargs) -> T:
        entity = await self.get_by_id(entity_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(entity, key):
                setattr(entity, key, value)
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity_id: int) -> None:
        entity = await self.get_by_id(entity_id)
        await self.session.delete(entity)
        await self.session.flush()


# ---------------------------------------------------------------------------
# Concrete repository factories
# ---------------------------------------------------------------------------


class InstitutionRepository(BaseRepository[Institution]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Institution)


class CampusRepository(BaseRepository[Campus]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Campus)


class SchoolRepository(BaseRepository[School]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, School)


class DepartmentRepository(BaseRepository[Department]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Department)


class ProgramRepository(BaseRepository[Program]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Program)


class BranchRepository(BaseRepository[Branch]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Branch)


class SemesterRepository(BaseRepository[Semester]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Semester)
