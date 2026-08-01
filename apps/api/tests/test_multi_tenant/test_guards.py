"""Direct unit tests for the tenant-guard helpers.

These cover the IDOR-critical logic in ``app.multi_tenant.guards`` in
isolation: scoped tenants must never read, list, or create records
outside their campus — including legacy rows with a ``NULL`` campus_id.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthorizationError
from app.multi_tenant.guards import (
    assert_tenant_scope,
    assert_tenant_scope_or_owner,
    effective_campus_id,
    inject_campus,
)
from app.multi_tenant.models import TenantContext


_MISSING = object()  # sentinel: "no campus_id attribute set"


class _FakeEntity:
    """Minimal stand-in for an ORM row with a campus tag."""

    def __init__(self, campus_id: object = _MISSING, user_id: int | None = None):
        if campus_id is not _MISSING:
            self.campus_id = campus_id
        if user_id is not None:
            self.user_id = user_id


def _scoped() -> TenantContext:
    return TenantContext(campus_id=1)


def _unscoped() -> TenantContext:
    return TenantContext(campus_id=None)


# ======================================================================
# effective_campus_id — list-scope pinning
# ======================================================================


class TestEffectiveCampusId:
    def test_scoped_tenant_pinned_ignores_client_value(self) -> None:
        """A scoped tenant can never filter by a foreign campus."""
        assert effective_campus_id(_scoped(), client_campus_id=99) == 1

    def test_scoped_tenant_no_client_value(self) -> None:
        assert effective_campus_id(_scoped()) == 1

    def test_unscoped_tenant_with_client_filter(self) -> None:
        """Platform admins may still filter by any campus."""
        assert effective_campus_id(_unscoped(), client_campus_id=7) == 7

    def test_unscoped_tenant_no_filter_means_everything(self) -> None:
        assert effective_campus_id(_unscoped()) is None


# ======================================================================
# assert_tenant_scope — object access
# ======================================================================


class TestAssertTenantScope:
    def test_same_campus_allowed(self) -> None:
        assert_tenant_scope(_FakeEntity(campus_id=1), _scoped())

    def test_foreign_campus_denied(self) -> None:
        with pytest.raises(AuthorizationError):
            assert_tenant_scope(_FakeEntity(campus_id=2), _scoped())

    def test_null_campus_denied_for_scoped_tenant(self) -> None:
        """Legacy rows without a campus tag are invisible to scoped users."""
        with pytest.raises(AuthorizationError):
            assert_tenant_scope(_FakeEntity(campus_id=None), _scoped())

    def test_unscoped_caller_bypasses_check(self) -> None:
        assert_tenant_scope(_FakeEntity(campus_id=2), _unscoped())

    def test_entity_without_campus_id_denied_when_scoped(self) -> None:
        with pytest.raises(AuthorizationError):
            assert_tenant_scope(_FakeEntity(user_id=5), _scoped())


# ======================================================================
# assert_tenant_scope_or_owner — owner access to legacy rows
# ======================================================================


class TestAssertTenantScopeOrOwner:
    def test_owner_can_access_legacy_null_campus_row(self) -> None:
        assert_tenant_scope_or_owner(
            _FakeEntity(campus_id=None, user_id=5), _scoped(), owner_user_id=5
        )

    def test_owner_denied_on_row_tagged_with_foreign_campus(self) -> None:
        """Owner-ship does not override an explicit foreign campus tag."""
        with pytest.raises(AuthorizationError):
            assert_tenant_scope_or_owner(
                _FakeEntity(campus_id=2, user_id=5), _scoped(), owner_user_id=5
            )

    def test_owner_same_campus_allowed(self) -> None:
        assert_tenant_scope_or_owner(
            _FakeEntity(campus_id=1, user_id=5), _scoped(), owner_user_id=5
        )

    def test_non_owner_foreign_campus_denied(self) -> None:
        with pytest.raises(AuthorizationError):
            assert_tenant_scope_or_owner(
                _FakeEntity(campus_id=2, user_id=5), _scoped(), owner_user_id=6
            )


# ======================================================================
# inject_campus — create-scope enforcement
# ======================================================================


class TestInjectCampus:
    def test_scoped_tenant_overwrites_client_value(self) -> None:
        entity = _FakeEntity(campus_id=99)
        inject_campus(entity, _scoped())
        assert entity.campus_id == 1

    def test_scoped_tenant_sets_campus_on_untagged_entity(self) -> None:
        entity = _FakeEntity(campus_id=None)
        inject_campus(entity, _scoped())
        assert entity.campus_id == 1

    def test_unscoped_tenant_left_untouched(self) -> None:
        entity = _FakeEntity(campus_id=42)
        inject_campus(entity, _unscoped())
        assert entity.campus_id == 42
