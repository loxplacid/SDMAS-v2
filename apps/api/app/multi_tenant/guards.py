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
from app.multi_tenant.models import TenantContext, TenantScopeLevel


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


# ---------------------------------------------------------------------------
# Enterprise hierarchy guards (organization → school group → region → campus)
#
# These guards verify that a target campus / hierarchy node lies INSIDE the
# caller's subtree.  Campus-scoped callers must match exactly; hierarchy
# administrators (region / group / organization) must be able to reach the
# campus through their subtree; platform callers may reach anything; and an
# unscoped non-platform caller is denied by default.
# ---------------------------------------------------------------------------


def _scope_error(resource: str, detail: str) -> AuthorizationError:
    return AuthorizationError(
        f"Cross-tenant access denied to {resource}: {detail}"
    )


async def _resolve_campus_scope(
    session: AsyncSession,
    campus_id: int,
) -> tuple[int, int | None, int | None] | None:
    """Return ``(institution_id, school_group_id, region_id)`` for a campus,
    resolving the group through the region when the campus is not directly
    linked to a group.  Returns ``None`` when the campus does not exist."""
    from app.domains.institution.models import Campus, Region

    result = await session.execute(
        select(Campus.institution_id, Campus.school_group_id, Campus.region_id).where(
            Campus.id == campus_id
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    institution_id, school_group_id, region_id = row
    if school_group_id is None and region_id is not None:
        region_result = await session.execute(
            select(Region.school_group_id).where(Region.id == region_id)
        )
        school_group_id = region_result.scalar_one_or_none()
    return institution_id, school_group_id, region_id


async def assert_campus_in_scope(
    session: AsyncSession,
    tenant: TenantContext,
    campus_id: Optional[int],
    resource: str = "resource",
) -> None:
    """Raise ``AuthorizationError`` (403) when ``campus_id`` lies outside the
    caller's hierarchy subtree.

    * Platform callers may reach any campus.
    * Campus-scoped callers must match ``tenant.campus_id`` exactly.
    * Region administrators may reach campuses in their region.
    * Group administrators may reach campuses in their group.
    * Organization administrators may reach any campus of their institution.
    * An unscoped non-platform caller is denied by default.
    """
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return
    if campus_id is None:
        raise _scope_error(resource, "entity is not assigned to a campus")
    if tenant.is_tenant_scoped:
        if campus_id != tenant.campus_id:
            raise _scope_error(
                resource,
                f"entity belongs to campus {campus_id}, "
                f"current tenant is campus {tenant.campus_id}.",
            )
        return

    resolved = await _resolve_campus_scope(session, campus_id)
    if resolved is None:
        raise _scope_error(resource, f"campus {campus_id} does not exist")
    institution_id, school_group_id, region_id = resolved

    if tenant.scope_level == TenantScopeLevel.ORGANIZATION:
        if institution_id != tenant.institution_id:
            raise _scope_error(
                resource,
                f"campus {campus_id} belongs to institution {institution_id}, "
                f"current tenant is institution {tenant.institution_id}.",
            )
        return
    if tenant.scope_level == TenantScopeLevel.GROUP:
        if school_group_id != tenant.school_group_id:
            raise _scope_error(
                resource,
                f"campus {campus_id} does not belong to the caller's "
                f"school group {tenant.school_group_id}.",
            )
        return
    if tenant.scope_level == TenantScopeLevel.REGION:
        if region_id != tenant.region_id:
            raise _scope_error(
                resource,
                f"campus {campus_id} does not belong to the caller's "
                f"region {tenant.region_id}.",
            )
        return
    raise _scope_error(resource, "caller has no tenant context and no platform permission.")


async def assert_tenant_scope_async(
    session: AsyncSession,
    entity: Any,
    tenant: TenantContext,
    resource: str = "resource",
) -> None:
    """Async variant of :func:`assert_tenant_scope` that additionally
    verifies hierarchy administrators (region / group / organization) may
    reach the entity's campus.

    Falls back to the synchronous check for campus-scoped and platform
    callers; a non-hierarchy unscoped caller is denied by default.
    """
    if tenant.is_tenant_scoped or tenant.platform:
        assert_tenant_scope(entity, tenant, resource=resource)
        return
    if tenant.is_hierarchy_scoped:
        await assert_campus_in_scope(
            session, tenant, getattr(entity, "campus_id", None), resource=resource
        )
        return
    raise _scope_error(resource, "caller has no tenant context and no platform permission.")


async def assert_institution_in_scope(
    session: AsyncSession,
    tenant: TenantContext,
    institution_id: int,
    resource: str = "resource",
) -> None:
    """Raise 403 when ``institution_id`` (a legal organization) is outside
    the caller's scope.

    Only organization administrators may manage their own institution;
    group/region/campus administrators and unscoped callers are denied.
    Platform callers may reach any institution.
    """
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return
    if tenant.scope_level == TenantScopeLevel.ORGANIZATION:
        if institution_id != tenant.institution_id:
            raise _scope_error(
                resource,
                f"institution {institution_id} is outside the caller's "
                f"organization {tenant.institution_id}.",
            )
        return
    raise _scope_error(
        resource,
        "only platform or organization administrators may access institutions.",
    )


async def assert_school_group_in_scope(
    session: AsyncSession,
    tenant: TenantContext,
    school_group: Any,
    resource: str = "school_group",
) -> None:
    """Raise 403 when ``school_group`` is outside the caller's scope.

    * Platform callers may reach any group.
    * Organization administrators may reach any group of their institution.
    * Group administrators may reach only their own group.
    * Everyone else is denied.
    """
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return
    if tenant.scope_level == TenantScopeLevel.ORGANIZATION:
        if getattr(school_group, "institution_id", None) != tenant.institution_id:
            raise _scope_error(
                resource,
                f"group {getattr(school_group, 'id', None)} belongs to "
                f"institution {getattr(school_group, 'institution_id', None)}, "
                f"caller is organization {tenant.institution_id}.",
            )
        return
    if tenant.scope_level == TenantScopeLevel.GROUP:
        if getattr(school_group, "id", None) != tenant.school_group_id:
            raise _scope_error(
                resource,
                f"group {getattr(school_group, 'id', None)} is not the "
                f"caller's group {tenant.school_group_id}.",
            )
        return
    raise _scope_error(
        resource,
        "only platform, organization or group administrators may access school groups.",
    )


async def assert_region_in_scope(
    session: AsyncSession,
    tenant: TenantContext,
    region: Any,
    resource: str = "region",
) -> None:
    """Raise 403 when ``region`` is outside the caller's scope.

    * Platform callers may reach any region.
    * Organization administrators may reach any region of their institution.
    * Group administrators may reach any region of their group.
    * Region administrators may reach only their own region.
    * Everyone else is denied.
    """
    if tenant.scope_level == TenantScopeLevel.PLATFORM:
        return
    if tenant.scope_level == TenantScopeLevel.ORGANIZATION:
        if getattr(region, "institution_id", None) != tenant.institution_id:
            raise _scope_error(
                resource,
                f"region {getattr(region, 'id', None)} belongs to institution "
                f"{getattr(region, 'institution_id', None)}, "
                f"caller is organization {tenant.institution_id}.",
            )
        return
    if tenant.scope_level == TenantScopeLevel.GROUP:
        region_group_id = getattr(region, "school_group_id", None)
        if region_group_id != tenant.school_group_id:
            raise _scope_error(
                resource,
                f"region {getattr(region, 'id', None)} does not belong to the "
                f"caller's group {tenant.school_group_id}.",
            )
        return
    if tenant.scope_level == TenantScopeLevel.REGION:
        if getattr(region, "id", None) != tenant.region_id:
            raise _scope_error(
                resource,
                f"region {getattr(region, 'id', None)} is not the caller's "
                f"region {tenant.region_id}.",
            )
        return
    raise _scope_error(
        resource,
        "only platform, organization, group or region administrators may access regions.",
    )
