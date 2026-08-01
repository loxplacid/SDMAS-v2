from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TenantContext:
    """Represents the current tenant scope extracted from authentication.

    Attributes:
        campus_id: The campus (tenant) ID the current user belongs to.
            May be None for cross-tenant admin users or until all legacy
            users have been assigned to a campus.
        institution_id: The top-level institution ID derived from the
            campus hierarchy. May be None when campus_id is None.
    """

    campus_id: int | None = None
    institution_id: int | None = None
    user_id: int | None = None

    @property
    def is_tenant_scoped(self) -> bool:
        """True when a concrete tenant (campus) is known."""
        return self.campus_id is not None
