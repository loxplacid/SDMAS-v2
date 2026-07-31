"""Tenant-aware service mixin.

Provides a base mixin that automatically injects ``campus_id`` from the
current tenant context into domain entities during creation.  This
prevents callers from accidentally creating data outside their tenant
scope.

Usage::

    class StudentService(TenantAwareService):
        def __init__(self, repo, tenant=None):
            super().__init__(tenant)
            self.repo = repo

        async def create(self, data):
            student = Student(...)
            self.inject_tenant(student)   # sets student.campus_id
            return await self.repo.create(student)
"""

from __future__ import annotations

from typing import Optional, TypeVar

from app.infrastructure.database import Base
from app.multi_tenant.models import TenantContext

T = TypeVar("T", bound=Base)


class TenantAwareService:
    """Mixin that provides tenant-scoped entity creation.

    Subclass this and call ``inject_tenant(entity)`` before persisting
    a new entity.  If the tenant context has a ``campus_id`` and the
    entity has a ``campus_id`` attribute, it will be set automatically.

    When ``campus_id`` is ``None`` (single-tenant / super-admin mode),
    no value is injected so existing NULL-friendly code continues to
    work unchanged.
    """

    def __init__(self, tenant: Optional[TenantContext] = None) -> None:
        self.tenant = tenant

    def inject_tenant(self, entity: T) -> T:
        """Set ``entity.campus_id`` from the current tenant context.

        Only sets the value when *both* sides have the attribute:
        the tenant must have a concrete ``campus_id`` and the entity
        model must declare a ``campus_id`` column.

        Returns the entity for chaining.
        """
        if self.tenant is not None and self.tenant.campus_id is not None:
            if hasattr(entity, "campus_id"):
                setattr(entity, "campus_id", self.tenant.campus_id)
        return entity

    def assert_tenant_scoped(self, entity: T) -> None:
        """Raise if the entity's ``campus_id`` does not match the
        current tenant context.

        Call this after loading an entity to guard against cross-tenant
        reads.  Skips the check when tenant is unscoped (``campus_id``
        is ``None``), preserving backward compatibility.
        """
        if self.tenant is None or self.tenant.campus_id is None:
            return
        entity_campus = getattr(entity, "campus_id", None)
        if entity_campus is not None and entity_campus != self.tenant.campus_id:
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError(
                "Cross-tenant access denied. "
                f"Entity belongs to campus {entity_campus}, "
                f"current tenant is campus {self.tenant.campus_id}."
            )
