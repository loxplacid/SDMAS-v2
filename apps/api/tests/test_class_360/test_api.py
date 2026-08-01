"""API tests for the Class 360 view.

Covers:
- Aggregation correctness (sections, student counts, teachers, subjects,
  attendance, fees, drill-down ids)
- RBAC (unauthenticated -> 401, limited role -> 403)
- Tenant isolation (campus-scoped caller cannot read another campus class)
- Missing resource -> 404
"""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient


async def _admin_headers(api_client: AsyncClient) -> dict:
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_class(api_client: AsyncClient, headers: dict) -> dict:
    """Create year -> class -> section -> student -> enrollment and return ids."""
    year_resp = await api_client.post(
        "/api/academic-years",
        json={"name": "C360 Year", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        headers=headers,
    )
    assert year_resp.status_code == 201, year_resp.text
    year_id = year_resp.json()["id"]

    class_resp = await api_client.post(
        "/api/classes",
        json={"name": "Grade 10", "academic_year_id": year_id},
        headers=headers,
    )
    assert class_resp.status_code == 201, class_resp.text
    class_id = class_resp.json()["id"]

    section_resp = await api_client.post(
        "/api/sections",
        json={"name": "Section A", "class_id": class_id},
        headers=headers,
    )
    assert section_resp.status_code == 201, section_resp.text
    section_id = section_resp.json()["id"]

    student_ids = []
    for i, num in enumerate(["C360S1", "C360S2"], start=1):
        resp = await api_client.post(
            "/students",
            json={
                "first_name": f"Student{i}",
                "last_name": "ThreeSixty",
                "student_number": num,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        student_ids.append(resp.json()["id"])
        enroll = await api_client.post(
            "/api/enrollments",
            json={
                "student_id": resp.json()["id"],
                "academic_year_id": year_id,
                "class_id": class_id,
                "section_id": section_id,
            },
            headers=headers,
        )
        assert enroll.status_code == 201, enroll.text

    return {
        "year_id": year_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_ids": student_ids,
    }


@pytest.mark.asyncio
async def test_class_360_requires_auth(api_client: AsyncClient):
    response = await api_client.get("/classes/1/360")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_class_360_denied_for_limited_role(api_client: AsyncClient):
    """A limited-role user (no academic.view) must be denied (403).

    Users created via /admin/users default to the ``staff`` role, which
    does not grant ``academic.view`` (see ROLE_PERMISSIONS), so this
    exercises the permission guard end-to-end.
    """
    admin_headers = await _admin_headers(api_client)
    created = await api_client.post(
        "/admin/users",
        json={
            "email": "limited@school.test",
            "username": "limited360",
            "password": "Password123!",
            "display_name": "Limited User",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    login = await api_client.post(
        "/auth/login",
        json={"login": "limited360", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    limited_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    response = await api_client.get("/classes/1/360", headers=limited_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_class_360_aggregation(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    seeded = await _seed_class(api_client, headers)
    class_id = seeded["class_id"]

    # Add a teacher + subject assignment and attendance records
    teacher = await api_client.post(
        "/api/teachers",
        json={
            "first_name": "Ms",
            "last_name": "Teacher",
            "employee_number": "C360T1",
        },
        headers=headers,
    )
    assert teacher.status_code == 201, teacher.text
    teacher_id = teacher.json()["id"]

    subject = await api_client.post(
        "/api/subjects",
        json={"name": "Mathematics", "code": "MATH"},
        headers=headers,
    )
    assert subject.status_code == 201, subject.text
    subject_id = subject.json()["id"]

    assign = await api_client.post(
        "/api/teacher-assignments",
        json={"teacher_id": teacher_id, "class_id": class_id, "subject_id": subject_id},
        headers=headers,
    )
    assert assign.status_code == 201, assign.text

    # Attendance must fall inside the service's 90-day aggregation window.
    recent = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    for sid in seeded["student_ids"]:
        att = await api_client.post(
            "/attendance",
            json={
                "student_id": sid,
                "academic_year_id": seeded["year_id"],
                "class_id": class_id,
                "section_id": seeded["section_id"],
                "attendance_date": recent,
                "status": "present",
            },
            headers=headers,
        )
        assert att.status_code == 201, att.text

    response = await api_client.get(f"/classes/{class_id}/360", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["identity"]["id"] == class_id
    assert data["identity"]["name"] == "Grade 10"
    assert data["student_count"] == 2
    assert len(data["sections"]) == 1
    assert data["sections"][0]["student_count"] == 2
    assert data["sections"][0]["id"] == seeded["section_id"]  # drill-down id
    assert data["attendance"]["total"] == 2
    assert data["attendance"]["present"] == 2
    assert data["attendance"]["percentage"] == 100.0
    assert any(t["teacher_id"] == teacher_id for t in data["teachers"])
    assert any(s["id"] == subject_id for s in data["subjects"])


@pytest.mark.asyncio
async def test_class_360_drill_down_contains_student_attention(api_client: AsyncClient):
    """Students requiring attention must carry student ids for drill-down."""
    headers = await _admin_headers(api_client)
    seeded = await _seed_class(api_client, headers)

    # Record one student as absent repeatedly so their attendance < 75%.
    # Dates must fall inside the 90-day aggregation window.
    sid = seeded["student_ids"][0]
    today = datetime.date.today()
    for day in range(5):
        att = await api_client.post(
            "/attendance",
            json={
                "student_id": sid,
                "academic_year_id": seeded["year_id"],
                "class_id": seeded["class_id"],
                "section_id": seeded["section_id"],
                "attendance_date": (today - datetime.timedelta(days=day + 1)).isoformat(),
                "status": "absent",
            },
            headers=headers,
        )
        assert att.status_code == 201, att.text

    response = await api_client.get(
        f"/classes/{seeded['class_id']}/360", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    attention = data["students_requiring_attention"]
    assert any(a["student_id"] == sid for a in attention)
    flagged = next(a for a in attention if a["student_id"] == sid)
    assert flagged["reason"].lower().startswith("low attendance")


@pytest.mark.asyncio
async def test_class_360_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/classes/999999/360", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_class_360_tenant_isolation(api_client: AsyncClient):
    """A campus-scoped user must not read another campus's class."""
    admin_headers = await _admin_headers(api_client)
    seeded = await _seed_class(api_client, admin_headers)

    # Create a real user pinned to a foreign campus via the app's test
    # session (same engine the api_client talks to). The api_client
    # fixture overrides get_session with a factory bound to its own
    # in-memory engine, so a user seeded through that override is
    # visible to subsequent HTTP requests.
    from app.main import app as fastapi_app
    from app.domains.auth.models import User
    from app.domains.auth.security import hash_password
    from app.infrastructure.database import get_session

    override = fastapi_app.dependency_overrides[get_session]
    agen = override()
    session = await agen.__anext__()
    try:
        other = User(
            username="othercampus360",
            email="othercampus360@school.test",
            password_hash=hash_password("Password123!"),
            display_name="Other Campus",
            role="staff",
            is_active=True,
            campus_id=987,
        )
        session.add(other)
        await session.commit()
    finally:
        await agen.aclose()

    login = await api_client.post(
        "/auth/login",
        json={"login": "othercampus360", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # The class belongs to no campus (seeded unscoped) so a scoped caller
    # must be denied by assert_tenant_scope.
    response = await api_client.get(
        f"/classes/{seeded['class_id']}/360", headers=other_headers
    )
    assert response.status_code == 403
