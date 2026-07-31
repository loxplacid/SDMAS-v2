"""Service for checking permissions against the database role-permission
mappings and the in-memory default registry.

The service provides two modes:

1. **DB-backed** — queries the ``role_permissions`` join table for the
   current role (future-proof, supports custom roles).
2. **Registry fallback** — uses the in-memory ``ROLE_PERMISSIONS`` dict
   when the DB tables don't exist yet (testing / fresh installs).

Callers should always go through the ``PermissionService`` class; the
``has_permission_sync`` helper is exposed for lightweight in-process
checks that do not require a database session.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import Role, Permission
from app.domains.auth.permissions import has_permission as _registry_check


class PermissionService:
    """Check user permissions against the database role-permission
    mappings, falling back to the in-memory registry when the DB
    has not been seeded yet."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def role_has_permission(
        self,
        role_code: str,
        permission_code: str,
    ) -> bool:
        """Check if a single role has a specific permission.

        First tries a DB lookup via the ``role_permissions`` join
        table.  If the role row does not exist (e.g. test env before
        migrations), falls back to the in-memory permission registry.
        """
        result = await self.session.execute(
            select(Role).where(Role.code == role_code)
        )
        role = result.scalar_one_or_none()
        if role is None:
            return _registry_check(role_code, permission_code)

        # Eagerly loaded via relationship(…, lazy="selectin")
        return any(p.code == permission_code for p in role.permissions)

    async def any_role_has_permission(
        self,
        role_codes: list[str],
        permission_code: str,
    ) -> bool:
        """Check if ANY of the given roles has a specific permission.

        Useful for multi-role users: returns True if at least one
        assigned role grants the permission.
        """
        for role_code in role_codes:
            if await self.role_has_permission(role_code, permission_code):
                return True
        return False

    async def get_role_permissions(
        self,
        role_code: str,
    ) -> list[str]:
        """Return all permission codes for a given role."""
        result = await self.session.execute(
            select(Role).where(Role.code == role_code)
        )
        role = result.scalar_one_or_none()
        if role is None:
            from app.domains.auth.permissions import get_permissions_for_role
            return get_permissions_for_role(role_code)

        return [p.code for p in (role.permissions or [])]

    async def get_all_permissions_for_roles(
        self,
        role_codes: list[str],
    ) -> set[str]:
        """Return the union of all permission codes across multiple roles."""
        all_perms: set[str] = set()
        for role_code in role_codes:
            perms = await self.get_role_permissions(role_code)
            all_perms.update(perms)
        return all_perms


def has_permission_sync(role: str, permission: str) -> bool:
    """Lightweight synchronous permission check (no DB required).

    Intended for use in middleware, decorators, or frontend-equivalent
    contexts where a database round-trip is undesirable.

    Uses the in-memory ``ROLE_PERMISSIONS`` registry.
    """
    return _registry_check(role, permission)
