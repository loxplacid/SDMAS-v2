from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.multi_tenant import registry
from app.multi_tenant.models import TenantContext
from app.multi_tenant.models import platform_context


class TenantScopedRepository:
    """Canonical base class for all tenant-owned repositories.

    **Tenant scoping is applied at query construction time** — every
    ``SELECT`` built through this class carries the current tenant's
    ``campus_id`` predicate, so a scoped caller can never retrieve a row
    belonging to another campus (IDOR is closed in the repository layer,
    not by remembering to call a guard afterwards).

    Usage::

        class StudentRepository(TenantScopedRepository):
            def __init__(self, session, tenant=None):
                super().__init__(session, tenant)
                ...

    Scope rules
    -----------
    * ``tenant.campus_id`` set → every query is pinned to that campus.
    * ``tenant`` explicitly platform-authorized (``platform=True``)
      → no filter is applied (cross-tenant read).
    * ``tenant`` is ``None`` or unscoped and NOT platform-authorized
      → calls that go through :meth:`scoped_query` / :meth:`get_by_id`
      raise :class:`AuthorizationError`; platform data models are exempt.

    ``tenant=None`` is **never** treated as platform access — a missing
    tenant context fails closed instead of silently granting cross-tenant
    visibility.  Platform callers must pass an explicit platform
    ``TenantContext`` (see ``multi_tenant.models.platform_context()``).

    Platform-owned models (see :mod:`app.multi_tenant.registry`) are never
    filtered, so global tables keep working unchanged.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant

    # ------------------------------------------------------------------
    # Scope resolution helpers
    # ------------------------------------------------------------------

    def _effective_campus_id(self) -> Optional[int]:
        """Return the campus id every tenant-owned query must be pinned to,
        or ``None`` for platform / unscoped access."""
        if self.tenant is not None and self.tenant.is_tenant_scoped:
            return self.tenant.campus_id
        return None

    def _has_platform_access(self) -> bool:
        """True when the caller may legally query across campuses.

        ``tenant=None`` is treated as **no access** (fail-closed).
        Only an explicitly platform-authorized ``TenantContext``
        (``platform=True``) may operate outside tenant boundaries.
        """
        if self.tenant is None:
            return False
        if not self.tenant.is_tenant_scoped:
            return self.tenant.allow_cross_tenant
        return False

    def require_tenant_scope(self, model: Any) -> None:
        """Raise when ``model`` is tenant-owned and the caller has neither
        a concrete tenant scope nor explicit platform authorization.

        This is the deny-by-default enforcement point: a tenant-owned
        model queried by an unscoped, non-platform caller is a cross-tenant
        access attempt.
        """
        if registry.tenant_scope_of(model) == registry.PLATFORM:
            return
        if self._effective_campus_id() is not None:
            return
        if self._has_platform_access():
            return
        raise AuthorizationError(
            "Cross-tenant access denied: querying a tenant-owned resource "
            "requires an active school context or explicit platform "
            "authorization."
        )

    # ------------------------------------------------------------------
    # Public helpers for subclasses (backward compatible)
    # ------------------------------------------------------------------

    def _apply_tenant_filter(self, query, model):
        """Append the canonical tenant predicate (and join, if the model
        inherits tenancy) to ``query``.

        Returns ``(modified_query, was_applied)`` so callers can decide
        whether a companion count query needs the same filter.
        """
        campus_id = self._effective_campus_id()
        if campus_id is None:
            return query, False
        spec = registry.tenant_filter_for(model, campus_id)
        if spec is None:
            return query, False
        return registry.apply_tenant_filter(query, model, campus_id), True

    def _apply_tenant_to_count(self, query, model):
        """Convenience wrapper that applies the tenant filter to a
        count / aggregate query using the same logic as
        ``_apply_tenant_filter``."""
        query, _ = self._apply_tenant_filter(query, model)
        return query

    # ------------------------------------------------------------------
    # Canonical query construction
    # ------------------------------------------------------------------

    def scoped_query(self, model: Any):
        """Build ``select(model)`` with the tenant predicate already
        applied (and the parent join added for inherited-tenancy models).

        Raises :class:`AuthorizationError` when the caller is neither
        tenant-scoped nor explicitly platform-authorized.
        """
        self.require_tenant_scope(model)
        query = select(model)
        return self._apply_tenant_filter(query, model)[0]

    def scoped_count(self, model: Any):
        """Build ``select(func.count(model.id))`` with the tenant predicate
        applied.  Mirrors :meth:`scoped_query` for companion count queries."""
        self.require_tenant_scope(model)
        return self._apply_tenant_to_count(select(func.count(model.id)), model)

    def tenant_scope_checked(self, model: Any) -> None:
        """Assert the caller may touch ``model`` (tenant-owned or not).

        Convenience for methods that build raw queries which are later
        combined with :meth:`_apply_tenant_filter`; raises the same
        default-deny :class:`AuthorizationError` as :meth:`scoped_query`.
        """
        self.require_tenant_scope(model)

    def _tenant_conditions(self, model: Any, extra_filters: Optional[list] = None) -> list:
        """Return the full WHERE condition list (tenant predicate + extras)."""
        conditions: list = list(extra_filters or [])
        campus_id = self._effective_campus_id()
        if campus_id is not None:
            spec = registry.tenant_filter_for(model, campus_id)
            if spec is not None:
                conditions.append(spec[0])
        return conditions

    async def get_by_id(self, model: Any, entity_id: int):
        """Fetch one row by primary key, tenant-filtered at query time.

        A row owned by a different campus simply does not exist to a
        scoped caller — returns ``None`` (callers usually raise
        :class:`NotFoundError`).
        """
        self.require_tenant_scope(model)
        query = self.scoped_query(model).where(model.id == entity_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_none(self, model: Any, entity_id: int):
        """Alias for :meth:`get_by_id` — returns ``None`` when absent."""
        return await self.get_by_id(model, entity_id)

    async def get_by_id_or_404(self, model: Any, entity_id: int, resource: str = "resource"):
        """Fetch by id and raise :class:`NotFoundError` when absent
        (including when the row belongs to another campus)."""
        entity = await self.get_by_id(model, entity_id)
        if entity is None:
            raise NotFoundError(f"{resource} with id {entity_id} not found")
        return entity

    async def exists(self, model: Any, entity_id: int) -> bool:
        """Tenant-scoped existence check."""
        self.require_tenant_scope(model)
        campus_id = self._effective_campus_id()
        count_query = select(func.count(model.id)).where(model.id == entity_id)
        if campus_id is not None:
            count_query = self._apply_tenant_to_count(count_query, model)
        result = await self.session.execute(count_query)
        return (result.scalar() or 0) > 0

    async def first(self, model: Any, *where_conditions: Any):
        """Tenant-scoped ``SELECT ... LIMIT 1`` with optional extra
        conditions."""
        query = self.scoped_query(model)
        if where_conditions:
            query = query.where(*where_conditions)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Convenience CRUD helpers that respect tenant scope
    # ------------------------------------------------------------------

    async def _list_by_tenant(
        self,
        model,
        *,
        order_by_attr: str = "id",
        skip: int = 0,
        limit: int = 100,
        extra_filters: Optional[list] = None,
    ) -> tuple[list, int]:
        """Generic paginated list with automatic tenant scoping.

        Raises :class:`AuthorizationError` when the caller is
        neither tenant-scoped nor explicitly platform-authorized.
        """
        self.require_tenant_scope(model)

        query = select(model)
        count_query = select(func.count(model.id))

        if extra_filters:
            query = query.where(*extra_filters)
            count_query = count_query.where(*extra_filters)

        query, tenant_applied = self._apply_tenant_filter(query, model)
        if tenant_applied:
            count_query = self._apply_tenant_to_count(count_query, model)

        order_col = getattr(model, order_by_attr, model.id)
        query = query.order_by(order_col).offset(skip).limit(limit)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total
