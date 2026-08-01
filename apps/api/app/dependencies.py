from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.exceptions import AuthenticationError
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.service import UserService
from app.infrastructure.database import async_session_factory
from app.multi_tenant.models import TenantContext


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
# Multi-tenancy — canonical implementation lives in app.multi_tenant.dependencies
# ---------------------------------------------------------------------------


async def get_school_context(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    """Backward-compatible alias for ``app.multi_tenant.dependencies.get_school_context``.

    Kept so that legacy imports of ``app.dependencies.get_school_context``
    continue to resolve to the secure, membership-validated
    implementation. New code should import from ``app.multi_tenant.dependencies``.
    """
    from app.multi_tenant.dependencies import resolve_tenant_context

    return await resolve_tenant_context(session, current_user, require_school=True)