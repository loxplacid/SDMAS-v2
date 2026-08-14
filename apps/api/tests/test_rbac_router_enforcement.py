"""Regression tests for router-level RBAC enforcement.

Background
----------
The permission system (``ROLE_PERMISSIONS`` in
``app.domains.auth.permissions``) defines what each role may do, but
several routers enforced only a *tenant context* and never a role or
permission.  That let any authenticated campus member — including a
``student`` or ``parent`` — mutate academic structure, record attendance,
and enumerate every student's PII:

* ``academic/router.py``    — create/update/delete classes, sections,
  enrollments, terms, subjects, teachers, teacher-assignments
* ``attendance/router.py``  — record and update attendance records
* ``student/router.py``     — list / read any student in the campus
* ``auth/admin_router.py``  — ``POST /admin/users/{id}/roles`` accepted
  arbitrary role codes (latent ``platform_admin`` escalation)
* ``reports/router.py``     — staff could export PII/payments and read
  financial reports without any fee/export permission
* ``fees/router.py``        — read endpoints were tenant-only, so staff
  (zero fee permissions) could read the whole fee ledger
* ``cases/router.py``       — ``/bulk/*`` routes were shadowed by the
  ``/{case_id}/*`` family (bulk operations unreachable)

These tests pin the fixes: low-privilege roles are denied each operation
with 403 (or 422 for invalid role codes), while admin/principal/
accountant retain their legitimate access.

Frontend hiding is not authorization — these assertions run against the
real FastAPI routers through the live ASGI app.
"""

from __future__ import annotations

import base64
import json as _json
from collections.abc import AsyncGenerator
from datetime import date
from typing import AsyncGenerator as AsyncGeneratorType

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domains.academic.models import AcademicYear, Class, Enrollment, Section
from app.domains.auth.models import Permission, Role, User, UserSchoolMembership
from app.domains.auth.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.domains.auth.security import hash_password
from app.domains.institution.models import Campus, Institution
from app.domains.student.models import Student
from app.infrastructure.database import Base, get_session

_TEST_DB = "sqlite+aiosqlite:///:memory:"

#: Schema-valid payloads — the permission dependency fires before any
#: service logic, so these never need to reference real seed rows for
#: the *denied* assertions.
CLASS_PAYLOAD = {"name": "Grade 10", "academic_year_id": 1}
SECTION_PAYLOAD = {"name": "A", "class_id": 1}
SUBJECT_PAYLOAD = {"name": "Mathematics", "code": "MATH"}
TEACHER_PAYLOAD = {
    "first_name": "Ada", "last_name": "Lovelace", "employee_number": "T-001"
}
YEAR_PAYLOAD = {
    "name": "Academic Year 2026",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
}
ATTENDANCE_PAYLOAD = {
    "student_id": 1,
    "academic_year_id": 1,
    "class_id": 1,
    "section_id": 1,
    "attendance_date": "2026-01-15",
    "status": "present",
}
ATTENDANCE_UPDATE_PAYLOAD = {"status": "absent"}


