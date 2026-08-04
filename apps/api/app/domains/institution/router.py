from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
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
from app.domains.institution.models import (
    Branch,
    Campus,
    Department,
    Institution,
    Program,
    School,
    Semester,
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
from app.core.exceptions import AuthorizationError
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/institution", tags=["institution"])


# ---------------------------------------------------------------------------
# Tenant scope resolution for the institution hierarchy
# ---------------------------------------------------------------------------
# The hierarchy (Institution → Campus → School → Department → Program →
# Branch/Semester) is the tenant-defining structure itself. Tenant-scoped
# users must never read or mutate nodes outside their own subtree.


async def _hierarchy_campus_id(
    session: AsyncSession,
    kind: str,
    entity: Any,
) -> Optional[int]:
    """Resolve the campus a hierarchy node belongs to (for scoping)."""
    if kind == "campus":
        return int(getattr(entity, "id"))
    if kind == "school":
        return getattr(entity, "campus_id", None)
    if kind == "department":
        school = await SchoolRepository(session).get_by_id(entity.school_id)
        return school.campus_id if school else None
    if kind == "program":
        dep = await DepartmentRepository(session).get_by_id(entity.department_id)
        if dep is None:
            return None
        school = await SchoolRepository(session).get_by_id(dep.school_id)
        return school.campus_id if school else None
    if kind in ("branch", "semester"):
        prog = await ProgramRepository(session).get_by_id(entity.program_id)
        if prog is None:
            return None
        dep = await DepartmentRepository(session).get_by_id(prog.department_id)
        if dep is None:
            return None
        school = await SchoolRepository(session).get_by_id(dep.school_id)
        return school.campus_id if school else None
    return None


async def _assert_hierarchy_scope(
    session: AsyncSession,
    tenant: TenantContext,
    kind: str,
    entity: Any,
) -> None:
    """Raise 403 when a hierarchy node lies outside the tenant's subtree.

    Institution nodes are matched against ``tenant.institution_id``; all
    deeper nodes are resolved to a campus and matched against
    ``tenant.campus_id``. Unscoped (platform) callers are unaffected.
    """
    if not tenant.is_tenant_scoped:
        return
    if kind == "institution":
        if getattr(entity, "id") != tenant.institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied to institution: "
                f"entity belongs to institution {getattr(entity, 'id')}, "
                f"current tenant is institution {tenant.institution_id}."
            )
        return
    campus_id = await _hierarchy_campus_id(session, kind, entity)
    if campus_id != tenant.campus_id:
        raise AuthorizationError(
            f"Cross-tenant access denied to {kind}: "
            f"entity belongs to campus {campus_id}, "
            f"current tenant is campus {tenant.campus_id}."
        )


async def _scoped_institution_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the institution IDs visible to the tenant (own institution)."""
    if not tenant.is_tenant_scoped or tenant.institution_id is None:
        return []
    return [tenant.institution_id]


async def _scoped_campus_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the campus IDs visible to the tenant."""
    if not tenant.is_tenant_scoped:
        return []
    result = await session.execute(
        select(Campus.id).where(Campus.institution_id == tenant.institution_id)
    )
    return list(result.scalars().all())


async def _scoped_school_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the school IDs visible to the tenant."""
    if not tenant.is_tenant_scoped:
        return []
    result = await session.execute(
        select(School.id).where(School.campus_id == tenant.campus_id)
    )
    return list(result.scalars().all())


async def _scoped_department_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the department IDs visible to the tenant."""
    if not tenant.is_tenant_scoped:
        return []
    school_ids = await _scoped_school_ids(session, tenant)
    if not school_ids:
        return []
    result = await session.execute(
        select(Department.id).where(Department.school_id.in_(school_ids))
    )
    return list(result.scalars().all())


async def _scoped_program_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the program IDs visible to the tenant."""
    if not tenant.is_tenant_scoped:
        return []
    dept_ids = await _scoped_department_ids(session, tenant)
    if not dept_ids:
        return []
    result = await session.execute(
        select(Program.id).where(Program.department_id.in_(dept_ids))
    )
    return list(result.scalars().all())


async def _scoped_branch_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the branch IDs visible to the tenant."""
    if not tenant.is_tenant_scoped:
        return []
    program_ids = await _scoped_program_ids(session, tenant)
    if not program_ids:
        return []
    result = await session.execute(
        select(Branch.id).where(Branch.program_id.in_(program_ids))
    )
    return list(result.scalars().all())


