from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.service import UserService
from app.domains.auth.permission_service import PermissionService
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
    """FastAPI dependency: require the user to have one of the given roles.

    Checks across ALL of the user's roles (primary ``role`` field +
    ``assigned_roles`` M2M relationship).  A user with role "teacher"
    who is also assigned "staff" via the M2M table will pass a
    ``require_role("staff")`` check.

    Example::

        @router.get("/students")
        async def list_students(
            _user: User = Depends(require_role("admin", "staff")),
        ):
            ...
    """

    def __init__(self, *roles: str) -> None:
        self.roles = roles

    async def __call__(
        self, current_user: User = Depends(get_current_user)
    ) -> User:
        user_role_codes = current_user.role_codes
        for required in self.roles:
            if required in user_role_codes:
                return current_user
        raise AuthorizationError(
            f"Requires one of these roles: {', '.join(self.roles)}. "
            f"User has: {', '.join(user_role_codes)}"
        )


class require_permission:
    """FastAPI dependency: require the user's role to have a specific
    permission.

    Checks both the database role-permission mapping (via
    ``PermissionService``) and the in-memory registry as a fallback.

    Example::

        @router.delete("/students/{id}")
        async def delete_student(
            _user: User = Depends(require_permission("students.delete")),  # noqa
        ):
            ...

    Note: The dependency ordering means the user is resolved first via
    ``get_current_user``, then permission is checked.  The session is
    injected separately for the DB-backed permission lookup.
    """

    def __init__(self, *permissions: str) -> None:
        self.permissions = permissions

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        svc = PermissionService(session)
        role_codes = current_user.role_codes
        for perm in self.permissions:
            allowed = await svc.any_role_has_permission(role_codes, perm)
            if not allowed:
                raise AuthorizationError(
                    f"Missing required permission: '{perm}'. "
                    f"None of your roles ({', '.join(role_codes)}) "
                    f"grant this permission."
                )
        return current_user