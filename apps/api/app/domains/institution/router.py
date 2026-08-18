from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.institution.models import (
    Branch,
    Campus,
    Department,
    Program,
    Region,
    School,
    SchoolGroup,
    Semester,
)
from app.domains.institution.repository import (
    BranchRepository,
    CampusRepository,
    DepartmentRepository,
    InstitutionRepository,
    ProgramRepository,
    RegionRepository,
    SchoolGroupRepository,
    SchoolRepository,
    SemesterRepository,
)
from app.domains.institution.schemas import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    CampusCreate,
    CampusResponse,
    CampusUpdate,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    InstitutionCreate,
    InstitutionResponse,
    InstitutionUpdate,
    ProgramCreate,
    ProgramResponse,
    ProgramUpdate,
    RegionCreate,
    RegionResponse,
    RegionUpdate,
    SchoolCreate,
    SchoolGroupCreate,
    SchoolGroupResponse,
    SchoolGroupUpdate,
    SchoolResponse,
    SchoolUpdate,
    SemesterCreate,
    SemesterResponse,
    SemesterUpdate,
)
from app.domains.institution.service import (
    BranchService,
    CampusService,
    DepartmentService,
    InstitutionService,
    ProgramService,
    RegionService,
    SchoolGroupService,
    SchoolService,
    SemesterService,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import (
    assert_campus_in_scope,
    assert_institution_in_scope,
    assert_region_in_scope,
    assert_school_group_in_scope,
)
from app.multi_tenant.models import TenantContext, TenantScopeLevel

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
        direct = getattr(entity, "campus_id", None)
        if direct is not None:
            return int(direct)
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

    * Platform callers are unaffected.
    * Institution nodes are matched against the caller's organization
      scope (``assert_institution_in_scope``); only platform or
      organization administrators may access them.
    * School-group / region nodes use the hierarchy guards.
    * All deeper nodes are resolved to a campus and verified with
      ``assert_campus_in_scope``, so campus-scoped callers stay pinned
      to their own campus and hierarchy administrators stay inside their
      subtree.
    """
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return
    if kind == "institution":
        await assert_institution_in_scope(
            session, tenant, int(getattr(entity, "id")), resource="institution"
        )
        return
    if kind == "school_group":
        await assert_school_group_in_scope(session, tenant, entity)
        return
    if kind == "region":
        await assert_region_in_scope(session, tenant, entity)
        return
    campus_id = await _hierarchy_campus_id(session, kind, entity)
    await assert_campus_in_scope(session, tenant, campus_id, resource=kind)


async def _scoped_institution_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the institution IDs visible to the tenant.

    Organization administrators see only their own institution; other
    hierarchy scopes and campus-scoped callers are denied (they must not
    enumerate institutions).  Platform callers are unrestricted.
    """
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return []
    if tenant.scope_level == TenantScopeLevel.ORGANIZATION:
        return [tenant.institution_id]
    return []


async def _scoped_campus_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the campus IDs visible to the tenant (its whole subtree)."""
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return []
    if tenant.campus_id is not None:
        return [tenant.campus_id]
    if tenant.region_id is not None:
        result = await session.execute(
            select(Campus.id).where(Campus.region_id == tenant.region_id)
        )
        return list(result.scalars().all())
    if tenant.school_group_id is not None:
        result = await session.execute(
            select(Campus.id).where(Campus.school_group_id == tenant.school_group_id)
        )
        return list(result.scalars().all())
    if tenant.institution_id is not None:
        result = await session.execute(
            select(Campus.id).where(Campus.institution_id == tenant.institution_id)
        )
        return list(result.scalars().all())
    return []


async def _scoped_school_group_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the school-group IDs visible to the tenant."""
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return []
    if tenant.school_group_id is not None:
        return [tenant.school_group_id]
    if tenant.institution_id is not None:
        result = await session.execute(
            select(SchoolGroup.id).where(
                SchoolGroup.institution_id == tenant.institution_id
            )
        )
        return list(result.scalars().all())
    return []


async def _scoped_region_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the region IDs visible to the tenant."""
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return []
    if tenant.region_id is not None:
        return [tenant.region_id]
    if tenant.school_group_id is not None:
        result = await session.execute(
            select(Region.id).where(Region.school_group_id == tenant.school_group_id)
        )
        return list(result.scalars().all())
    if tenant.institution_id is not None:
        result = await session.execute(
            select(Region.id).where(Region.institution_id == tenant.institution_id)
        )
        return list(result.scalars().all())
    return []


async def _scoped_school_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the school IDs visible to the tenant."""
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return []
    campus_ids = await _scoped_campus_ids(session, tenant)
    if not campus_ids:
        return []
    result = await session.execute(
        select(School.id).where(School.campus_id.in_(campus_ids))
    )
    return list(result.scalars().all())


async def _scoped_department_ids(
    session: AsyncSession,
    tenant: TenantContext,
) -> list[int]:
    """Return the department IDs visible to the tenant."""
    if not tenant.is_hierarchy_scoped:
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
    if not tenant.is_hierarchy_scoped:
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
    if not tenant.is_hierarchy_scoped:
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
    if not tenant.is_hierarchy_scoped:
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


def _grp(session: AsyncSession) -> SchoolGroupService:
    return SchoolGroupService(SchoolGroupRepository(session))


def _reg(session: AsyncSession) -> RegionService:
    return RegionService(RegionRepository(session))


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
    elif tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            status=status_filter, skip=pagination.offset, limit=pagination.limit,
        )
    else:
        # Campus-scoped users and group/region administrators must never
        # enumerate legal organizations outside their own.
        raise AuthorizationError(
            "Only platform or organization administrators may list institutions"
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
# SCHOOL GROUP (enterprise hierarchy: Organization → Group → Region → Campus)
# ===================================================================


@router.post(
    "/school-groups",
    response_model=SchoolGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_school_group(
    data: SchoolGroupCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "org_admin", "group_admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SchoolGroupResponse:
    if tenant.scope_level not in (
        TenantScopeLevel.PLATFORM,
        TenantScopeLevel.ORGANIZATION,
    ):
        raise AuthorizationError(
            "Only platform or organization administrators can create school groups"
        )
    if tenant.scope_level == TenantScopeLevel.ORGANIZATION and (
        data.institution_id != tenant.institution_id
    ):
        raise AuthorizationError(
            "Cross-tenant access denied: school group belongs to another organization"
        )
    svc = _grp(session)
    entity = await svc.create(
        institution_id=data.institution_id, name=data.name, code=data.code,
        description=data.description,
    )
    return SchoolGroupResponse.model_validate(entity)


@router.get("/school-groups/{entity_id}", response_model=SchoolGroupResponse)
async def get_school_group(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SchoolGroupResponse:
    svc = _grp(session)
    entity = await svc.get(entity_id)
    await assert_school_group_in_scope(session, tenant, entity)
    return SchoolGroupResponse.model_validate(entity)


@router.get("/school-groups", response_model=Page[SchoolGroupResponse])
async def list_school_groups(
    pagination: PaginationParams = Depends(),
    institution_id: Optional[int] = Query(default=None, alias="institution_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[SchoolGroupResponse]:
    svc = _grp(session)
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            institution_id=institution_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    else:
        group_ids = await _scoped_school_group_ids(session, tenant)
        if (
            institution_id is not None
            and tenant.scope_level == TenantScopeLevel.ORGANIZATION
            and institution_id != tenant.institution_id
        ):
            raise AuthorizationError(
                "Cross-tenant access denied to school-group listing"
            )
        items, total = await svc.list(
            ids=group_ids, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    return Page.create(
        items=[SchoolGroupResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/school-groups/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_school_group(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "org_admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _grp(session)
    entity = await svc.get(entity_id)
    await assert_school_group_in_scope(session, tenant, entity)
    if tenant.scope_level not in (
        TenantScopeLevel.PLATFORM,
        TenantScopeLevel.ORGANIZATION,
    ):
        raise AuthorizationError(
            "Only platform or organization administrators can delete school groups"
        )
    await svc.delete(entity_id)


@router.patch("/school-groups/{entity_id}", response_model=SchoolGroupResponse)
async def update_school_group(
    entity_id: int,
    data: SchoolGroupUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "org_admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SchoolGroupResponse:
    svc = _grp(session)
    existing = await svc.get(entity_id)
    await assert_school_group_in_scope(session, tenant, existing)
    if tenant.scope_level not in (
        TenantScopeLevel.PLATFORM,
        TenantScopeLevel.ORGANIZATION,
    ):
        raise AuthorizationError(
            "Only platform or organization administrators can update school groups"
        )
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        description=data.description, status=data.status,
    )
    return SchoolGroupResponse.model_validate(entity)


# ===================================================================
# REGION (enterprise hierarchy)
# ===================================================================


@router.post(
    "/regions",
    response_model=RegionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_region(
    data: RegionCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "org_admin", "group_admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RegionResponse:
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        pass
    elif tenant.scope_level == TenantScopeLevel.ORGANIZATION:
        if data.institution_id != tenant.institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied: region belongs to another organization"
            )
    elif tenant.scope_level == TenantScopeLevel.GROUP:
        if data.institution_id != tenant.institution_id or (
            data.school_group_id is not None
            and data.school_group_id != tenant.school_group_id
        ):
            raise AuthorizationError(
                "Cross-tenant access denied: region belongs to another school group"
            )
    else:
        raise AuthorizationError(
            "Only platform, organization or group administrators can create regions"
        )
    svc = _reg(session)
    entity = await svc.create(
        institution_id=data.institution_id,
        school_group_id=data.school_group_id,
        name=data.name, code=data.code, description=data.description,
    )
    return RegionResponse.model_validate(entity)


@router.get("/regions/{entity_id}", response_model=RegionResponse)
async def get_region(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RegionResponse:
    svc = _reg(session)
    entity = await svc.get(entity_id)
    await assert_region_in_scope(session, tenant, entity)
    return RegionResponse.model_validate(entity)


@router.get("/regions", response_model=Page[RegionResponse])
async def list_regions(
    pagination: PaginationParams = Depends(),
    school_group_id: Optional[int] = Query(default=None, alias="school_group_id"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(require_tenant_context),
) -> Page[RegionResponse]:
    svc = _reg(session)
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            school_group_id=school_group_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    else:
        region_ids = await _scoped_region_ids(session, tenant)
        if (
            school_group_id is not None
            and tenant.scope_level == TenantScopeLevel.GROUP
            and school_group_id != tenant.school_group_id
        ):
            raise AuthorizationError(
                "Cross-tenant access denied to region listing"
            )
        items, total = await svc.list(
            ids=region_ids, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    return Page.create(
        items=[RegionResponse.model_validate(i) for i in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.delete("/regions/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(
    entity_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "org_admin", "group_admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    svc = _reg(session)
    entity = await svc.get(entity_id)
    await assert_region_in_scope(session, tenant, entity)
    if tenant.scope_level not in (
        TenantScopeLevel.PLATFORM,
        TenantScopeLevel.ORGANIZATION,
        TenantScopeLevel.GROUP,
    ):
        raise AuthorizationError(
            "Only platform, organization or group administrators can delete regions"
        )
    await svc.delete(entity_id)


@router.patch("/regions/{entity_id}", response_model=RegionResponse)
async def update_region(
    entity_id: int,
    data: RegionUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_role("admin", "org_admin", "group_admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RegionResponse:
    svc = _reg(session)
    existing = await svc.get(entity_id)
    await assert_region_in_scope(session, tenant, existing)
    if tenant.scope_level not in (
        TenantScopeLevel.PLATFORM,
        TenantScopeLevel.ORGANIZATION,
        TenantScopeLevel.GROUP,
    ):
        raise AuthorizationError(
            "Only platform, organization or group administrators can update regions"
        )
    entity = await svc.update(
        entity_id, name=data.name, code=data.code,
        description=data.description, status=data.status,
    )
    return RegionResponse.model_validate(entity)


async def _assert_campus_parent_scope(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    institution_id: int,
    school_group_id: Optional[int] = None,
    region_id: Optional[int] = None,
) -> None:
    """Validate that a campus's organization links (institution, school
    group, region) lie inside the caller's hierarchy subtree.

    Raises ``AuthorizationError`` when any link is outside the caller's
    scope, and validates region ↔ group ↔ institution consistency so a
    campus cannot be attached to a region/group of a different
    organization.
    """
    level = tenant.scope_level
    if level == TenantScopeLevel.PLATFORM:
        return
    if level == TenantScopeLevel.CAMPUS:
        if institution_id != tenant.institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied: campus belongs to another institution"
            )
        return
    if level == TenantScopeLevel.ORGANIZATION:
        if institution_id != tenant.institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied: campus belongs to another organization"
            )
    elif level == TenantScopeLevel.GROUP:
        if institution_id != tenant.institution_id or (
            school_group_id is not None
            and school_group_id != tenant.school_group_id
        ):
            raise AuthorizationError(
                "Cross-tenant access denied: campus belongs to another school group"
            )
    elif level == TenantScopeLevel.REGION:
        if region_id is not None and region_id != tenant.region_id:
            raise AuthorizationError(
                "Cross-tenant access denied: campus belongs to another region"
            )
        if institution_id != tenant.institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied: campus belongs to another institution"
            )
    else:
        raise AuthorizationError(
            "Only platform or hierarchy administrators can manage campuses"
        )

    if region_id is not None:
        region = await RegionRepository(session).get_by_id(region_id)
        if region is None or region.institution_id != institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied: region does not belong to the "
                "campus's institution"
            )
        if school_group_id is not None and region.school_group_id not in (None, school_group_id):
            raise AuthorizationError(
                "Cross-tenant access denied: region does not belong to the "
                "campus's school group"
            )
    if school_group_id is not None:
        group = await SchoolGroupRepository(session).get_by_id(school_group_id)
        if group is None or group.institution_id != institution_id:
            raise AuthorizationError(
                "Cross-tenant access denied: school group does not belong to "
                "the campus's institution"
            )


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
    await _assert_campus_parent_scope(
        session, tenant,
        institution_id=data.institution_id,
        school_group_id=data.school_group_id,
        region_id=data.region_id,
    )
    svc = _cam(session)
    entity = await svc.create(
        institution_id=data.institution_id, name=data.name, code=data.code,
        address=data.address, phone=data.phone, email=data.email,
        school_group_id=data.school_group_id, region_id=data.region_id,
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
    svc = _cam(session)
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            institution_id=institution_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    else:
        campus_ids = await _scoped_campus_ids(session, tenant)
        items, total = await svc.list(
            ids=campus_ids, status=status_filter,
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
    if data.school_group_id is not None or data.region_id is not None:
        await _assert_campus_parent_scope(
            session, tenant,
            institution_id=existing.institution_id,
            school_group_id=data.school_group_id or existing.school_group_id,
            region_id=data.region_id or existing.region_id,
        )
    entity = await svc.update(
        entity_id, name=data.name, code=data.code, address=data.address,
        phone=data.phone, email=data.email, status=data.status,
        school_group_id=data.school_group_id, region_id=data.region_id,
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
    if tenant.scope_level != TenantScopeLevel.PLATFORM:
        await assert_campus_in_scope(session, tenant, data.campus_id, resource="school")
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
    svc = _sch(session)
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            campus_id=campus_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    else:
        campus_ids = await _scoped_campus_ids(session, tenant)
        if campus_id is not None and campus_id not in campus_ids:
            raise AuthorizationError(
                "Cross-tenant access denied to school listing"
            )
        if campus_id is not None:
            items, total = await svc.list(
                campus_id=campus_id, status=status_filter,
                skip=pagination.offset, limit=pagination.limit,
            )
        else:
            school_ids = await _scoped_school_ids(session, tenant)
            items, total = await svc.list(
                ids=school_ids, status=status_filter,
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
    campus_id: Optional[int] = None
    if tenant.scope_level != TenantScopeLevel.PLATFORM:
        school = await SchoolRepository(session).get_by_id(data.school_id)
        await _assert_hierarchy_scope(session, tenant, "school", school)
        campus_id = school.campus_id if school else None
    svc = _dep(session)
    entity = await svc.create(
        school_id=data.school_id, name=data.name, code=data.code,
        description=data.description, campus_id=campus_id,
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
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            school_id=school_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    elif tenant.is_hierarchy_scoped:
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
        raise AuthorizationError(
            "No tenant context — cross-tenant access denied to department listing"
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
    if tenant.scope_level != TenantScopeLevel.PLATFORM:
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
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            department_id=department_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    elif tenant.is_hierarchy_scoped:
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
        raise AuthorizationError(
            "No tenant context — cross-tenant access denied to program listing"
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
    if tenant.scope_level != TenantScopeLevel.PLATFORM:
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
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            program_id=program_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    elif tenant.is_hierarchy_scoped:
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
        raise AuthorizationError(
            "No tenant context — cross-tenant access denied to branch listing"
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
    if tenant.scope_level != TenantScopeLevel.PLATFORM:
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
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        items, total = await svc.list(
            program_id=program_id, status=status_filter,
            skip=pagination.offset, limit=pagination.limit,
        )
    elif tenant.is_hierarchy_scoped:
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
        raise AuthorizationError(
            "No tenant context — cross-tenant access denied to semester listing"
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
