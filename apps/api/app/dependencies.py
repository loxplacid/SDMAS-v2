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


# ---------------------------------------------------------------------------
# Multi-tenancy — deprecated stub replaced by app.multi_tenant.dependencies
# ---------------------------------------------------------------------------


async def get_school_context():
    """DEPRECATED — Use ``app.multi_tenant.dependencies.get_current_tenant``
    instead.

    This stub exists only to preserve backward compatibility until all
    callers have been migrated to the new dependency.

    See ``app/multi_tenant/`` for the current implementation.
    """
    from app.multi_tenant.dependencies import get_current_tenant as _new
    from app.domains.auth.dependencies import get_current_user as _get_user
    from app.infrastructure.database import get_session as _get_db

    # Approximate the new dependency pipeline — requires the caller
    # to provide user + session via override, which they already do.
    raise NotImplementedError(
        "get_school_context is deprecated. Use "
        "app.multi_tenant.dependencies.get_current_tenant instead."
    )