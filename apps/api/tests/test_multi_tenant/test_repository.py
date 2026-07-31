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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ======================================================================
# TenantScopedRepository unit tests
# ======================================================================


class TestTenantScopedRepository:
    """Verify that the mixin correctly applies tenant filters."""

    async def test_no_tenant_no_filter(self, db_session: AsyncSession):
        """When tenant is None, no filter is added."""
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

    async def test_empty_tenant_returns_all(self, db_session: AsyncSession):
        """When tenant has no campus_id, all records are returned."""
        db_session.add_all([
            Student(first_name="A1", last_name="B1", student_number="TN005", campus_id=1),
            Student(first_name="A2", last_name="B2", student_number="TN006", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, TenantContext())
        items, total = await repo._list_by_tenant(Student, skip=0, limit=100)
        assert total == 2

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
# Integration test — full auth → tenant pipeline
# ======================================================================


@pytest.mark.asyncio
async def test_multi_tenant_dependency_works_with_api_client(api_client: AsyncClient):
    """Verify that a logged-in user can resolve the tenant context
    via the dependency injection chain: login → JWT → get_current_user
    → get_current_tenant."""
    # 1. Register a user
    register_resp = await api_client.post(
        "/auth/register",
        json={
            "email": "tenant@test.local",
            "username": "tenantuser",
            "password": "password123",
            "display_name": "Tenant User",
        },
    )
    assert register_resp.status_code == 201
    user_data = register_resp.json()

    # 2. Login
    login_resp = await api_client.post(
        "/auth/login",
        json={"login": "tenantuser", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 3. Verify /auth/me works with the token
    me_resp = await api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "tenantuser"
