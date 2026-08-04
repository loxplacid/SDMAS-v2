from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.domains.auth.dependencies import (
    get_current_user,
    get_optional_current_user,
)
from app.domains.auth.models import User, UserSchoolMembership
from app.domains.auth.permissions import PLATFORM_ACCESS
from app.domains.institution.models import Campus
from app.infrastructure.database import get_session
from app.multi_tenant.models import TenantContext


# ---------------------------------------------------------------------------
# Membership resolution helpers
# ---------------------------------------------------------------------------


async def _load_memberships(
    session: AsyncSession,
    user_id: int,
) -> list[UserSchoolMembership]:
    result = await session.execute(
        select(UserSchoolMembership).where(
            UserSchoolMembership.user_id == user_id,
            UserSchoolMembership.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def _campus_institution_id(
    session: AsyncSession,
    campus_id: int,
) -> int | None:
    campus = await session.get(Campus, campus_id)
    return campus.institution_id if campus else None


async def _has_platform_access(
    session: AsyncSession,
    user: User,
) -> bool:
    """True when the user holds an explicit platform permission.

    Platform access is the ONLY way an unscoped (campus-less) user may
    operate — "unscoped" alone must never imply full access.
    """
    from app.domains.auth.permission_service import PermissionService

    svc = PermissionService(session)
    return await svc.any_role_has_permission(user.role_codes, PLATFORM_ACCESS)


async def resolve_tenant_context(
    session: AsyncSession,
    current_user: Optional[User],
    *,
    require_school: bool = False,
) -> TenantContext:
    """Resolve the tenant context for a user from their *active* school
    membership.

    Resolution order:

    1. If the user holds school membership rows, the active campus is
       ``user.campus_id`` — but only when it is one of the user's active
       memberships; otherwise ``AuthorizationError`` (403) is raised.
    2. If the user has memberships but ``campus_id`` is ``None``, the
       default membership is used (and persisted back to the user row so
       the JWT claim stays consistent).
    3. If the user has no memberships (legacy / platform admin), the
       legacy ``campus_id`` column is honoured for backward
       compatibility; ``require_school`` turns this into a 403.

    Never returns a context whose campus the user is not a member of —
    this is the server-side enforcement that prevents cross-tenant reads.
    """
    if current_user is None:
        return TenantContext(user_id=None)

    memberships = await _load_memberships(session, current_user.id)

    if memberships:
        active_campus_id = current_user.campus_id
        if active_campus_id is None:
            default = next(
                (m for m in memberships if m.is_default),
                memberships[0],
            )
            active_campus_id = default.campus_id
            # Keep the JWT claim and the membership in sync.
            if current_user.campus_id != active_campus_id:
                current_user.campus_id = active_campus_id
                await session.flush()
        elif not any(m.campus_id == active_campus_id for m in memberships):
            raise AuthorizationError(
                "Your active school is not part of your memberships. "
                "Use POST /auth/schools/switch to select a school you belong to."
            )

        institution_id = await _campus_institution_id(session, active_campus_id)
        if institution_id is None:
            raise AuthorizationError(
                f"Active campus {active_campus_id} no longer exists"
            )
        return TenantContext(
            campus_id=active_campus_id,
            institution_id=institution_id,
            user_id=current_user.id,
        )

    # Legacy mode: honour the legacy column (concrete campus).
    if current_user.campus_id is not None:
        institution_id = await _campus_institution_id(session, current_user.campus_id)
        if require_school and institution_id is None:
            raise AuthorizationError("No active school context for this user")
        return TenantContext(
            campus_id=current_user.campus_id,
            institution_id=institution_id,
            user_id=current_user.id,
        )

    # No campus at all.  Default-deny: only an explicit platform
    # permission converts this into cross-tenant access.  A plain
    # authenticated user without any tenant membership is denied.
    if await _has_platform_access(session, current_user):
        return TenantContext(user_id=current_user.id, platform=True)

    if require_school:
        raise AuthorizationError(
            "No active school context for this user — "
            "an authenticated user without tenant membership is denied."
        )
    return TenantContext(user_id=current_user.id)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """Return the current tenant context for the authenticated user.

    Backward-compatible: users without memberships (platform admins)
    resolve to an unscoped context exactly as before.
    """
    return await resolve_tenant_context(session, current_user)


async def get_optional_tenant(
    current_user: Optional[User] = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """Like ``get_current_tenant`` but returns an empty context when the
    user is not authenticated (for public endpoints)."""
    return await resolve_tenant_context(session, current_user)


async def get_school_context(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """Return a *school-scoped* tenant context for the authenticated user.

    Raises ``AuthorizationError`` (403) when the user has no active
    school — used by endpoints that must not operate without a concrete
    school context.
    """
    return await resolve_tenant_context(session, current_user, require_school=True)


async def require_active_school(
    tenant: TenantContext = Depends(get_school_context),
) -> TenantContext:
    """Dependency alias for endpoints that require a concrete school.

    Equivalent to ``get_school_context`` — provided as a descriptive
    name for routers.
    """
    return tenant


async def require_tenant_context(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """Canonical dependency for tenant-scoped (C-class) endpoints.

    Enforces default-deny:
    * authenticated user with a campus (membership or legacy) → scoped
      ``TenantContext``
    * platform user (explicit ``platform.access``) → platform context
    * authenticated user with NO tenant → 403 (never global access)
    """
    return await resolve_tenant_context(session, current_user, require_school=True)
