from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_record_attendance_single(auth_client: AsyncClient):
    student_resp = await auth_client.post(
        "/students",
        json={"first_name": "John", "last_name": "Doe", "student_number": "ATAPI001"},
    )
    s1 = student_resp.json()

    year_resp = await auth_client.post(
        "/api/academic-years",
        json={"name": "API Year", "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    year = year_resp.json()

    class_resp = await auth_client.post(
        "/api/classes",
        json={"name": "Grade 10", "academic_year_id": year["id"]},
    )
    cls = class_resp.json()

    section_resp = await auth_client.post(
        "/api/sections",
        json={"name": "Section A", "class_id": cls["id"]},
    )
    section = section_resp.json()

    enroll_resp = await auth_client.post(
        "/api/enrollments",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
        },
    )
    assert enroll_resp.status_code == 201

    response = await auth_client.post(
        "/attendance",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
            "attendance_date": "2026-03-15",
            "status": "present",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == s1["id"]
    assert data["status"] == "present"
    assert data["attendance_date"] == "2026-03-15"
    assert "id" in data
    assert "recorded_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_record_attendance_duplicate(auth_client: AsyncClient):
    student_resp = await auth_client.post(
        "/students",
        json={"first_name": "Jane", "last_name": "Doe", "student_number": "ATAPI002"},
    )
    s1 = student_resp.json()

    year_resp = await auth_client.post(
        "/api/academic-years",
        json={"name": "API Year 2", "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    year = year_resp.json()

    class_resp = await auth_client.post(
        "/api/classes",
        json={"name": "Grade 11", "academic_year_id": year["id"]},
    )
    cls = class_resp.json()

    section_resp = await auth_client.post(
        "/api/sections",
        json={"name": "Section B", "class_id": cls["id"]},
    )
    section = section_resp.json()

    await auth_client.post(
        "/api/enrollments",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
        },
    )

    payload = {
        "student_id": s1["id"],
        "academic_year_id": year["id"],
        "class_id": cls["id"],
        "section_id": section["id"],
        "attendance_date": "2026-03-15",
        "status": "present",
    }
    await auth_client.post("/attendance", json=payload)
    response = await auth_client.post("/attendance", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_record_attendance_invalid_status(auth_client: AsyncClient):
    response = await auth_client.post(
        "/attendance",
        json={
            "student_id": 1,
            "academic_year_id": 1,
            "class_id": 1,
            "section_id": 1,
            "attendance_date": "2026-03-15",
            "status": "invalid",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_attendance(auth_client: AsyncClient):
    student_resp = await auth_client.post(
        "/students",
        json={"first_name": "Get", "last_name": "Test", "student_number": "ATAPI003"},
    )
    s1 = student_resp.json()

    year_resp = await auth_client.post(
        "/api/academic-years",
        json={"name": "API Year 3", "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    year = year_resp.json()

    class_resp = await auth_client.post(
        "/api/classes",
        json={"name": "Grade 12", "academic_year_id": year["id"]},
    )
    cls = class_resp.json()

    section_resp = await auth_client.post(
        "/api/sections",
        json={"name": "Section C", "class_id": cls["id"]},
    )
    section = section_resp.json()

    await auth_client.post(
        "/api/enrollments",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
        },
    )

    create_resp = await auth_client.post(
        "/attendance",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
            "attendance_date": "2026-03-15",
            "status": "present",
        },
    )
    record_id = create_resp.json()["id"]

    response = await auth_client.get(f"/attendance/{record_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == record_id
    assert data["status"] == "present"


@pytest.mark.asyncio
async def test_get_attendance_not_found(auth_client: AsyncClient):
    response = await auth_client.get("/attendance/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_attendance(auth_client: AsyncClient):
    student_resp = await auth_client.post(
        "/students",
        json={"first_name": "Update", "last_name": "Test", "student_number": "ATAPI004"},
    )
    s1 = student_resp.json()

    year_resp = await auth_client.post(
        "/api/academic-years",
        json={"name": "API Year 4", "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    year = year_resp.json()

    class_resp = await auth_client.post(
        "/api/classes",
        json={"name": "Grade 9", "academic_year_id": year["id"]},
    )
    cls = class_resp.json()

    section_resp = await auth_client.post(
        "/api/sections",
        json={"name": "Section D", "class_id": cls["id"]},
    )
    section = section_resp.json()

    await auth_client.post(
        "/api/enrollments",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
        },
    )

    create_resp = await auth_client.post(
        "/attendance",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
            "attendance_date": "2026-03-15",
            "status": "absent",
        },
    )
    record_id = create_resp.json()["id"]

    response = await auth_client.patch(
        f"/attendance/{record_id}",
        json={"status": "present"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "present"


@pytest.mark.asyncio
async def test_update_attendance_not_found(auth_client: AsyncClient):
    response = await auth_client.patch("/attendance/99999", json={"status": "present"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_attendance(auth_client: AsyncClient):
    response = await auth_client.get("/attendance")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_daily_attendance(auth_client: AsyncClient):
    student_resp1 = await auth_client.post(
        "/students",
        json={"first_name": "Daily1", "last_name": "Test", "student_number": "ATAPI005"},
    )
    s1 = student_resp1.json()
    student_resp2 = await auth_client.post(
        "/students",
        json={"first_name": "Daily2", "last_name": "Test", "student_number": "ATAPI006"},
    )
    s2 = student_resp2.json()

    year_resp = await auth_client.post(
        "/api/academic-years",
        json={"name": "API Year 5", "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    year = year_resp.json()

    class_resp = await auth_client.post(
        "/api/classes",
        json={"name": "Grade 8", "academic_year_id": year["id"]},
    )
    cls = class_resp.json()

    section_resp = await auth_client.post(
        "/api/sections",
        json={"name": "Section E", "class_id": cls["id"]},
    )
    section = section_resp.json()

    await auth_client.post(
        "/api/enrollments",
        json={
            "student_id": s1["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
        },
    )
    await auth_client.post(
        "/api/enrollments",
        json={
            "student_id": s2["id"],
            "academic_year_id": year["id"],
            "class_id": cls["id"],
            "section_id": section["id"],
        },
    )

    response = await auth_client.post(
        "/attendance/daily",
        json={
            "section_id": section["id"],
            "attendance_date": "2026-03-15",
            "records": [
                {"student_id": s1["id"], "status": "present"},
                {"student_id": s2["id"], "status": "absent"},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    assert data[0]["status"] == "present"
    assert data[1]["status"] == "absent"


@pytest.mark.asyncio
async def test_health_still_works(auth_client: AsyncClient):
    response = await auth_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"