async def _scoped_semester_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the semester IDs visible to the tenant."""
    if not tenant.is_tenant_scoped:
        return []
    program_ids = await _scoped_program_ids(session, tenant)
    if not program_ids:
        return []
    result = await session.execute(
        select(Semester.id).where(Semester.program_id.in_(program_ids))
    )
    return list(result.scalars().all())


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
    tenant: TenantContext = Depends(require_tenant_context),
) -> InstitutionResponse:
    if tenant.is_tenant_scoped:
        # A school-scoped admin must not create institutions at platform level.
        raise AuthorizationError(
            "Only platform admins can create institutions"
        )
    svc = _ins(session)
    entity = await svc.create(name=data.name, code=data.code)
    return InstitutionResponse.model_validate(entity)


@router.get("/institutions/{entity_id}", response_model=InstitutionResponse)
async def get_institution(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> InstitutionResponse:
    svc = _ins(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "institution", entity)
    return InstitutionResponse.model_validate(entity)


@router.get("/institutions", response_model=Page[InstitutionResponse])
async def list_institutions(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[InstitutionResponse]:
    svc = _ins(session)
    institution_ids = await _scoped_institution_ids(session, tenant)
    if institution_ids:
        items, total = await svc.list(
            status=status_filter, ids=institution_ids,
            skip=pagination.offset, limit=pagination.limit,
        )
    else:
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    if tenant.is_tenant_scoped:
        raise AuthorizationError(
            "Only platform admins can delete institutions"
        )
    svc = _ins(session)
    await svc.delete(entity_id)


@router.patch("/institutions/{entity_id}", response_model=InstitutionResponse)
async def update_institution(
    entity_id: int,
    data: InstitutionUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> InstitutionResponse:
    if tenant.is_tenant_scoped:
        raise AuthorizationError(
            "Only platform admins can update institutions"
        )
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> CampusResponse:
    if tenant.is_tenant_scoped and data.institution_id != tenant.institution_id:
        raise AuthorizationError(
            "Cross-tenant access denied: campus belongs to another institution"
        )
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> CampusResponse:
    svc = _cam(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "campus", entity)
    return CampusResponse.model_validate(entity)


@router.get("/campuses", response_model=Page[CampusResponse])
async def list_campuses(
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = Query(default=None, alias="institution_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[CampusResponse]:
    effective_institution_id = (
        tenant.institution_id if tenant.is_tenant_scoped else institution_id
    )
    svc = _cam(session)
    items, total = await svc.list(
        institution_id=effective_institution_id, status=status_filter,
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _cam(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "campus", entity)
    await svc.delete(entity_id)


@router.patch("/campuses/{entity_id}", response_model=CampusResponse)
async def update_campus(
    entity_id: int,
    data: CampusUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CampusResponse:
    svc = _cam(session)
    existing = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "campus", existing)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> SchoolResponse:
    if tenant.is_tenant_scoped and data.campus_id != tenant.campus_id:
        raise AuthorizationError(
            "Cross-tenant access denied: school belongs to another campus"
        )
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> SchoolResponse:
    svc = _sch(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "school", entity)
    return SchoolResponse.model_validate(entity)


@router.get("/schools", response_model=Page[SchoolResponse])
async def list_schools(
    pagination: PaginationParams = Depends(),
    campus_id: Optional[int] = Query(default=None, alias="campus_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[SchoolResponse]:
    effective_campus_id = tenant.campus_id if tenant.is_tenant_scoped else campus_id
    svc = _sch(session)
    items, total = await svc.list(
        campus_id=effective_campus_id, status=status_filter,
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _sch(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "school", entity)
    await svc.delete(entity_id)


@router.patch("/schools/{entity_id}", response_model=SchoolResponse)
async def update_school(
    entity_id: int,
    data: SchoolUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SchoolResponse:
    svc = _sch(session)
    existing = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "school", existing)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> DepartmentResponse:
    if tenant.is_tenant_scoped:
        school = await SchoolRepository(session).get_by_id(data.school_id)
        await _assert_hierarchy_scope(session, tenant, "school", school)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> DepartmentResponse:
    svc = _dep(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "department", entity)
    return DepartmentResponse.model_validate(entity)


@router.get("/departments", response_model=Page[DepartmentResponse])
async def list_departments(
    pagination: PaginationParams = Depends(),
    school_id: Optional[int] = Query(default=None, alias="school_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[DepartmentResponse]:
    svc = _dep(session)
    if tenant.is_tenant_scoped:
        allowed_schools = await _scoped_school_ids(session, tenant)
        if school_id is not None and school_id not in allowed_schools:
            raise AuthorizationError(
                "Cross-tenant access denied to department listing"
            )
        if school_id is not None:
            items, total = await svc.list(
                school_id=school_id, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
        else:
            dept_ids = await _scoped_department_ids(session, tenant)
            items, total = await svc.list(
                ids=dept_ids, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
    else:
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _dep(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "department", entity)
    await svc.delete(entity_id)


@router.patch("/departments/{entity_id}", response_model=DepartmentResponse)
async def update_department(
    entity_id: int,
    data: DepartmentUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> DepartmentResponse:
    svc = _dep(session)
    existing = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "department", existing)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> ProgramResponse:
    if tenant.is_tenant_scoped:
        department = await DepartmentRepository(session).get_by_id(data.department_id)
        await _assert_hierarchy_scope(session, tenant, "department", department)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> ProgramResponse:
    svc = _prog(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "program", entity)
    return ProgramResponse.model_validate(entity)


@router.get("/programs", response_model=Page[ProgramResponse])
async def list_programs(
    pagination: PaginationParams = Depends(),
    department_id: Optional[int] = Query(default=None, alias="department_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[ProgramResponse]:
    svc = _prog(session)
    if tenant.is_tenant_scoped:
        allowed_departments = await _scoped_department_ids(session, tenant)
        if department_id is not None and department_id not in allowed_departments:
            raise AuthorizationError(
                "Cross-tenant access denied to program listing"
            )
        if department_id is not None:
            items, total = await svc.list(
                department_id=department_id, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
        else:
            prog_ids = await _scoped_program_ids(session, tenant)
            items, total = await svc.list(
                ids=prog_ids, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
    else:
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _prog(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "program", entity)
    await svc.delete(entity_id)


@router.patch("/programs/{entity_id}", response_model=ProgramResponse)
async def update_program(
    entity_id: int,
    data: ProgramUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ProgramResponse:
    svc = _prog(session)
    existing = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "program", existing)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> BranchResponse:
    if tenant.is_tenant_scoped:
        program = await ProgramRepository(session).get_by_id(data.program_id)
        await _assert_hierarchy_scope(session, tenant, "program", program)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> BranchResponse:
    svc = _bra(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "branch", entity)
    return BranchResponse.model_validate(entity)


@router.get("/branches", response_model=Page[BranchResponse])
async def list_branches(
    pagination: PaginationParams = Depends(),
    program_id: Optional[int] = Query(default=None, alias="program_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[BranchResponse]:
    svc = _bra(session)
    if tenant.is_tenant_scoped:
        allowed_programs = await _scoped_program_ids(session, tenant)
        if program_id is not None and program_id not in allowed_programs:
            raise AuthorizationError(
                "Cross-tenant access denied to branch listing"
            )
        if program_id is not None:
            items, total = await svc.list(
                program_id=program_id, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
        else:
            branch_ids = await _scoped_branch_ids(session, tenant)
            items, total = await svc.list(
                ids=branch_ids, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
    else:
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _bra(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "branch", entity)
    await svc.delete(entity_id)


@router.patch("/branches/{entity_id}", response_model=BranchResponse)
async def update_branch(
    entity_id: int,
    data: BranchUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> BranchResponse:
    svc = _bra(session)
    existing = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "branch", existing)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> SemesterResponse:
    if tenant.is_tenant_scoped:
        program = await ProgramRepository(session).get_by_id(data.program_id)
        await _assert_hierarchy_scope(session, tenant, "program", program)
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> SemesterResponse:
    svc = _sem(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "semester", entity)
    return SemesterResponse.model_validate(entity)


@router.get("/semesters", response_model=Page[SemesterResponse])
async def list_semesters(
    pagination: PaginationParams = Depends(),
    program_id: Optional[int] = Query(default=None, alias="program_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[SemesterResponse]:
    svc = _sem(session)
    if tenant.is_tenant_scoped:
        allowed_programs = await _scoped_program_ids(session, tenant)
        if program_id is not None and program_id not in allowed_programs:
            raise AuthorizationError(
                "Cross-tenant access denied to semester listing"
            )
        if program_id is not None:
            items, total = await svc.list(
                program_id=program_id, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
        else:
            semester_ids = await _scoped_semester_ids(session, tenant)
            items, total = await svc.list(
                ids=semester_ids, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
    else:
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
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _sem(session)
    entity = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "semester", entity)
    await svc.delete(entity_id)


@router.patch("/semesters/{entity_id}", response_model=SemesterResponse)
async def update_semester(
    entity_id: int,
    data: SemesterUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SemesterResponse:
    svc = _sem(session)
    existing = await svc.get(entity_id)
    await _assert_hierarchy_scope(session, tenant, "semester", existing)
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        semester_number=data.semester_number,
        start_date=data.start_date, end_date=data.end_date,
        status=data.status,
    )
    return SemesterResponse.model_validate(entity)
