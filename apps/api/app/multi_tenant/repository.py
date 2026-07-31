from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext


class TenantScopedRepository:
    """Mixin that adds automatic tenant-scoped filtering to queries.

    Usage:
        class StudentRepository(TenantScopedRepository):
            def __init__(self, session, tenant=None):
                super().__init__(session, tenant)
                ...

    When ``tenant.campus_id`` is set and the model has a ``campus_id``
    column, every read query is automatically filtered to only return
    data belonging to that campus.  When tenant is ``None`` or
    ``campus_id`` is ``None``, no tenant filter is applied (backward-
    compatible single-tenant / cross-tenant-admin mode).
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant

    # ------------------------------------------------------------------
    # Public helpers for subclasses
    # ------------------------------------------------------------------

    def _apply_tenant_filter(self, query, model):
        """Append a ``campus_id`` WHERE clause when tenant-scoped.

        Returns ``(modified_query, was_applied)`` so callers can decide
        whether a companion count query needs the same filter.
        """
        if self.tenant is not None and self.tenant.campus_id is not None:
            col = getattr(model, "campus_id", None)
            if col is not None:
                return query.where(col == self.tenant.campus_id), True
        return query, False

    def _apply_tenant_to_count(self, query, model):
        """Convenience wrapper that applies the tenant filter to a
        count / aggregate query using the same logic as
        ``_apply_tenant_filter``."""
        query, _ = self._apply_tenant_filter(query, model)
        return query

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

        Args:
            model: The SQLAlchemy model class.
            order_by_attr: Attribute name to order results by.
            skip: Offset for pagination.
            limit: Page size.
            extra_filters: Optional list of additional WHERE conditions.

        Returns:
            ``(items, total_count)`` tuple.
        """
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
