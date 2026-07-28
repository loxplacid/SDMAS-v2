from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_student(api_client: AsyncClient):
    response = await api_client.post(
        "/students",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "student_number": "STU001",
            "email": "john@school.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["student_number"] == "STU001"
    assert data["email"] == "john@school.com"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_student_duplicate(api_client: AsyncClient):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "student_number": "STU001",
    }
    await api_client.post("/students", json=payload)
    response = await api_client.post("/students", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_student_invalid_email(api_client: AsyncClient):
    response = await api_client.post(
        "/students",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "student_number": "STU002",
            "email": "not-an-email",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_student(api_client: AsyncClient):
    create_resp = await api_client.post(
        "/students",
        json={"first_name": "Jane", "last_name": "Smith", "student_number": "STU010"},
    )
    student_id = create_resp.json()["id"]

    response = await api_client.get(f"/students/{student_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Jane"
    assert data["student_number"] == "STU010"


@pytest.mark.asyncio
async def test_get_student_not_found(api_client: AsyncClient):
    response = await api_client.get("/students/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_students_empty(api_client: AsyncClient):
    response = await api_client.get("/students")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["pages"] == 0


@pytest.mark.asyncio
async def test_list_students_pagination(api_client: AsyncClient):
    for i in range(5):
        await api_client.post(
            "/students",
            json={
                "first_name": f"User{i}",
                "last_name": "Test",
                "student_number": f"API{i:03d}",
            },
        )

    response = await api_client.get("/students?page=1&size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["size"] == 2
    assert data["pages"] == 3


@pytest.mark.asyncio
async def test_list_students_search(api_client: AsyncClient):
    await api_client.post(
        "/students",
        json={"first_name": "Alice", "last_name": "Wonder", "student_number": "A001"},
    )
    await api_client.post(
        "/students",
        json={"first_name": "Bob", "last_name": "Builder", "student_number": "B001"},
    )

    response = await api_client.get("/students?search=alice")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["first_name"] == "Alice"


@pytest.mark.asyncio
async def test_list_students_filter_by_status(api_client: AsyncClient):
    r1 = await api_client.post(
        "/students",
        json={"first_name": "Active", "last_name": "User", "student_number": "ACT001"},
    )
    s1_id = r1.json()["id"]
    await api_client.post(
        "/students",
        json={"first_name": "Active2", "last_name": "User", "student_number": "ACT002"},
    )

    await api_client.patch(f"/students/{s1_id}", json={"status": "inactive"})

    response = await api_client.get("/students?status=active")
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_update_student(api_client: AsyncClient):
    create_resp = await api_client.post(
        "/students",
        json={"first_name": "Old", "last_name": "Name", "student_number": "UPD001"},
    )
    student_id = create_resp.json()["id"]

    response = await api_client.patch(
        f"/students/{student_id}",
        json={"first_name": "New", "email": "new@school.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "New"
    assert data["last_name"] == "Name"
    assert data["email"] == "new@school.com"
    assert data["student_number"] == "UPD001"


@pytest.mark.asyncio
async def test_update_student_not_found(api_client: AsyncClient):
    response = await api_client.patch(
        "/students/99999", json={"first_name": "Ghost"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_student(api_client: AsyncClient):
    create_resp = await api_client.post(
        "/students",
        json={"first_name": "Delete", "last_name": "Me", "student_number": "DEL001"},
    )
    student_id = create_resp.json()["id"]

    response = await api_client.delete(f"/students/{student_id}")
    assert response.status_code == 204

    get_resp = await api_client.get(f"/students/{student_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_student_not_found(api_client: AsyncClient):
    response = await api_client.delete("/students/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_still_works(api_client: AsyncClient):
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_ready_still_works(api_client: AsyncClient):
    response = await api_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"