from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.exceptions import AuthenticationError
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.service import UserService
from app.infrastructure.database import async_session_factory


def get_settings() -> Settings:
    return settings


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> User:
    if authorization is None:
        raise AuthenticationError("Not authenticated")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Invalid authorization header")

    async with async_session_factory() as session:
        service = UserService(UserRepository(session))
        return await service.get_current_user(token)


async def get_school_context():
    """Multi-tenancy / school context.

    DEFERRED — The legacy implementation (SDMAS v1) does not include
    multi-tenant support. All data is school-scoped implicitly through
    enrollment relationships rather than an explicit tenant identifier.

    When multi-tenancy is required in a future phase, this dependency
    should:
      1. Extract the school/tenant ID from the authenticated user's
         token or a separate header.
      2. Inject the school context into every domain service/repository
         to scope all queries.
      3. Require a schema-level migration (school_id column on every
         domain table) and a tenant registry.

    This placeholder raises NotImplementedError to make any accidental
    use fail at runtime rather than silently producing unscoped results.
    """
    raise NotImplementedError(
        "get_school_context is not implemented — multi-tenancy has been "
        "deferred. See the docstring for details."
    )