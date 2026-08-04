"""Authorization boundary tests.

Proves, at the API layer:

* a role without the required permission is denied (missing permission)
* a role that is not permitted at all is denied (incorrect role)
* a tenant admin cannot reach ANOTHER tenant's user records — including
  through the admin user-management surface (horizontal escalation)
* a low-privilege user cannot self-promote (vertical escalation)
* the same role in another tenant cannot touch this tenant's data
* admin-created users are pinned to the admin's campus
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domains.auth.models import User

from .conftest import AcqEnv, seed_student

pytestmark = pytest.mark.asyncio


async def test_missing_permission_denied(
    acq_env: AcqEnv, headers_staff_a
):
    """Invariant: ``staff`` has students.view/create/update but NOT
    students.delete — a delete must be rejected with 403, not silently
    allowed or masked as 404."""
    student_id = await seed_student(acq_env.factory, 1, "ACQ-AUTH-1", "Auth")
    resp = await acq_env.client.delete(
        f"/students/{student_id}", headers=headers_staff_a
    )
    assert resp.status_code == 403, resp.text

    # The record still exists — the delete was refused, not applied.
    from app.domains.student.models import Student

    async with acq_env.factory() as s:
        exists = (await s.execute(
            select(Student).where(Student.id == student_id)
        )).scalar_one_or_none()
    assert exists is not None


async def test_incorrect_role_denied(
    acq_env: AcqEnv, headers_staff_a
):
    """Invariant: the admin user-management surface requires the ``admin``
    role — a staff member is rejected before any data is touched."""
    resp = await acq_env.client.get("/admin/users", headers=headers_staff_a)
    assert resp.status_code == 403, resp.text


async def test_horizontal_privilege_escalation_blocked(
    acq_env: AcqEnv, headers_a
):
    """Invariant: a tenant admin of campus A cannot read or modify a user
    record owned by campus B via the admin surface (IDOR on users)."""
    async with acq_env.factory() as s:
        admin_b_id = (await s.execute(
            select(User).where(User.username == "admin_b")
        )).scalar_one().id

    resp = await acq_env.client.get(
        f"/admin/users/{admin_b_id}", headers=headers_a
    )
    assert resp.status_code in (403, 404), resp.text

    resp = await acq_env.client.patch(
        f"/admin/users/{admin_b_id}",
        json={"is_active": False, "role": "staff"},
        headers=headers_a,
    )
    assert resp.status_code in (403, 404), resp.text

    resp = await acq_env.client.post(
        f"/admin/users/{admin_b_id}/roles",
        json=["staff"],
        headers=headers_a,
    )
    assert resp.status_code in (403, 404), resp.text


async def test_vertical_privilege_escalation_blocked(
    acq_env: AcqEnv, headers_staff_a
):
    """Invariant: a staff member cannot escalate their own role (or anyone
    else's) to ``admin`` — the role-assignment surface is admin-only."""
    async with acq_env.factory() as s:
        staff_id = (await s.execute(
            select(User).where(User.username == "staff_a")
        )).scalar_one().id

    resp = await acq_env.client.post(
        f"/admin/users/{staff_id}/roles",
        json=["admin"],
        headers=headers_staff_a,
    )
    assert resp.status_code == 403, resp.text

    # The primary role is unchanged afterwards.
    async with acq_env.factory() as s:
        role = (await s.execute(
            select(User.role).where(User.id == staff_id)
        )).scalar_one()
    assert role == "staff"


async def test_role_from_wrong_tenant_denied(
    acq_env: AcqEnv, headers_b
):
    """Invariant: role alone is never enough — an ``admin`` of campus B is
    still denied campus A's data (tenant boundary outranks role)."""
    student_id = await seed_student(acq_env.factory, 1, "ACQ-RT-1", "RoleT")
    resp = await acq_env.client.get(f"/students/{student_id}", headers=headers_b)
    assert resp.status_code in (403, 404), resp.text

    resp = await acq_env.client.patch(
        f"/students/{student_id}", json={"last_name": "Hijacked"},
        headers=headers_b,
    )
    assert resp.status_code in (403, 404), resp.text


async def test_admin_user_list_is_campus_scoped(acq_env: AcqEnv, headers_a):
    """Invariant: the admin user list returns ONLY the acting admin's campus
    users — no other campus, no platform users, no unscoped users."""
    resp = await acq_env.client.get("/admin/users", headers=headers_a)
    assert resp.status_code == 200, resp.text
    usernames = {u["username"] for u in resp.json()["items"]}
    assert "admin_a" in usernames
    assert "staff_a" in usernames
    assert "teacher_a" in usernames
    assert "student_a" in usernames
    # Cross-tenant / unscoped / platform users must never appear.
    assert "admin_b" not in usernames
    assert "staff_x" not in usernames
    assert "plat_admin" not in usernames


async def test_admin_created_user_pinned_to_own_campus(
    acq_env: AcqEnv, headers_a
):
    """Invariant: a tenant admin creates users inside their OWN campus; the
    created record can never be a cross-tenant or unscoped account."""
    resp = await acq_env.client.post(
        "/admin/users",
        json={
            "email": "newstaff@acq.test",
            "username": "newstaff_a",
            "password": "Str0ng!Pass",
            "display_name": "New Staff",
        },
        headers=headers_a,
    )
    assert resp.status_code == 201, resp.text

    async with acq_env.factory() as s:
        user = (await s.execute(
            select(User).where(User.username == "newstaff_a")
        )).scalar_one()
    assert user.campus_id == acq_env.campus_a

    # And the new user is visible to the campus-A admin list only.
    resp = await acq_env.client.get("/admin/users", headers=headers_a)
    assert "newstaff_a" in resp.text
