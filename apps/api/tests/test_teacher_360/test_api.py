"""API tests for the Teacher 360 view.

Covers:
- Aggregation correctness (subjects, assignments, workload, attendance)
- RBAC (unauthenticated -> 401, limited role -> 403)
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


async def _seed_teacher(api_client: AsyncClient, headers: dict) -> dict:
    year_resp = await api_client.post(
        "/api/academic-years",
        json={"name": "T360 Year", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        headers=headers,
    )
    assert year_resp.status_code == 201, year_resp.text
    year_id = year_resp.json()["id"]

    class_resp = await api_client.post(
        "/api/classes",
        json={"name": "Grade 9", "academic_year_id": year_id},
        headers=headers,
    )
    assert class_resp.status_code == 201, class_resp.text
    class_id = class_resp.json()["id"]

    section_resp = await api_client.post(
        "/api/sections",
        json={"name": "Section B", "class_id": class_id},
        headers=headers,
    )
    assert section_resp.status_code == 201, section_resp.text
    section_id = section_resp.json()["id"]

    teacher_resp = await api_client.post(
        "/api/teachers",
        json={
            "first_name": "Prof",
            "last_name": "Algebra",
            "employee_number": "T360T1",
            "email": "algebra@school.test",
        },
        headers=headers,
    )
    assert teacher_resp.status_code == 201, teacher_resp.text
    teacher_id = teacher_resp.json()["id"]

    subject_resp = await api_client.post(
        "/api/subjects",
        json={"name": "Algebra", "code": "ALG"},
        headers=headers,
    )
    assert subject_resp.status_code == 201, subject_resp.text
    subject_id = subject_resp.json()["id"]

    assign_resp = await api_client.post(
        "/api/teacher-assignments",
        json={"teacher_id": teacher_id, "class_id": class_id, "subject_id": subject_id},
        headers=headers,
    )
    assert assign_resp.status_code == 201, assign_resp.text

    return {
        "year_id": year_id,
        "class_id": class_id,
        "section_id": section_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
    }


@pytest.mark.asyncio
async def test_teacher_360_requires_auth(api_client: AsyncClient):
    response = await api_client.get("/teachers/1/360")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_teacher_360_denied_for_limited_role(api_client: AsyncClient):
    """A limited-role user (no teachers.view) must be denied (403).

    Users created via /admin/users default to the ``staff`` role, which
    does not grant ``teachers.view`` (see ROLE_PERMISSIONS).
    """
    admin_headers = await _admin_headers(api_client)
    created = await api_client.post(
        "/admin/users",
        json={
            "email": "limited2@school.test",
            "username": "limitedt360",
            "password": "Password123!",
            "display_name": "Limited User 2",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    login = await api_client.post(
        "/auth/login",
        json={"login": "limitedt360", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    limited_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await api_client.get("/teachers/1/360", headers=limited_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_teacher_360_aggregation(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    seeded = await _seed_teacher(api_client, headers)

    # Record attendance in the teacher's section so the attendance summary
    # aggregates real data. Must fall inside the 90-day window.
    student = await api_client.post(
        "/students",
        json={
            "first_name": "Sally",
            "last_name": "Smith",
            "student_number": "T360S1",
        },
        headers=headers,
    )
    assert student.status_code == 201, student.text
    enroll = await api_client.post(
        "/api/enrollments",
        json={
            "student_id": student.json()["id"],
            "academic_year_id": seeded["year_id"],
            "class_id": seeded["class_id"],
            "section_id": seeded["section_id"],
        },
        headers=headers,
    )
    assert enroll.status_code == 201, enroll.text
    recent = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    att = await api_client.post(
        "/attendance",
        json={
            "student_id": student.json()["id"],
            "academic_year_id": seeded["year_id"],
            "class_id": seeded["class_id"],
            "section_id": seeded["section_id"],
            "attendance_date": recent,
            "status": "present",
        },
        headers=headers,
    )
    assert att.status_code == 201, att.text

    response = await api_client.get(
        f"/teachers/{seeded['teacher_id']}/360", headers=headers
    )
    assert response.status_code == 200
    data = response.json()

    assert data["profile"]["id"] == seeded["teacher_id"]
    assert data["profile"]["email"] == "algebra@school.test"
    assert any(
        s["subject_id"] == seeded["subject_id"] for s in data["subjects"]
    )
    assert any(
        a["class_id"] == seeded["class_id"] for a in data["assignments"]
    )
    assert data["workload"]["assigned_classes"] == 1
    assert data["workload"]["subjects"] == 1
    assert data["attendance"]["total"] == 1
    assert data["attendance"]["present"] == 1


@pytest.mark.asyncio
async def test_teacher_360_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/teachers/999999/360", headers=headers)
    assert response.status_code == 404
