from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, get_user_service, require_role
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    AdminUserUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.domains.auth.service import UserService
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/admin/users", tags=["admin"])


async def _admin_user(
    service: UserService = Depends(get_user_service),
    _admin: User = Depends(require_role("admin")),
    tenant: TenantContext = Depends(require_tenant_context),
) -> tuple[UserService, TenantContext]:
    """Admin user-management gate: ``admin`` role + an explicit tenant
    context. User records are tenant-owned, so every handler below is
    pinned to the acting admin's campus (default-deny for cross-tenant
    user access)."""
    return service, tenant


@router.get("", response_model=Page[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    role: Optional[str] = Query(default=None, description="Filter by role"),
    is_active: Optional[bool] = Query(default=None, alias="is_active", description="Filter by active status"),
    _admin_ctx: tuple[UserService, TenantContext] = Depends(_admin_user),
) -> Page[UserResponse]:
    service, tenant = _admin_ctx
    effective_campus = effective_campus_id(tenant, None)
    items, total = await service.list_users(
        role=role, is_active=is_active, campus_id=effective_campus,
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    _admin_ctx: tuple[UserService, TenantContext] = Depends(_admin_user),
) -> UserResponse:
    service, tenant = _admin_ctx
    user = await service.get_user(user_id)
    assert_tenant_scope(user, tenant, resource="user")
    return UserResponse.model_validate(user)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    data: UserCreate,
    _admin_ctx: tuple[UserService, TenantContext] = Depends(_admin_user),
) -> UserResponse:
    service, tenant = _admin_ctx
    # New users are pinned to the acting admin's campus so a tenant
    # admin can never create (and thereby leak) a cross-tenant account.
    campus_id = tenant.campus_id if tenant.is_tenant_scoped else None
    user = await service.register(data, campus_id=campus_id)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    _admin_ctx: tuple[UserService, TenantContext] = Depends(_admin_user),
) -> UserResponse:
    service, tenant = _admin_ctx
    user = await service.get_user(user_id)
    assert_tenant_scope(user, tenant, resource="user")
    updated = await service.admin_update_user(user_id, data)
    return UserResponse.model_validate(updated)


@router.post("/{user_id}/roles", response_model=UserResponse)
async def set_user_roles(
    user_id: int,
    role_codes: list[str],
    _admin_ctx: tuple[UserService, TenantContext] = Depends(_admin_user),
) -> UserResponse:
    """Replace all M2M role assignments for a user.

    The user's ``role`` field (primary role) is *not* changed by this
    endpoint.  To change the primary role, use PATCH ``/admin/users/{id}``
    with ``{"role": "..."}``.
    """
    service, tenant = _admin_ctx
    user = await service.get_user(user_id)
    assert_tenant_scope(user, tenant, resource="user")
    updated = await service.set_user_roles(user_id, role_codes)
    return UserResponse.model_validate(updated)