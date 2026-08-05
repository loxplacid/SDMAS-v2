"""Tests for the TenantScopedRepository mixin and full auth->tenant pipeline.

Uses the existing Student model (which has a campus_id column) to
verify that tenant filtering is applied correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func

from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.multi_tenant.models import platform_context

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ======================================================================
# TenantScopedRepository unit tests
# ======================================================================


class TestTenantScopedRepository:
    """Verify that the mixin correctly applies tenant filters."""

    async def test_raw_select_is_not_tenancy_checked(self, db_session: AsyncSession):
        """Raw ``select`` bypasses the repository entirely — it is NOT an
        implicit platform access.  Tenant isolation is enforced where
        queries are built through :class:`TenantScopedRepository`, which
        fails closed on ``tenant=None`` (see the fail-closed tests below)."""
        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="TN002", campus_id=2),
        ])
        await db_session.flush()

        result = await db_session.execute(select(Student))
        assert len(result.scalars().all()) == 2

    async def test_tenant_scoped_filter(self, db_session: AsyncSession):
        """With a tenant, only matching campus students are returned."""
        db_session.add_all([
            Student(first_name="X", last_name="Y", student_number="TN003", campus_id=1),
            Student(first_name="Z", last_name="W", student_number="TN004", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, TenantContext(campus_id=1))
        query = select(Student)
        query, applied = repo._apply_tenant_filter(query, Student)
        assert applied is True

        result = await db_session.execute(query)
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].student_number == "TN003"

    async def test_empty_tenant_denied_for_tenant_owned_model(self, db_session: AsyncSession):
        """A TenantContext with no campus and no platform must be
        denied for tenant-owned models (fail-closed)."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A1", last_name="B1", student_number="TN005", campus_id=1),
            Student(first_name="A2", last_name="B2", student_number="TN006", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, TenantContext())
        with pytest.raises(AuthorizationError):
            await repo._list_by_tenant(Student, skip=0, limit=100)

    async def test_tenant_scoped_list(self, db_session: AsyncSession):
        """_list_by_tenant returns only campus-scoped rows."""
        db_session.add_all([
            Student(first_name="P", last_name="Q", student_number="TN007", campus_id=1),
            Student(first_name="R", last_name="S", student_number="TN008", campus_id=2),
            Student(first_name="T", last_name="U", student_number="TN009", campus_id=1),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, TenantContext(campus_id=1))
        items, total = await repo._list_by_tenant(Student, skip=0, limit=100)
        assert total == 2
        assert {s.student_number for s in items} == {"TN007", "TN009"}

    async def test_apply_tenant_to_count(self, db_session: AsyncSession):
        """_apply_tenant_to_count correctly scopes count queries."""
        db_session.add_all([
            Student(first_name="M", last_name="N", student_number="TN010", campus_id=1),
            Student(first_name="O", last_name="P", student_number="TN011", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, TenantContext(campus_id=1))
        query = select(func.count(Student.id))
        filtered = repo._apply_tenant_to_count(query, Student)

        result = await db_session.execute(filtered)
        assert result.scalar() == 1  # only campus 1

    async def test_model_without_campus_id(self, db_session: AsyncSession):
        """Models without campus_id column are not filtered."""
        repo = TenantScopedRepository(db_session, TenantContext(campus_id=1))

        # The select() query should not crash — no campus_id attr to filter on
        class FakeModel:
            id: int

        query = select(1)
        filtered, applied = repo._apply_tenant_filter(query, FakeModel)
        assert applied is False


# ======================================================================
# TenantContext model tests
# ======================================================================


class TestTenantContext:
    def test_empty_context(self):
        ctx = TenantContext()
        assert ctx.campus_id is None
        assert ctx.institution_id is None
        assert ctx.is_tenant_scoped is False

    def test_campus_only(self):
        ctx = TenantContext(campus_id=5)
        assert ctx.campus_id == 5
        assert ctx.is_tenant_scoped is True

    def test_full_context(self):
        ctx = TenantContext(campus_id=5, institution_id=1)
        assert ctx.campus_id == 5
        assert ctx.institution_id == 1
        assert ctx.is_tenant_scoped is True

    def test_mutable_fields(self):
        ctx = TenantContext()
        ctx.campus_id = 10
        assert ctx.is_tenant_scoped is True


# ======================================================================
# TenantScopedRepository - fail-closed when tenant=None
# ======================================================================


class TestTenantScopedRepositoryFailClosed:
    """When tenant is None, the repository must deny access rather
    than silently granting platform-level cross-tenant visibility."""

    async def test_no_tenant_denies_scoped_query(self, db_session: AsyncSession):
        """A TenantScopedRepository with tenant=None must raise
        AuthorizationError when querying tenant-owned models."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="TN002", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo.scoped_query(Student)

    async def test_no_tenant_denies_get_by_id(self, db_session: AsyncSession):
        """A TenantScopedRepository with tenant=None must raise
        AuthorizationError when fetching by id."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo.get_by_id(Student, 1)

    async def test_no_tenant_denies_scoped_count(self, db_session: AsyncSession):
        """A TenantScopedRepository with tenant=None must raise
        AuthorizationError when counting tenant-owned models."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo.scoped_count(Student)

    async def test_no_tenant_denies_first(self, db_session: AsyncSession):
        """A TenantScopedRepository with tenant=None must raise
        AuthorizationError when calling first()."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo.first(Student)

    async def test_no_tenant_denies_exists(self, db_session: AsyncSession):
        """A TenantScopedRepository with tenant=None must raise
        AuthorizationError when checking existence."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo.exists(Student, 1)

    async def test_no_tenant_denies_list_by_tenant(self, db_session: AsyncSession):
        """A TenantScopedRepository with tenant=None must raise
        AuthorizationError when listing tenant-owned models."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="TN001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="TN002", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo._list_by_tenant(Student)


# ======================================================================
# TenantContext.scope - fail-closed classification
# ======================================================================


class TestTenantContextScopeFailClosed:
    """TenantContext.scope must never return PLATFORM for an
    authenticated user without explicit platform permission."""

    def test_tenant_scoped_user_is_tenant(self):
        ctx = TenantContext(campus_id=1, user_id=5)
        assert ctx.scope.value == "tenant"

    def test_platform_user_is_platform(self):
        ctx = TenantContext(campus_id=None, platform=True, user_id=5)
        assert ctx.scope.value == "platform"

    def test_authenticated_user_without_campus_is_anon(self):
        """A user with no campus and no platform permission must
        be ANON, not PLATFORM.  This is the core fail-closed fix."""
        ctx = TenantContext(campus_id=None, platform=False, user_id=5)
        assert ctx.scope.value == "anon"

    def test_unauthenticated_is_anon(self):
        ctx = TenantContext(user_id=None)
        assert ctx.scope.value == "anon"


# ======================================================================
# Tenant isolation - tenant A cannot access tenant B
# ======================================================================


class TestTenantIsolation:
    """Tenant-scoped users must never see data from other tenants."""

    async def test_tenant_a_cannot_read_tenant_b_student(self, db_session: AsyncSession):
        """A student from campus 1 must not be visible to a
        tenant-scoped repository for campus 2."""
        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="ISO001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="ISO002", campus_id=2),
        ])
        await db_session.flush()

        repo_a = TenantScopedRepository(db_session, TenantContext(campus_id=1))
        repo_b = TenantScopedRepository(db_session, TenantContext(campus_id=2))

        # Tenant A can only see their own student
        rows_a = await repo_a._list_by_tenant(Student)
        assert len(rows_a[0]) == 1
        assert rows_a[0][0].student_number == "ISO001"

        # Tenant B can only see their own student
        rows_b = await repo_b._list_by_tenant(Student)
        assert len(rows_b[0]) == 1
        assert rows_b[0][0].student_number == "ISO002"

    async def test_tenant_a_cannot_read_tenant_b_by_id(self, db_session: AsyncSession):
        """A tenant-scoped get_by_id must return None for a
        foreign campus record, not raise."""
        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="ISO003", campus_id=1),
            Student(first_name="C", last_name="D", student_number="ISO004", campus_id=2),
        ])
        await db_session.flush()

        repo_a = TenantScopedRepository(db_session, TenantContext(campus_id=1))
        result = await repo_a.get_by_id(Student, 2)
        assert result is None


