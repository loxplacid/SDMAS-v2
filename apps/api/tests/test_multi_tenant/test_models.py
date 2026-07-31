"""Tests for the multi-tenant data model."""

from __future__ import annotations

from app.multi_tenant.models import TenantContext


class TestTenantContext:
    """TenantContext should correctly represent tenant scope."""

    def test_empty_context(self):
        ctx = TenantContext()
        assert ctx.campus_id is None
        assert ctx.institution_id is None
        assert ctx.is_tenant_scoped is False

    def test_campus_only(self):
        ctx = TenantContext(campus_id=5)
        assert ctx.campus_id == 5
        assert ctx.institution_id is None
        assert ctx.is_tenant_scoped is True

    def test_full_context(self):
        ctx = TenantContext(campus_id=5, institution_id=1)
        assert ctx.campus_id == 5
        assert ctx.institution_id == 1
        assert ctx.is_tenant_scoped is True

    def test_mutable_fields(self):
        """TenantContext uses dataclass so fields are mutable."""
        ctx = TenantContext()
        ctx.campus_id = 10
        assert ctx.campus_id == 10
        assert ctx.is_tenant_scoped is True
