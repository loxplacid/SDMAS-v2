from __future__ import annotations

from typing import Optional

from app.domains.institution.models import (
    Institution,
    Campus,
    School,
    Department,
    Program,
    Branch,
    Semester,
)
from app.domains.institution.repository import (
    InstitutionRepository,
    CampusRepository,
    SchoolRepository,
    DepartmentRepository,
    ProgramRepository,
    BranchRepository,
    SemesterRepository,
)


class InstitutionService:
    def __init__(self, repo: InstitutionRepository) -> None:
        self.repo = repo

    async def create(self, name: str, code: str) -> Institution:
        entity = Institution(name=name, code=code)
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> Institution:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, status: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> tuple[list[Institution], int]:
        return await self.repo.list(status=status, skip=skip, limit=limit)

    async def update(
        self, entity_id: int, name: Optional[str] = None,
        code: Optional[str] = None, status: Optional[str] = None,
    ) -> Institution:
        return await self.repo.update(entity_id, name=name, code=code, status=status)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)


class CampusService:
    def __init__(self, repo: CampusRepository) -> None:
        self.repo = repo

    async def create(
        self, institution_id: int, name: str, code: str,
        address: Optional[str] = None, phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Campus:
        entity = Campus(
            institution_id=institution_id, name=name, code=code,
            address=address, phone=phone, email=email,
        )
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> Campus:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, institution_id: Optional[int] = None,
        status: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[list[Campus], int]:
        return await self.repo.list(
            parent_column="institution_id", parent_id=institution_id,
            status=status, skip=skip, limit=limit,
        )

    async def update(
        self, entity_id: int, **kwargs,
    ) -> Campus:
        return await self.repo.update(entity_id, **kwargs)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)


class SchoolService:
    def __init__(self, repo: SchoolRepository) -> None:
        self.repo = repo

    async def create(
        self, campus_id: int, name: str, code: str,
        description: Optional[str] = None,
    ) -> School:
        entity = School(campus_id=campus_id, name=name, code=code, description=description)
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> School:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, campus_id: Optional[int] = None,
        status: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[list[School], int]:
        return await self.repo.list(
            parent_column="campus_id", parent_id=campus_id,
            status=status, skip=skip, limit=limit,
        )

    async def update(self, entity_id: int, **kwargs) -> School:
        return await self.repo.update(entity_id, **kwargs)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)


class DepartmentService:
    def __init__(self, repo: DepartmentRepository) -> None:
        self.repo = repo

    async def create(
        self, school_id: int, name: str, code: str,
        description: Optional[str] = None,
    ) -> Department:
        entity = Department(
            school_id=school_id, name=name, code=code, description=description,
        )
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> Department:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, school_id: Optional[int] = None,
        status: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[list[Department], int]:
        return await self.repo.list(
            parent_column="school_id", parent_id=school_id,
            status=status, skip=skip, limit=limit,
        )

    async def update(self, entity_id: int, **kwargs) -> Department:
        return await self.repo.update(entity_id, **kwargs)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)


class ProgramService:
    def __init__(self, repo: ProgramRepository) -> None:
        self.repo = repo

    async def create(
        self, department_id: int, name: str, code: str,
        duration_years: int = 4, description: Optional[str] = None,
    ) -> Program:
        entity = Program(
            department_id=department_id, name=name, code=code,
            duration_years=duration_years, description=description,
        )
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> Program:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, department_id: Optional[int] = None,
        status: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[list[Program], int]:
        return await self.repo.list(
            parent_column="department_id", parent_id=department_id,
            status=status, skip=skip, limit=limit,
        )

    async def update(self, entity_id: int, **kwargs) -> Program:
        return await self.repo.update(entity_id, **kwargs)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)


class BranchService:
    def __init__(self, repo: BranchRepository) -> None:
        self.repo = repo

    async def create(
        self, program_id: int, name: str, code: str,
        description: Optional[str] = None,
    ) -> Branch:
        entity = Branch(
            program_id=program_id, name=name, code=code, description=description,
        )
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> Branch:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, program_id: Optional[int] = None,
        status: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[list[Branch], int]:
        return await self.repo.list(
            parent_column="program_id", parent_id=program_id,
            status=status, skip=skip, limit=limit,
        )

    async def update(self, entity_id: int, **kwargs) -> Branch:
        return await self.repo.update(entity_id, **kwargs)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)


class SemesterService:
    def __init__(self, repo: SemesterRepository) -> None:
        self.repo = repo

    async def create(
        self, program_id: int, name: str, code: str,
        semester_number: int, start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Semester:
        entity = Semester(
            program_id=program_id, name=name, code=code,
            semester_number=semester_number,
            start_date=start_date, end_date=end_date,
        )
        return await self.repo.create(entity)

    async def get(self, entity_id: int) -> Semester:
        return await self.repo.get_by_id(entity_id)

    async def list(
        self, program_id: Optional[int] = None,
        status: Optional[str] = None, skip: int = 0, limit: int = 100,
    ) -> tuple[list[Semester], int]:
        return await self.repo.list(
            parent_column="program_id", parent_id=program_id,
            status=status, skip=skip, limit=limit,
        )

    async def update(self, entity_id: int, **kwargs) -> Semester:
        return await self.repo.update(entity_id, **kwargs)

    async def delete(self, entity_id: int) -> None:
        await self.repo.delete(entity_id)
