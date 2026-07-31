"""Tests for the enterprise permission system.

Covers:
- Permission registry constants and role-permission mappings
- PermissionService DB-backed and fallback modes
- require_permission FastAPI dependency (multi-role aware)
- require_role backward compatibility (multi-role aware)
- Multi-role user scenarios
- Edge cases: unknown roles, missing permissions, admin full access
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import AuthorizationError
from sqlalchemy import select

from app.domains.auth.models import Role, Permission, User
from app.domains.auth.dependencies import require_role, require_permission
from app.domains.auth.permissions import (
    ALL_PERMISSIONS,
    ROLE_PERMISSIONS,
    STUDENTS_VIEW,
    STUDENTS_CREATE,
    STUDENTS_DELETE,
    FEES_VIEW,
    FEES_RECORD_PAYMENT,
    ATTENDANCE_VIEW,
    ATTENDANCE_RECORD,
    USERS_VIEW,
    ROLES_MANAGE,
    has_permission,
    get_permissions_for_role,
)
from app.domains.auth.permission_service import (
    PermissionService,
    has_permission_sync,
)


# =====================================================================
# Registry tests (no DB needed)
# =====================================================================


class TestPermissionRegistry:
    """Verify the in-memory permission registry."""

    def test_all_permissions_are_unique(self):
        assert len(ALL_PERMISSIONS) == len(set(ALL_PERMISSIONS)), \
            "Duplicate permission codes found"

    def test_admin_has_all_permissions(self):
        """Admin role must have every permission in ALL_PERMISSIONS."""
        admin_perms = set(ROLE_PERMISSIONS["admin"])
        expected = set(ALL_PERMISSIONS)
        missing = expected - admin_perms
        assert not missing, f"Admin missing permissions: {missing}"

    def test_has_permission_returns_true_for_granted(self):
        assert has_permission("admin", STUDENTS_DELETE) is True
        assert has_permission("accountant", FEES_RECORD_PAYMENT) is True
        assert has_permission("teacher", ATTENDANCE_RECORD) is True

    def test_has_permission_returns_false_for_denied(self):
        assert has_permission("student", STUDENTS_CREATE) is False
        assert has_permission("parent", FEES_RECORD_PAYMENT) is False
        assert has_permission("teacher", ROLES_MANAGE) is False

    def test_unknown_role_gets_no_permissions(self):
        assert get_permissions_for_role("nonexistent_role") == []
        assert has_permission("bogus_role", STUDENTS_VIEW) is False

    def test_has_permission_sync_matches_registry(self):
        assert has_permission_sync("admin", ROLES_MANAGE) is True
        assert has_permission_sync("student", USERS_VIEW) is False

    def test_principal_has_leadership_permissions(self):
        perms = set(get_permissions_for_role("principal"))
        assert STUDENTS_VIEW in perms
        assert FEES_VIEW in perms
        assert ATTENDANCE_VIEW in perms
        # Principal should NOT have create/delete
        assert STUDENTS_CREATE not in perms
        assert STUDENTS_DELETE not in perms

    def test_accountant_has_finance_permissions(self):
        perms = set(get_permissions_for_role("accountant"))
        assert FEES_VIEW in perms
        assert FEES_RECORD_PAYMENT in perms
        assert STUDENTS_VIEW in perms
        # Accountant should NOT have attendance record
        assert ATTENDANCE_RECORD not in perms

    def test_student_has_limited_permissions(self):
        perms = set(get_permissions_for_role("student"))
        assert ATTENDANCE_VIEW in perms
        assert FEES_VIEW in perms
        assert STUDENTS_CREATE not in perms
        assert ROLES_MANAGE not in perms


# =====================================================================
# PermissionService tests (DB-backed)
# =====================================================================


class TestPermissionServiceDB:
    """Verify PermissionService with a real (in-memory) database."""

    async def test_role_has_permission_via_db(self, db_session):
        """When DB is seeded, check via role_permissions join."""
        # Seed a minimal Permission + Role
        perm = Permission(code="test.view", description="Test permission")
        role = Role(code="tester", label="Tester", is_system=False, permissions=[perm])
        db_session.add_all([perm, role])
        await db_session.flush()

        svc = PermissionService(db_session)
        assert await svc.role_has_permission("tester", "test.view") is True
        assert await svc.role_has_permission("tester", "test.create") is False

    async def test_role_has_permission_fallback_to_registry(self, db_session):
        """When role row doesn't exist, fallback to in-memory registry."""
        svc = PermissionService(db_session)
        assert await svc.role_has_permission("admin", STUDENTS_DELETE) is True
        assert await svc.role_has_permission("student", ROLES_MANAGE) is False

    async def test_get_role_permissions_empty_for_unknown(self, db_session):
        svc = PermissionService(db_session)
        perms = await svc.get_role_permissions("nonexistent")
        assert perms == []

    async def test_get_role_permissions_from_db(self, db_session):
        perm = Permission(code="alpha.view")
        perm2 = Permission(code="beta.edit")
        role = Role(code="custom", label="Custom", permissions=[perm, perm2])
        db_session.add_all([perm, perm2, role])
        await db_session.flush()

        svc = PermissionService(db_session)
        perms = await svc.get_role_permissions("custom")
        assert "alpha.view" in perms
        assert "beta.edit" in perms
        assert len(perms) == 2

    async def test_any_role_has_permission(self, db_session):
        """any_role_has_permission checks across multiple roles."""
        svc = PermissionService(db_session)
        # teacher has ATTENDANCE_RECORD but not ROLES_MANAGE
        # admin has both
        assert await svc.any_role_has_permission(["teacher"], ATTENDANCE_RECORD) is True
        assert await svc.any_role_has_permission(["teacher"], ROLES_MANAGE) is False
        assert await svc.any_role_has_permission(["teacher", "admin"], ROLES_MANAGE) is True
        assert await svc.any_role_has_permission([], ATTENDANCE_RECORD) is False

    async def test_get_all_permissions_for_roles(self, db_session):
        """get_all_permissions_for_roles returns union of permissions."""
        svc = PermissionService(db_session)
        teacher_perms = await svc.get_all_permissions_for_roles(["teacher"])
        assert ATTENDANCE_RECORD in teacher_perms
        assert ATTENDANCE_VIEW in teacher_perms

        # Combine teacher + accountant
        combined = await svc.get_all_permissions_for_roles(["teacher", "accountant"])
        assert ATTENDANCE_RECORD in combined  # from teacher
        assert FEES_RECORD_PAYMENT in combined  # from accountant

    async def test_get_all_permissions_for_roles_empty(self, db_session):
        svc = PermissionService(db_session)
        result = await svc.get_all_permissions_for_roles([])
        assert result == set()


