"""Tenant-guard helpers shared by domain routers.

These helpers centralise the two enforcement rules that every
tenant-owned endpoint must follow:

1. **List scope** — a tenant-scoped user's queries are pinned to their
   campus. A client-supplied ``campus_id`` filter is only honoured for
   platform admins (unscoped tenant context).
2. **Object access** — loading a record that belongs to another campus
   raises ``AuthorizationError`` (HTTP 403).

Routers use these in place of trusting client-supplied ``campus_id``
query parameters, which closes the IDOR class of bugs where a user from
School A could pass ``?campus_id=B`` to read School B's data.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.multi_tenant.models import TenantContext


def effective_campus_id(
    tenant: TenantContext,
    client_campus_id: Optional[int] = None,
) -> Optional[int]:
    """Return the campus scope that must be applied to a query.

    * Tenant-scoped users are pinned to ``tenant.campus_id`` — the client
      value is ignored.
    * Platform callers (explicit ``platform.access``) may filter by any
      campus via ``client_campus_id``.
    * Anyone else without a tenant context is DENIED — an unscoped
      non-platform caller must never see tenant data (default-deny).
    """
    if tenant.is_tenant_scoped:
        return tenant.campus_id
    if tenant.platform:
        return client_campus_id
    raise AuthorizationError(
        "No tenant context — cross-tenant access requires an explicit "
        "platform permission."
    )


def assert_tenant_scope(
    entity: Any,
    tenant: TenantContext,
    resource: str = "resource",
) -> None:
    """Raise ``AuthorizationError`` (403) when ``entity`` belongs to a
    campus other than the current tenant's.

    * Tenant-scoped users may only touch their own campus.
    * Platform callers (explicit ``platform.access``) may operate on any
      campus.
    * Unscoped non-platform callers are DENIED by default.

    An entity whose ``campus_id`` is ``None`` is never visible to a
    scoped tenant.
    """
    if tenant.is_tenant_scoped:
        entity_campus = getattr(entity, "campus_id", None)
        if entity_campus is None or entity_campus != tenant.campus_id:
            raise AuthorizationError(
                f"Cross-tenant access denied to {resource}: "
                f"entity belongs to campus {entity_campus}, "
                f"current tenant is campus {tenant.campus_id}."
            )
        return
    if tenant.platform:
        return
    raise AuthorizationError(
        f"Cross-tenant access denied to {resource}: "
        "caller has no tenant context and no platform permission."
    )


def assert_tenant_scope_or_owner(
    entity: Any,
    tenant: TenantContext,
    owner_user_id: int,
    resource: str = "resource",
) -> None:
    """Tenant-scope check that lets the record's owner through.

    Legacy rows (pre-multi-tenancy) may have a ``None`` campus_id while
    still being legitimately owned by the caller. This guard allows the
    owner to access their own record **only when it carries no campus
    tag** (legacy data), then falls back to ``assert_tenant_scope`` for
    everything else — a record explicitly tagged with another campus is
    never accessible, even to its owner.
    """
    if getattr(entity, "user_id", None) == owner_user_id and getattr(
        entity, "campus_id", None
    ) is None:
        return
    assert_tenant_scope(entity, tenant, resource=resource)


def inject_campus(entity: Any, tenant: TenantContext) -> None:
    """Set ``entity.campus_id`` from the tenant context on creation.

    Scoped users can only create records inside their own school; the
    client-supplied value (if any) is overwritten. Unscoped callers are
    left untouched for backward compatibility.
    """
    if tenant.is_tenant_scoped and hasattr(entity, "campus_id"):
        entity.campus_id = tenant.campus_id


async def assert_tenant_scope_by_parent_id(
    session: AsyncSession,
    model: type[Any],
    parent_id: int,
    tenant: TenantContext,
    resource: str = "resource",
) -> None:
    """Raise ``AuthorizationError`` (403) when the parent record's campus
    differs from the tenant's.

    Used for entities that do **not** carry their own ``campus_id`` and
    instead inherit tenancy from a parent (e.g. admission documents,
    interviews, merit entries and seat allocations inherit from
    ``AdmissionApplication``).
    """
    if tenant.is_tenant_scoped:
        result = await session.execute(
            select(model.campus_id).where(model.id == parent_id)
        )
        parent_campus_id = result.scalar_one_or_none()
        if parent_campus_id is None or parent_campus_id != tenant.campus_id:
            raise AuthorizationError(
                f"Cross-tenant access denied to {resource}: "
                f"parent record belongs to campus {parent_campus_id}, "
                f"current tenant is campus {tenant.campus_id}."
            )
        return
    if tenant.platform:
        return
    raise AuthorizationError(
        f"Cross-tenant access denied to {resource}: "
        "caller has no tenant context and no platform permission."
    )
