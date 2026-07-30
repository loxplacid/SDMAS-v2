from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.institution.repository import (
    InstitutionRepository,
    CampusRepository,
    SchoolRepository,
    DepartmentRepository,
    ProgramRepository,
    BranchRepository,
    SemesterRepository,
)
from app.domains.institution.schemas import (
    InstitutionCreate,
    InstitutionResponse,
    InstitutionUpdate,
    CampusCreate,
    CampusResponse,
    CampusUpdate,
    SchoolCreate,
    SchoolResponse,
    SchoolUpdate,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    ProgramCreate,
    ProgramResponse,
    ProgramUpdate,
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    SemesterCreate,
    SemesterResponse,
    SemesterUpdate,
)
from app.domains.institution.service import (
    InstitutionService,
    CampusService,
    SchoolService,
    DepartmentService,
    ProgramService,
    BranchService,
    SemesterService,
)
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api/institution", tags=["institution"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _ins(session: AsyncSession) -> InstitutionService:
    return InstitutionService(InstitutionRepository(session))


def _cam(session: AsyncSession) -> CampusService:
    return CampusService(CampusRepository(session))


def _sch(session: AsyncSession) -> SchoolService:
    return SchoolService(SchoolRepository(session))


def _dep(session: AsyncSession) -> DepartmentService:
    return DepartmentService(DepartmentRepository(session))


def _prog(session: AsyncSession) -> ProgramService:
    return ProgramService(ProgramRepository(session))


def _bra(session: AsyncSession) -> BranchService:
    return BranchService(BranchRepository(session))


def _sem(session: AsyncSession) -> SemesterService:
    return SemesterService(SemesterRepository(session))


# ===================================================================
# INSTITUTION
# ===================================================================