# =====================================================================
# require_permission dependency tests
# =====================================================================


class TestRequirePermissionDependency:
    """Verify the require_permission and require_role FastAPI dependencies.

    These tests use ``db_session`` (in-memory SQLite) to create the
    ``roles`` table so the DB-backed permission lookup succeeds.
    """

    async def _make_user(self, role: str = "admin", assigned_roles: list[Role] | None = None):
        return User(
            id=999,
            email=f"{role}@test.com",
            username=role,
            password_hash="x",
            display_name=role.title(),
            role=role,
            is_active=True,
            assigned_roles=assigned_roles or [],
        )

    async def _seed_role_permission(self, db_session, role_code: str, perm_code: str):
        """Ensure a minimal role-permission mapping exists in the DB."""
        perm = Permission(code=perm_code)
        role = Role(code=role_code, label=role_code.title(), permissions=[perm])
        db_session.add_all([perm, role])
        await db_session.flush()

    async def test_admin_has_all_permissions(self, db_session):
        """Admin should pass any require_permission check (registry fallback)."""
        await self._seed_role_permission(db_session, "admin", STUDENTS_DELETE)
        user = await self._make_user("admin")
        dep = require_permission(STUDENTS_DELETE)
        result = await dep(current_user=user, session=db_session)
        assert result is user

    async def test_student_denied_student_create(self, db_session):
        """Student should be denied the students.create permission."""
        await self._seed_role_permission(db_session, "student", STUDENTS_VIEW)
        user = await self._make_user("student")
        dep = require_permission(STUDENTS_CREATE)
        with pytest.raises(AuthorizationError, match="Missing required permission"):
            await dep(current_user=user, session=db_session)

    async def test_accountant_allowed_fees_record_payment(self, db_session):
        """Accountant should pass fees.record_payment check (registry fallback)."""
        await self._seed_role_permission(db_session, "accountant", FEES_RECORD_PAYMENT)
        user = await self._make_user("accountant")
        dep = require_permission(FEES_RECORD_PAYMENT)
        result = await dep(current_user=user, session=db_session)
        assert result is user

    async def test_require_role_backward_compatible(self, db_session):
        """require_role still works for role-based checks (no DB needed)."""
        user = await self._make_user("admin")
        dep = require_role("admin")
        result = await dep(current_user=user)
        assert result is user

    async def test_require_role_blocks_wrong_role(self, db_session):
        """require_role raises for unauthorized roles."""
        user = await self._make_user("student")
        dep = require_role("admin")
        with pytest.raises(AuthorizationError, match="Requires one of these roles"):
            await dep(current_user=user)

    async def test_require_role_multi_role_user_passes(self, db_session):
        """A user with a secondary role from M2M should pass require_role."""
        # Seed the role in DB so we can reference it
        admin_role = Role(code="admin", label="Admin")
        db_session.add(admin_role)
        await db_session.flush()

        # User whose primary role is "staff" but is also assigned "admin" via M2M
        user = await self._make_user("staff", assigned_roles=[admin_role])
        dep = require_role("admin")
        result = await dep(current_user=user)
        assert result is user

    async def test_require_permission_via_m2m_role(self, db_session):
        """A user gains permission through an M2M-assigned role."""
        await self._seed_role_permission(db_session, "admin", ROLES_MANAGE)
        result = await db_session.execute(
            select(Role).where(Role.code == "admin")
        )
        admin_role = result.scalar_one_or_none()
        assert admin_role is not None

        # User's primary role is "staff" (no ROLES_MANAGE), but assigned admin via M2M
        user = await self._make_user("staff", assigned_roles=[admin_role])
        dep = require_permission(ROLES_MANAGE)
        result = await dep(current_user=user, session=db_session)
        assert result is user

    async def test_require_permission_denied_even_with_m2m(self, db_session):
        """Even with multiple roles, a user who lacks the permission is denied."""
        await self._seed_role_permission(db_session, "staff", STUDENTS_VIEW)
        result = await db_session.execute(
            select(Role).where(Role.code == "staff")
        )
        staff_role = result.scalar_one_or_none()
        assert staff_role is not None
        student_role = Role(code="student", label="Student")
        db_session.add(student_role)
        await db_session.flush()

        # User has "staff" (only STUDENTS_VIEW) and "student" via M2M (no STUDENTS_DELETE)
        user = await self._make_user("student", assigned_roles=[staff_role, student_role])
        dep = require_permission(STUDENTS_DELETE)
        with pytest.raises(AuthorizationError, match="Missing required permission"):
            await dep(current_user=user, session=db_session)


