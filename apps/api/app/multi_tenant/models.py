from __future__ import annotations

import enum
from dataclasses import dataclass


class TenantScope(str, enum.Enum):
    """The explicit scope of a request's tenant context.

    Tenants (campus members) and platform operators are *explicitly*
    distinguished so that platform-level (cross-tenant) access can be
    authorized deliberately instead of being the accidental default.
    """

    #: No authenticated principal (public / optional-auth endpoints).
    ANON = "anon"
    #: Authenticated, but scoped to a concrete campus.
    TENANT = "tenant"
    #: Authenticated, unscoped — platform / cross-tenant operator.
    #: Only valid after explicit platform authorization (see
    #: ``multi_tenant.dependencies.get_platform_context``).
    PLATFORM = "platform"


class TenantScopeLevel(str, enum.Enum):
    """The granularity of a caller's tenant scope within the enterprise
    hierarchy ``Organization → School Group → Region → Campus``.

    Every level below ``PLATFORM`` is a *restricted* scope: queries are
    pinned to the subtree at that level and can never escape it.  Only
    explicit platform authorization may operate outside every hierarchy
    boundary.
    """

    #: No scope at all — fail-closed for tenant-owned data.
    NONE = "none"
    #: Explicit platform grant — may operate across all boundaries.
    PLATFORM = "platform"
    #: Organization administrator — all campuses under one institution.
    ORGANIZATION = "organization"
    #: School-group administrator — all campuses under one group.
    GROUP = "group"
    #: Region administrator — all campuses under one region.
    REGION = "region"
    #: Campus-scoped (the existing tenant unit) — one campus.
    CAMPUS = "campus"


@dataclass
class TenantContext:
    """Represents the current tenant scope extracted from authentication.

    Attributes:
        campus_id: The campus (tenant) ID the current user belongs to.
            May be None for cross-tenant admin users or until all legacy
            users have been assigned to a campus.
        institution_id: The top-level institution ID derived from the
            campus hierarchy.  For an organization-administrator scope this
            is the scope itself; otherwise it is informational.  May be
            None when the caller has no organization.
        school_group_id: Non-None only for a school-group-administrator
            scope (authorizes every campus under that group).
        region_id: Non-None only for a region-administrator scope
            (authorizes every campus under that region).
        user_id: The authenticated user's ID, when known.
        platform: True when the caller holds an explicit platform
            permission and may operate outside tenant boundaries.
    """

    campus_id: int | None = None
    institution_id: int | None = None
    school_group_id: int | None = None
    region_id: int | None = None
    user_id: int | None = None
    platform: bool = False
    """True when the caller holds an explicit platform permission.

    Platform-scoped callers are the ONLY ones allowed to operate outside
    tenant boundaries.  An unscoped context without ``platform`` is never
    treated as full access — guards deny it by default.
    """

    @property
    def is_tenant_scoped(self) -> bool:
        """True when a concrete tenant (campus) is known.

        Kept campus-only for backward compatibility: hierarchy
        administrators (region/group/organization) are *not* "tenant
        scoped" in the campus sense; use :attr:`is_hierarchy_scoped` or
        :attr:`scope_level` for those.
        """
        return self.campus_id is not None

    @property
    def is_hierarchy_scoped(self) -> bool:
        """True when the caller is pinned to a concrete subtree of the
        enterprise hierarchy (campus, region, group or organization).

        This is the general "may query tenant-owned data" flag: it covers
        the classic campus-scoped tenant plus hierarchy administrators.
        Unscoped non-platform callers return False and are denied.
        """
        return self.scope_level in (
            TenantScopeLevel.CAMPUS,
            TenantScopeLevel.REGION,
            TenantScopeLevel.GROUP,
            TenantScopeLevel.ORGANIZATION,
        )

    @property
    def scope_level(self) -> TenantScopeLevel:
        """Classify the context into a hierarchy scope level.

        The most specific non-empty scope wins: campus → region → group →
        organization → platform → none.
        """
        if self.campus_id is not None:
            return TenantScopeLevel.CAMPUS
        if self.region_id is not None:
            return TenantScopeLevel.REGION
        if self.school_group_id is not None:
            return TenantScopeLevel.GROUP
        if self.institution_id is not None:
            return TenantScopeLevel.ORGANIZATION
        if self.platform:
            return TenantScopeLevel.PLATFORM
        return TenantScopeLevel.NONE

    @property
    def allow_cross_tenant(self) -> bool:
        """True when the caller may legally operate across campuses
        (explicit platform permission or a hierarchy admin scope)."""
        return self.platform or self.scope_level in (
            TenantScopeLevel.ORGANIZATION,
            TenantScopeLevel.GROUP,
            TenantScopeLevel.REGION,
        )

    @property
    def scope(self) -> TenantScope:
        """Classify the context into an explicit scope.

        ``tenant=None`` or an authenticated user without a campus
        and without explicit platform permission is ANON — never
        PLATFORM.  Platform scope requires an explicit platform
        grant.
        """
        if self.campus_id is not None:
            return TenantScope.TENANT
        if self.platform:
            return TenantScope.PLATFORM
        return TenantScope.ANON

    def require_platform(self) -> "TenantContext":
        """Return a copy flagged as explicitly platform-authorized.

        This is the explicit opt-in required for cross-tenant queries;
        callers may only produce it after checking the caller holds a
        platform permission.
        """
        return TenantContext(
            campus_id=self.campus_id,
            institution_id=self.institution_id,
            school_group_id=self.school_group_id,
            region_id=self.region_id,
            user_id=self.user_id,
            platform=True,
        )


def platform_context(user_id: int | None = None) -> TenantContext:
    """Return an **explicitly platform-authorized** tenant context.

    The ONLY sanctioned way for platform-level code (background workers,
    schedulers, platform admin flows) to construct an unscoped context:
    ``tenant=None`` fails closed in :class:`TenantScopedRepository`, so
    legitimate cross-tenant operations must declare their platform scope
    explicitly instead of relying on the absence of a tenant.
    """
    return TenantContext(user_id=user_id, platform=True)


def hierarchy_context(
    *,
    institution_id: int | None = None,
    school_group_id: int | None = None,
    region_id: int | None = None,
    campus_id: int | None = None,
    user_id: int | None = None,
) -> TenantContext:
    """Construct a hierarchy-scoped tenant context for administrative code
    (background workers, platform flows) that must operate across a known
    subtree.

    Exactly the levels permitted for enterprise administrators — callers
    are responsible for resolving the admin's assignment *first*; this
    helper only packages an already-authorized scope.  It never implies
    platform access: an ``institution_id`` alone stays inside that one
    organization.
    """
    return TenantContext(
        campus_id=campus_id,
        institution_id=institution_id,
        school_group_id=school_group_id,
        region_id=region_id,
        user_id=user_id,
    )