@router.post(
    "/institutions",
    response_model=InstitutionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_institution(
    data: InstitutionCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> InstitutionResponse:
    svc = _ins(session)
    entity = await svc.create(name=data.name, code=data.code)
    return InstitutionResponse.model_validate(entity)


@router.get("/institutions/{entity_id}", response_model=InstitutionResponse)
async def get_institution(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> InstitutionResponse:
    svc = _ins(session)
    entity = await svc.get(entity_id)
    return InstitutionResponse.model_validate(entity)


@router.get("/institutions", response_model=Page[InstitutionResponse])
async def list_institutions(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[InstitutionResponse]:
    svc = _ins(session)
    items, total = await svc.list(
        status=status_filter, skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[InstitutionResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/institutions/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_institution(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _ins(session)
    await svc.delete(entity_id)


@router.patch("/institutions/{entity_id}", response_model=InstitutionResponse)
async def update_institution(
    entity_id: int,
    data: InstitutionUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> InstitutionResponse:
    svc = _ins(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code, status=data.status,
    )
    return InstitutionResponse.model_validate(entity)


# ===================================================================
# CAMPUS
# ===================================================================


@router.post("/campuses", response_model=CampusResponse, status_code=status.HTTP_201_CREATED)
async def create_campus(
    data: CampusCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> CampusResponse:
    svc = _cam(session)
    entity = await svc.create(
        institution_id=data.institution_id, name=data.name, code=data.code,
        address=data.address, phone=data.phone, email=data.email,
    )
    return CampusResponse.model_validate(entity)


@router.get("/campuses/{entity_id}", response_model=CampusResponse)
async def get_campus(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> CampusResponse:
    svc = _cam(session)
    entity = await svc.get(entity_id)
    return CampusResponse.model_validate(entity)


@router.get("/campuses", response_model=Page[CampusResponse])
async def list_campuses(
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = Query(default=None, alias="institution_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[CampusResponse]:
    svc = _cam(session)
    items, total = await svc.list(
        institution_id=institution_id, status=status_filter,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[CampusResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/campuses/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campus(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _cam(session)
    await svc.delete(entity_id)


@router.patch("/campuses/{entity_id}", response_model=CampusResponse)
async def update_campus(
    entity_id: int,
    data: CampusUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> CampusResponse:
    svc = _cam(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code, address=data.address,
        phone=data.phone, email=data.email, status=data.status,
    )
    return CampusResponse.model_validate(entity)


# ===================================================================
# SCHOOL
# ===================================================================


@router.post("/schools", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    data: SchoolCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> SchoolResponse:
    svc = _sch(session)
    entity = await svc.create(
        campus_id=data.campus_id, name=data.name, code=data.code,
        description=data.description,
    )
    return SchoolResponse.model_validate(entity)


@router.get("/schools/{entity_id}", response_model=SchoolResponse)
async def get_school(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> SchoolResponse:
    svc = _sch(session)
    entity = await svc.get(entity_id)
    return SchoolResponse.model_validate(entity)


@router.get("/schools", response_model=Page[SchoolResponse])
async def list_schools(
    pagination: PaginationParams = Depends(),
    campus_id: Optional[int] = Query(default=None, alias="campus_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[SchoolResponse]:
    svc = _sch(session)
    items, total = await svc.list(
        campus_id=campus_id, status=status_filter,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[SchoolResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/schools/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _sch(session)
    await svc.delete(entity_id)


@router.patch("/schools/{entity_id}", response_model=SchoolResponse)
async def update_school(
    entity_id: int,
    data: SchoolUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> SchoolResponse:
    svc = _sch(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        description=data.description, status=data.status,
    )
    return SchoolResponse.model_validate(entity)


# ===================================================================
# DEPARTMENT
# ===================================================================


@router.post(
    "/departments", response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    data: DepartmentCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> DepartmentResponse:
    svc = _dep(session)
    entity = await svc.create(
        school_id=data.school_id, name=data.name, code=data.code,
        description=data.description,
    )
    return DepartmentResponse.model_validate(entity)


@router.get("/departments/{entity_id}", response_model=DepartmentResponse)
async def get_department(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> DepartmentResponse:
    svc = _dep(session)
    entity = await svc.get(entity_id)
    return DepartmentResponse.model_validate(entity)


@router.get("/departments", response_model=Page[DepartmentResponse])
async def list_departments(
    pagination: PaginationParams = Depends(),
    school_id: Optional[int] = Query(default=None, alias="school_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[DepartmentResponse]:
    svc = _dep(session)
    items, total = await svc.list(
        school_id=school_id, status=status_filter,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[DepartmentResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/departments/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _dep(session)
    await svc.delete(entity_id)


@router.patch("/departments/{entity_id}", response_model=DepartmentResponse)
async def update_department(
    entity_id: int,
    data: DepartmentUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> DepartmentResponse:
    svc = _dep(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        description=data.description, status=data.status,
    )
    return DepartmentResponse.model_validate(entity)


# ===================================================================
# PROGRAM
# ===================================================================


@router.post("/programs", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    data: ProgramCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> ProgramResponse:
    svc = _prog(session)
    entity = await svc.create(
        department_id=data.department_id, name=data.name, code=data.code,
        duration_years=data.duration_years, description=data.description,
    )
    return ProgramResponse.model_validate(entity)


@router.get("/programs/{entity_id}", response_model=ProgramResponse)
async def get_program(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> ProgramResponse:
    svc = _prog(session)
    entity = await svc.get(entity_id)
    return ProgramResponse.model_validate(entity)


@router.get("/programs", response_model=Page[ProgramResponse])
async def list_programs(
    pagination: PaginationParams = Depends(),
    department_id: Optional[int] = Query(default=None, alias="department_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[ProgramResponse]:
    svc = _prog(session)
    items, total = await svc.list(
        department_id=department_id, status=status_filter,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[ProgramResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/programs/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _prog(session)
    await svc.delete(entity_id)


@router.patch("/programs/{entity_id}", response_model=ProgramResponse)
async def update_program(
    entity_id: int,
    data: ProgramUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> ProgramResponse:
    svc = _prog(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        duration_years=data.duration_years,
        description=data.description, status=data.status,
    )
    return ProgramResponse.model_validate(entity)


# ===================================================================
# BRANCH
# ===================================================================


@router.post("/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    data: BranchCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> BranchResponse:
    svc = _bra(session)
    entity = await svc.create(
        program_id=data.program_id, name=data.name, code=data.code,
        description=data.description,
    )
    return BranchResponse.model_validate(entity)


@router.get("/branches/{entity_id}", response_model=BranchResponse)
async def get_branch(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> BranchResponse:
    svc = _bra(session)
    entity = await svc.get(entity_id)
    return BranchResponse.model_validate(entity)


@router.get("/branches", response_model=Page[BranchResponse])
async def list_branches(
    pagination: PaginationParams = Depends(),
    program_id: Optional[int] = Query(default=None, alias="program_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[BranchResponse]:
    svc = _bra(session)
    items, total = await svc.list(
        program_id=program_id, status=status_filter,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[BranchResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/branches/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _bra(session)
    await svc.delete(entity_id)


@router.patch("/branches/{entity_id}", response_model=BranchResponse)
async def update_branch(
    entity_id: int,
    data: BranchUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> BranchResponse:
    svc = _bra(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        description=data.description, status=data.status,
    )
    return BranchResponse.model_validate(entity)


# ===================================================================
# SEMESTER
# ===================================================================


@router.post(
    "/semesters", response_model=SemesterResponse, status_code=status.HTTP_201_CREATED,
)
async def create_semester(
    data: SemesterCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> SemesterResponse:
    svc = _sem(session)
    entity = await svc.create(
        program_id=data.program_id, name=data.name, code=data.code,
        semester_number=data.semester_number,
        start_date=data.start_date, end_date=data.end_date,
    )
    return SemesterResponse.model_validate(entity)


@router.get("/semesters/{entity_id}", response_model=SemesterResponse)
async def get_semester(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> SemesterResponse:
    svc = _sem(session)
    entity = await svc.get(entity_id)
    return SemesterResponse.model_validate(entity)


@router.get("/semesters", response_model=Page[SemesterResponse])
async def list_semesters(
    pagination: PaginationParams = Depends(),
    program_id: Optional[int] = Query(default=None, alias="program_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> Page[SemesterResponse]:
    svc = _sem(session)
    items, total = await svc.list(
        program_id=program_id, status=status_filter,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[SemesterResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/semesters/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_semester(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    svc = _sem(session)
    await svc.delete(entity_id)


@router.patch("/semesters/{entity_id}", response_model=SemesterResponse)
async def update_semester(
    entity_id: int,
    data: SemesterUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
) -> SemesterResponse:
    svc = _sem(session)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        semester_number=data.semester_number,
        start_date=data.start_date, end_date=data.end_date,
        status=data.status,
    )
    return SemesterResponse.model_validate(entity)
