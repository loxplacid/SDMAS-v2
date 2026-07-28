from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.service import UserService
from app.infrastructure.database import get_session


VALID_ROLES = frozenset({"admin", "staff"})


async def get_user_service(
    session: AsyncSession = Depends(get_session),
) -> UserService:
    return UserService(UserRepository(session))


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    service: UserService = Depends(get_user_service),
) -> User:
    if authorization is None:
        raise AuthenticationError("Not authenticated")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Invalid authorization header")

    return await service.get_current_user(token)


async def get_optional_current_user(
    authorization: Optional[str] = Header(default=None),
    service: UserService = Depends(get_user_service),
) -> Optional[User]:
    if authorization is None:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        return await service.get_current_user(token)
    except AuthenticationError:
        return None


class require_role:
    def __init__(self, *roles: str) -> None:
        self.roles = roles

    async def __call__(
        self, current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in self.roles:
            raise AuthorizationError(
                f"Requires one of these roles: {', '.join(self.roles)}"
            )
        return current_user