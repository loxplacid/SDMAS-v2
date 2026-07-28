from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, status

from app.domains.auth.dependencies import (
    get_current_user,
    get_user_service,
)
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.domains.auth.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.register(data)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    access_token, refresh_token, expires_in = await service.login(data)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_token: str,
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    access, new_refresh, expires_in = await service.refresh_token(
        refresh_token
    )
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = await service.update_user(current_user.id, data)
    return UserResponse.model_validate(user)


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_my_password(
    data: PasswordChange,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    await service.change_password(current_user.id, data)
    return {"detail": "Password updated"}