def _forge_alg_none_token(sub: str = "1") -> str:
    """Hand-craft an ``alg: none`` JWT (unsigned).

    The installed jose build refuses to *mint* algorithm ``none`` tokens
    (``JWSError: Algorithm none not supported``), so the forgery is built
    by hand: base64url header + payload with an empty signature.  The
    application must reject it regardless.
    """
    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = b64url(_json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(_json.dumps({"sub": sub, "type": "access"}).encode())
    return f"{header}.{payload}."


@pytest_asyncio.fixture
async def rbac_client() -> AsyncGenerator[AsyncClient, None]:
    """App client seeded with one user per role (campus 1) plus the
    minimal academic rows needed for positive-path checks."""
    from app.main import app

    engine = create_async_engine(_TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with factory() as seed:
        institution = Institution(name="RBAC District", code="RBAC-DIST")
        seed.add(institution)
        await seed.flush()
        campus_a = Campus(
            institution_id=institution.id, name="Campus A", code="CMP-A",
            status="active",
        )
        campus_b = Campus(
            institution_id=institution.id, name="Campus B", code="CMP-B",
            status="active",
        )
        seed.add_all([campus_a, campus_b])
        await seed.flush()

        users: list[tuple[str, str, str]] = [
            ("admin", "admin@rbac.test", "admin"),
            ("student.user", "student@rbac.test", "student"),
            ("teacher.user", "teacher@rbac.test", "teacher"),
            ("parent.user", "parent@rbac.test", "parent"),
            ("staff.user", "staff@rbac.test", "staff"),
            ("accountant.user", "accountant@rbac.test", "accountant"),
            ("principal.user", "principal@rbac.test", "principal"),
        ]
        created: dict[str, User] = {}
        for username, email, role in users:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password("RBACPass123!"),
                display_name=f"{role.title()} User",
                role=role,
                campus_id=campus_a.id,
                is_active=True,
            )
            seed.add(user)
            await seed.flush()
            seed.add(
                UserSchoolMembership(
                    user_id=user.id,
                    campus_id=campus_a.id,
                    role=role,
                    is_default=True,
                    is_active=True,
                )
            )
            created[role] = user

        year = AcademicYear(
            name="AY 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            campus_id=campus_a.id,
        )
        seed.add(year)
        await seed.flush()
        cls = Class(name="Grade 10", academic_year_id=year.id, campus_id=campus_a.id)
        seed.add(cls)
        await seed.flush()
        section = Section(name="A", class_id=cls.id, campus_id=campus_a.id)
        seed.add(section)
        await seed.flush()
        student = Student(
            first_name="Grace", last_name="Hopper",
            student_number="RBAC-0001", campus_id=campus_a.id,
        )
        seed.add(student)
        await seed.flush()
        seed.add(
            Enrollment(
                student_id=student.id,
                academic_year_id=year.id,
                class_id=cls.id,
                section_id=section.id,
                campus_id=campus_a.id,
            )
        )

        # Roles/permissions mirror the production seed: DB-backed role
        # lookups (e.g. ``set_user_roles``) require real Role rows.
        permissions = {
            code: Permission(code=code, description=code)
            for code in ALL_PERMISSIONS
        }
        seed.add_all(permissions.values())
        await seed.flush()
        for code, perm_codes in ROLE_PERMISSIONS.items():
            seed.add(
                Role(
                    code=code,
                    label=code.title(),
                    description=f"Seed {code}",
                    is_system=True,
                    permissions=[permissions[p] for p in perm_codes],
                )
            )
        await seed.commit()

    async def override_get_session() -> AsyncGeneratorType[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


async def _headers(client: AsyncClient, username: str) -> dict[str, str]:
    resp = await client.post(
        "/auth/login",
        json={"login": username, "password": "RBACPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# Academic structure — student must be denied all mutations
# =====================================================================


class TestAcademicPermissionEnforcement:
    async def test_student_cannot_create_class(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.post("/api/classes", json=CLASS_PAYLOAD, headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_student_cannot_update_class(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.patch("/api/classes/1", json={"name": "Hacked"}, headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_student_cannot_delete_class(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.delete("/api/classes/1", headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_student_cannot_create_section_or_subject_or_teacher(
        self, rbac_client: AsyncClient
    ) -> None:
        headers = await _headers(rbac_client, "student.user")
        for path, payload in (
            ("/api/sections", SECTION_PAYLOAD),
            ("/api/subjects", SUBJECT_PAYLOAD),
            ("/api/teachers", TEACHER_PAYLOAD),
            ("/api/academic-years", YEAR_PAYLOAD),
        ):
            resp = await rbac_client.post(path, json=payload, headers=headers)
            assert resp.status_code == 403, f"{path}: {resp.text}"

    async def test_student_cannot_create_enrollment(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.post(
            "/api/enrollments",
            json={"student_id": 1, "class_id": 1, "academic_year_id": 1},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    async def test_admin_can_create_class(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.post(
            "/api/classes", json={"name": "Grade 11", "academic_year_id": 1}, headers=headers
        )
        assert resp.status_code == 201, resp.text

    async def test_parent_cannot_create_class(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "parent.user")
        resp = await rbac_client.post("/api/classes", json=CLASS_PAYLOAD, headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_staff_cannot_create_class(self, rbac_client: AsyncClient) -> None:
        # Matrix: staff holds academic.view only — creating structure is a
        # leadership (admin/principal) operation.
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.post("/api/classes", json=CLASS_PAYLOAD, headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_principal_can_create_class(self, rbac_client: AsyncClient) -> None:
        # Matrix: principal holds academic.create/update — leadership can
        # shape the academic structure.
        headers = await _headers(rbac_client, "principal.user")
        resp = await rbac_client.post(
            "/api/classes", json={"name": "Grade 12", "academic_year_id": 1}, headers=headers
        )
        assert resp.status_code == 201, resp.text


# =====================================================================
# Attendance — student may view but never record or amend
# =====================================================================


class TestAttendancePermissionEnforcement:
    async def test_student_cannot_record_attendance(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.post("/attendance", json=ATTENDANCE_PAYLOAD, headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_student_cannot_update_attendance(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.patch(
            "/attendance/1", json=ATTENDANCE_UPDATE_PAYLOAD, headers=headers
        )
        assert resp.status_code == 403, resp.text

    async def test_student_can_view_attendance(self, rbac_client: AsyncClient) -> None:
        # ``student`` holds attendance.view — reads must not be blocked.
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.get("/attendance", headers=headers)
        assert resp.status_code == 200, resp.text

    async def test_admin_can_record_attendance(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.post("/attendance", json=ATTENDANCE_PAYLOAD, headers=headers)
        assert resp.status_code == 201, resp.text

    async def test_teacher_can_record_attendance(self, rbac_client: AsyncClient) -> None:
        # ``teacher`` holds attendance.record — legitimate workflow preserved.
        headers = await _headers(rbac_client, "teacher.user")
        resp = await rbac_client.post("/attendance", json=ATTENDANCE_PAYLOAD, headers=headers)
        assert resp.status_code == 201, resp.text

    async def test_staff_can_record_attendance(self, rbac_client: AsyncClient) -> None:
        # ``staff`` holds attendance.record too — the other primary recorder.
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.post("/attendance", json=ATTENDANCE_PAYLOAD, headers=headers)
        assert resp.status_code == 201, resp.text

    async def test_parent_cannot_record_attendance(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "parent.user")
        resp = await rbac_client.post("/attendance", json=ATTENDANCE_PAYLOAD, headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_parent_can_view_attendance(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "parent.user")
        resp = await rbac_client.get("/attendance", headers=headers)
        assert resp.status_code == 200, resp.text

    async def test_principal_is_attendance_view_only(self, rbac_client: AsyncClient) -> None:
        # Matrix: principal holds attendance.view only — leadership overview,
        # not data entry.  Writes must 403 while reads stay open.
        write_headers = await _headers(rbac_client, "principal.user")
        resp = await rbac_client.post("/attendance", json=ATTENDANCE_PAYLOAD, headers=write_headers)
        assert resp.status_code == 403, resp.text
        read_headers = await _headers(rbac_client, "principal.user")
        resp = await rbac_client.get("/attendance", headers=read_headers)
        assert resp.status_code == 200, resp.text


# =====================================================================
# Students — PII enumeration must require students.view
# =====================================================================


class TestStudentListingPermissionEnforcement:
    async def test_student_role_cannot_list_students(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.get("/students", headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_student_role_cannot_read_another_student(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.get("/students/1", headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_admin_can_list_students(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.get("/students", headers=headers)
        assert resp.status_code == 200, resp.text

    async def test_teacher_can_list_students(self, rbac_client: AsyncClient) -> None:
        # ``teacher`` holds students.view — legitimately needs the roster.
        headers = await _headers(rbac_client, "teacher.user")
        resp = await rbac_client.get("/students", headers=headers)
        assert resp.status_code == 200, resp.text


# =====================================================================
# Admin user management — role-code validation closes the escalation
# =====================================================================


class TestAdminRoleAssignmentValidation:
    async def test_platform_admin_role_code_rejected(
        self, rbac_client: AsyncClient
    ) -> None:
        headers = await _headers(rbac_client, "admin")
        # Create a target user through the API (pinned to campus 1).
        create = await rbac_client.post(
            "/admin/users",
            json={
                "email": "victim@rbac.test",
                "username": "victim.user",
                "password": "RBACPass123!",
                "display_name": "Victim User",
            },
            headers=headers,
        )
        assert create.status_code == 201, create.text
        user_id = create.json()["id"]

        resp = await rbac_client.post(
            f"/admin/users/{user_id}/roles", json=["platform_admin"], headers=headers
        )
        assert resp.status_code == 422, resp.text

    async def test_unknown_role_code_rejected(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "admin")
        create = await rbac_client.post(
            "/admin/users",
            json={
                "email": "victim2@rbac.test",
                "username": "victim2.user",
                "password": "RBACPass123!",
                "display_name": "Victim Two",
            },
            headers=headers,
        )
        user_id = create.json()["id"]
        resp = await rbac_client.post(
            f"/admin/users/{user_id}/roles", json=["superuser"], headers=headers
        )
        assert resp.status_code == 422, resp.text

    async def test_tenant_role_code_still_assignable(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "admin")
        create = await rbac_client.post(
            "/admin/users",
            json={
                "email": "victim3@rbac.test",
                "username": "victim3.user",
                "password": "RBACPass123!",
                "display_name": "Victim Three",
            },
            headers=headers,
        )
        user_id = create.json()["id"]
        resp = await rbac_client.post(
            f"/admin/users/{user_id}/roles", json=["staff"], headers=headers
        )
        assert resp.status_code == 200, resp.text


# =====================================================================
# Reports / finance / exports / bulk ops — staff has NO fee or export
# permissions in the matrix, so every one of these must be denied.
# =====================================================================


class TestReportsAndFinancePermissionEnforcement:
    async def test_staff_cannot_export_students(self, rbac_client: AsyncClient) -> None:
        # students.export = admin only; staff previously could export all PII.
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.get("/api/reports/export/students", headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_staff_cannot_export_payments(self, rbac_client: AsyncClient) -> None:
        # fees.export = admin/accountant; staff previously could export
        # the full payment ledger.
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.get("/api/reports/export/payments", headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_staff_cannot_read_financial_reports(self, rbac_client: AsyncClient) -> None:
        # fees.view is NOT granted to staff — collection/outstanding/receipts
        # were all previously readable by staff.
        headers = await _headers(rbac_client, "staff.user")
        for path in (
            "/api/reports/fees/collection?academic_year_id=1",
            "/api/reports/fees/outstanding?academic_year_id=1",
            "/api/reports/receipts/1",
            "/api/fees/dues",
            "/api/fees/payments",
            "/api/fees/structures",
            "/api/fees/students/1/summary?academic_year_id=1",
        ):
            resp = await rbac_client.get(path, headers=headers)
            assert resp.status_code == 403, f"{path}: {resp.text}"

    async def test_staff_cannot_bulk_operations(self, rbac_client: AsyncClient) -> None:
        # batch/enroll requires academic.create (admin/principal);
        # batch/fee-dues requires fees.create (admin/accountant).
        headers = await _headers(rbac_client, "staff.user")
        enroll = await rbac_client.post(
            "/api/reports/batch/enroll",
            json={"academic_year_id": 1, "enrollments": []},
            headers=headers,
        )
        assert enroll.status_code == 403, enroll.text
        dues = await rbac_client.post(
            "/api/reports/batch/fee-dues",
            json={"academic_year_id": 1, "student_ids": [1]},
            headers=headers,
        )
        assert dues.status_code == 403, dues.text

    async def test_teacher_cannot_read_payments(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "teacher.user")
        resp = await rbac_client.get("/api/fees/payments", headers=headers)
        assert resp.status_code == 403, resp.text

    async def test_staff_can_export_attendance(self, rbac_client: AsyncClient) -> None:
        # attendance.export IS granted to staff — legitimate workflow kept.
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.get("/api/reports/export/attendance", headers=headers)
        assert resp.status_code == 200, resp.text

    async def test_staff_can_read_attendance_reports(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.get(
            "/api/reports/attendance/class/1?academic_year_id=1", headers=headers
        )
        assert resp.status_code == 200, resp.text

    async def test_accountant_can_export_payments(self, rbac_client: AsyncClient) -> None:
        # fees.export IS granted to accountant — finance workflow preserved.
        headers = await _headers(rbac_client, "accountant.user")
        resp = await rbac_client.get("/api/reports/export/payments", headers=headers)
        assert resp.status_code == 200, resp.text

    async def test_accountant_can_read_fee_data(self, rbac_client: AsyncClient) -> None:
        # fees.view IS granted to accountant.
        headers = await _headers(rbac_client, "accountant.user")
        resp = await rbac_client.get("/api/fees/payments", headers=headers)
        assert resp.status_code == 200, resp.text

    async def test_student_can_read_own_fee_data(self, rbac_client: AsyncClient) -> None:
        # fees.view IS granted to student/parent — the portal flow stays open.
        headers = await _headers(rbac_client, "student.user")
        resp = await rbac_client.get("/api/fees/dues", headers=headers)
        assert resp.status_code == 200, resp.text


# =====================================================================
# Cases bulk operations — leadership (admin/principal) only.
# The /bulk/* routes must not be shadowed by the /{case_id}/* family.
# =====================================================================


class TestCaseBulkOperationPermissionEnforcement:
    async def test_staff_cannot_bulk_assign_cases(self, rbac_client: AsyncClient) -> None:
        headers = await _headers(rbac_client, "staff.user")
        resp = await rbac_client.post(
            "/api/cases/bulk/assign",
            json={"case_ids": [1], "assignee_id": 1},
            headers=headers,
        )
        # 403 from the leadership role gate — NOT a 422 from the shadowed
        # ``/{case_id}/assign`` route (regression: bulk routes must win).
        assert resp.status_code == 403, resp.text

    async def test_admin_can_reach_bulk_assign(self, rbac_client: AsyncClient) -> None:
        # Permission gate passes for admin; with correct route ordering the
        # bulk endpoint executes and reports the missing case as skipped.
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.post(
            "/api/cases/bulk/assign",
            json={"case_ids": [1], "assignee_id": 1},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["updated"] == [] and body["skipped"] == 1, body


# =====================================================================
# Tenant management — platform-gated creates, tenant-scoped campus CRUD
# =====================================================================


class TestTenantManagementPermissionEnforcement:
    async def test_tenant_admin_cannot_create_institution(self, rbac_client: AsyncClient) -> None:
        # Creating an institution is a PLATFORM operation; a tenant admin
        # must never mint new tenants.
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.post(
            "/api/institution/institutions",
            json={"name": "Rogue District", "code": "ROGUE"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    async def test_tenant_admin_cannot_create_campus_for_other_institution(
        self, rbac_client: AsyncClient
    ) -> None:
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.post(
            "/api/institution/campuses",
            json={"institution_id": 999, "name": "Foreign", "code": "FRN"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    async def test_tenant_admin_can_create_campus_in_own_institution(
        self, rbac_client: AsyncClient
    ) -> None:
        headers = await _headers(rbac_client, "admin")
        resp = await rbac_client.post(
            "/api/institution/campuses",
            json={"institution_id": 1, "name": "Campus C", "code": "CMP-C"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text


# =====================================================================
# Session & token security — stale sessions, token manipulation
# =====================================================================


class TestSessionAndTokenSecurity:
    async def test_alg_none_token_rejected(self, rbac_client: AsyncClient) -> None:
        forged = _forge_alg_none_token()
        resp = await rbac_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {forged}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_alg_none_token_rejected_on_protected_route(
        self, rbac_client: AsyncClient
    ) -> None:
        forged = _forge_alg_none_token()
        resp = await rbac_client.get(
            "/api/classes", headers={"Authorization": f"Bearer {forged}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_refresh_token_cannot_be_used_as_bearer(self, rbac_client: AsyncClient) -> None:
        login = await rbac_client.post(
            "/auth/login", json={"login": "staff.user", "password": "RBACPass123!"}
        )
        assert login.status_code == 200, login.text
        refresh = login.json()["refresh_token"]
        resp = await rbac_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {refresh}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_deactivated_users_token_is_rejected(self, rbac_client: AsyncClient) -> None:
        admin_headers = await _headers(rbac_client, "admin")
        create = await rbac_client.post(
            "/admin/users",
            json={
                "email": "doomed@rbac.test",
                "username": "doomed.user",
                "password": "RBACPass123!",
                "display_name": "Doomed User",
            },
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        user_id = create.json()["id"]

        victim_login = await rbac_client.post(
            "/auth/login", json={"login": "doomed.user", "password": "RBACPass123!"}
        )
        assert victim_login.status_code == 200, victim_login.text
        victim_token = victim_login.json()["access_token"]

        deactivate = await rbac_client.patch(
            f"/admin/users/{user_id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert deactivate.status_code == 200, deactivate.text

        resp = await rbac_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {victim_token}"}
        )
        assert resp.status_code == 401, resp.text
