from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import (
    get_current_user,
    get_optional_current_user,
)
from app.domains.auth.models import User
from app.domains.institution.models import Campus
from app.infrastructure.database import get_session
from app.multi_tenant.models import TenantContext


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """Extract the current tenant context from the authenticated user.

    The tenant is determined by the user's ``campus_id`` field:

    * If the user has a ``campus_id``, the campus and its parent
      institution are resolved to build a full ``TenantContext``.
    * If the user is a cross-tenant admin (``campus_id`` is ``None``),
      a context with no campus/institution is returned, meaning all
      queries run unscoped (backward-compatible mode).

    Returns:
        ``TenantContext`` with ``campus_id`` and ``institution_id``.
        Never raises — unscoped access is a valid mode for admins.
    """
    if current_user.campus_id is not None:
        campus_result = await session.execute(
            select(Campus).where(Campus.id == current_user.campus_id)
        )
        campus = campus_result.scalar_one_or_none()
        institution_id = campus.institution_id if campus else None
        return TenantContext(
            campus_id=current_user.campus_id,
            institution_id=institution_id,
        )

    return TenantContext(campus_id=None, institution_id=None)


async def get_optional_tenant(
    current_user: Optional[User] = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """Like ``get_current_tenant`` but returns an empty context when
    the user is not authenticated (for public endpoints)."""
    if current_user is None or current_user.campus_id is None:
        return TenantContext()

    campus_result = await session.execute(
        select(Campus).where(Campus.id == current_user.campus_id)
    )
    campus = campus_result.scalar_one_or_none()
    institution_id = campus.institution_id if campus else None
    return TenantContext(
        campus_id=current_user.campus_id,
        institution_id=institution_id,
    )
