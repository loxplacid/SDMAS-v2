"""Regression tests for the fail-closed tenant model and legacy NULL-campus data.

Two invariants are proven:

1. **Fail-closed tenant=None** — ``TenantScopedRepository(session, tenant=None)``
   is never treated as platform access; every scoped call raises
   ``AuthorizationError``.  Platform access requires an explicit platform
   context (``platform_context()`` / ``TenantContext(platform=True)``).

2. **Legacy NULL-campus isolation** — records whose ``campus_id`` is NULL
   (ambiguous ownership) are invisible to scoped tenants: repository
   queries and the class_360 / teacher_360 aggregation scope fragments
   never match ``campus_id IS NULL`` rows.  NULL is not an implicit
   authorization state.
"""

from __future__ import annotations

import pytest

from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext, platform_context
from app.multi_tenant.repository import TenantScopedRepository
from app.multi_tenant.models import platform_context


# ======================================================================
# Task 1 — explicit platform context helper
# ======================================================================


class TestPlatformContextHelper:
    def test_platform_context_is_explicitly_platform(self):
        ctx = platform_context()
        assert ctx.platform is True
        assert ctx.is_tenant_scoped is False
        assert ctx.allow_cross_tenant is True
        assert ctx.scope.value == "platform"

    def test_platform_context_keeps_user_id(self):
        ctx = platform_context(user_id=7)
        assert ctx.user_id == 7
        assert ctx.platform is True

    def test_platform_context_is_never_tenant_scoped(self):
        assert platform_context().campus_id is None


class TestRepositoryMisuseCannotBecomeGlobalAccess:
    """Repository misuse (missing tenant) must fail closed, never silently
    degrade to global visibility."""

    async def test_tenant_none_denied_for_tenant_owned(self, db_session):
        from app.core.exceptions import AuthorizationError

        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="FC001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="FC002", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, tenant=None)
        with pytest.raises(AuthorizationError):
            await repo.scoped_query(Student)
        with pytest.raises(AuthorizationError):
            await repo.scoped_count(Student)
        with pytest.raises(AuthorizationError):
            await repo._list_by_tenant(Student)

    async def test_explicit_platform_context_can_query_all(self, db_session):
        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="PLT001", campus_id=1),
            Student(first_name="C", last_name="D", student_number="PLT002", campus_id=2),
        ])
        await db_session.flush()

        repo = TenantScopedRepository(db_session, platform_context(user_id=1))
        items, total = await repo._list_by_tenant(Student)
        assert total == 2
        # get_by_id across campuses works for an explicit platform caller
        other = await repo.get_by_id(Student, 2)
        assert other is not None
        assert other.student_number == "PLT002"


# ======================================================================
# Task 2 — legacy NULL-campus rows never surface to scoped tenants
# ======================================================================


class TestLegacyNullCampusIsolation:
    async def test_null_campus_row_invisible_to_scoped_tenant(self, db_session):
        """A NULL-campus (legacy/ambiguous) row must never appear in a
        tenant-scoped list, while the same row remains visible to an
        explicit platform context."""
        db_session.add_all([
            Student(first_name="A", last_name="B", student_number="LG-A", campus_id=1),
            Student(first_name="L", last_name="EG", student_number="LG-NULL", campus_id=None),
        ])
        await db_session.flush()

        scoped = TenantScopedRepository(db_session, TenantContext(campus_id=1))
        items, total = await scoped._list_by_tenant(Student)
        assert total == 1
        assert [s.student_number for s in items] == ["LG-A"]

        # get_by_id on the NULL-campus row is a miss for the scoped tenant
        null_row = await scoped.get_by_id(Student, 2)
        assert null_row is None

        # Explicit platform context still sees the legacy row
        plat = TenantScopedRepository(db_session, platform_context())
        items, total = await plat._list_by_tenant(Student)
        assert total == 2

    def test_class360_scope_never_matches_null_campus(self):
        from app.domains.class_360.service import Class360Service

        svc = Class360Service.__new__(Class360Service)  # pure fragment method
        frag = svc._scope(1, "s")
        assert "IS NULL" not in frag.upper()
        assert "s.campus_id = :campus_id" in frag
        # Platform / unscoped caller: no restriction at all
        assert svc._scope(None, "s") == ""

    def test_teacher360_scope_never_matches_null_campus(self):
        from app.domains.teacher_360.service import Teacher360Service

        svc = Teacher360Service.__new__(Teacher360Service)
        frag = svc._scope(1, "ta")
        assert "IS NULL" not in frag.upper()
        assert "ta.campus_id = :campus_id" in frag
        assert svc._scope(None, "ta") == ""
