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

router = APIRouter(prefix="/admin/users", tags=["admin"])


async def _admin_user(
    service: UserService = Depends(get_user_service),
    _admin: User = Depends(require_role("admin")),
) -> UserService:
    return service


@router.get("", response_model=Page[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    role: Optional[str] = Query(default=None, description="Filter by role"),
    is_active: Optional[bool] = Query(default=None, alias="is_active", description="Filter by active status"),
    service: UserService = Depends(_admin_user),
) -> Page[UserResponse]:
    items, total = await service.list_users(
        role=role, is_active=is_active, skip=pagination.offset, limit=pagination.limit,
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
    service: UserService = Depends(_admin_user),
) -> UserResponse:
    user = await service.get_user(user_id)
    return UserResponse.model_validate(user)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    data: UserCreate,
    service: UserService = Depends(_admin_user),
) -> UserResponse:
    user = await service.register(data)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    service: UserService = Depends(_admin_user),
) -> UserResponse:
    user = await service.admin_update_user(user_id, data)
    return UserResponse.model_validate(user)