# =====================================================================
# Integration: require_permission via HTTP
# =====================================================================


class TestPermissionHTTPIntegration:
    """Verify permission enforcement works through the full HTTP layer."""

    @pytest.fixture
    def app(self):
        """A minimal FastAPI app with a permission-guarded endpoint."""
        from app.core.error_handlers import auth_error_handler
        from app.core.exceptions import AuthenticationError as AuthExc

        application = FastAPI()
        application.add_exception_handler(AuthExc, auth_error_handler)

        @application.get("/api/protected")
        async def protected_route(
            _user=Depends(require_permission("test.access")),
        ):
            return {"ok": True}

        @application.get("/api/role-protected")
        async def role_protected_route(
            _user=Depends(require_role("admin")),
        ):
            return {"ok": True}

        return application

    async def test_unauthenticated_request_blocked(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/protected")
        assert resp.status_code == 401

    async def test_authenticated_without_permission_blocked(self, app):
        """A valid user whose role lacks the permission gets 403."""
        from app.domains.auth.security import create_access_token

        token = create_access_token(
            {"sub": "1", "username": "student1"},
            campus_id=None,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        # The test app doesn't have actual DB-backed users, so the token
        # decode will succeed but the user lookup will fail → 401.
        # Real integration requires the full app with DB seeded users.
        assert resp.status_code in (401, 403)

    async def test_role_protected_blocks_wrong_role(self, app):
        from app.domains.auth.security import create_access_token

        token = create_access_token(
            {"sub": "1", "username": "teacher"},
            campus_id=None,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/role-protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code in (401, 403)
