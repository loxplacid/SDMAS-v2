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


@dataclass
class TenantContext:
    """Represents the current tenant scope extracted from authentication.

    Attributes:
        campus_id: The campus (tenant) ID the current user belongs to.
            May be None for cross-tenant admin users or until all legacy
            users have been assigned to a campus.
        institution_id: The top-level institution ID derived from the
            campus hierarchy. May be None when campus_id is None.
        user_id: The authenticated user's ID, when known.
        platform: True when the caller holds an explicit platform
            permission and may operate outside tenant boundaries.
    """

    campus_id: int | None = None
    institution_id: int | None = None
    user_id: int | None = None
    platform: bool = False
    """True when the caller holds an explicit platform permission.

    Platform-scoped callers are the ONLY ones allowed to operate outside
    tenant boundaries.  An unscoped context without ``platform`` is never
    treated as full access — guards deny it by default.
    """

    @property
    def is_tenant_scoped(self) -> bool:
        """True when a concrete tenant (campus) is known."""
        return self.campus_id is not None

    @property
    def allow_cross_tenant(self) -> bool:
        """True when the caller may legally operate across campuses
        (explicit platform permission)."""
        return self.platform

    @property
    def scope(self) -> TenantScope:
        """Classify the context into an explicit scope."""
        if self.campus_id is not None:
            return TenantScope.TENANT
        if self.platform:
            return TenantScope.PLATFORM
        if self.user_id is not None:
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
            user_id=self.user_id,
            platform=True,
        )