# ======================================================================
# Platform access requires explicit authorization
# ======================================================================


class TestPlatformAccessRequiresExplicitAuthorization:
    """Platform-level access must come from an explicit platform
    grant, not from a missing tenant context."""

    def test_platform_context_requires_platform_flag(self):
        """TenantContext without platform=True is not platform,
        even if campus_id is None."""
        ctx = TenantContext(campus_id=None, platform=False, user_id=5)
        assert ctx.platform is False
        assert ctx.is_tenant_scoped is False
        assert ctx.allow_cross_tenant is False

    def test_platform_context_with_explicit_flag(self):
        """TenantContext with platform=True grants cross-tenant access."""
        ctx = TenantContext(campus_id=None, platform=True, user_id=5)
        assert ctx.platform is True
        assert ctx.allow_cross_tenant is True

    async def test_platform_repo_can_query_all_campuses(self, db_session: AsyncSession):
        """A platform-authorized repository can see all campuses."""
        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="PLAT001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="PLAT002", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(
            db_session, TenantContext(campus_id=None, platform=True, user_id=5)
        )
        rows, total = await repo._list_by_tenant(Student)
        assert total == 2

    async def test_unscoped_non_platform_repo_cannot_query(self, db_session: AsyncSession):
        """An unscoped, non-platform repository must be denied."""
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="UNSC001", campus_id=1),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(
            db_session, TenantContext(campus_id=None, platform=False, user_id=5)
        )
        with pytest.raises(AuthorizationError):
            await repo.scoped_query(Student)
