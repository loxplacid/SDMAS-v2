from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _admin_headers(api_client: AsyncClient) -> dict:
    """Login as the seeded admin user (see conftest api_client fixture)."""
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_student(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.post(
        "/students",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "student_number": "STU001",
            "email": "john@school.com",
        },
        headers=headers,
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
    headers = await _admin_headers(api_client)
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "student_number": "STU001",
    }
    await api_client.post("/students", json=payload, headers=headers)
    response = await api_client.post("/students", json=payload, headers=headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_student_invalid_email(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.post(
        "/students",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "student_number": "STU002",
            "email": "not-an-email",
        },
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_student(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create_resp = await api_client.post(
        "/students",
        json={"first_name": "Jane", "last_name": "Smith", "student_number": "STU010"},
        headers=headers,
    )
    student_id = create_resp.json()["id"]

    response = await api_client.get(f"/students/{student_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Jane"
    assert data["student_number"] == "STU010"


@pytest.mark.asyncio
async def test_get_student_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/students/99999", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_students_empty(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.get("/students", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["pages"] == 0


@pytest.mark.asyncio
async def test_list_students_pagination(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    for i in range(5):
        await api_client.post(
            "/students",
            json={
                "first_name": f"User{i}",
                "last_name": "Test",
                "student_number": f"API{i:03d}",
            },
            headers=headers,
        )

    response = await api_client.get("/students?page=1&size=2", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["size"] == 2
    assert data["pages"] == 3


@pytest.mark.asyncio
async def test_list_students_search(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    await api_client.post(
        "/students",
        json={"first_name": "Alice", "last_name": "Wonder", "student_number": "A001"},
        headers=headers,
    )
    await api_client.post(
        "/students",
        json={"first_name": "Bob", "last_name": "Builder", "student_number": "B001"},
        headers=headers,
    )

    response = await api_client.get("/students?search=alice", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["first_name"] == "Alice"


@pytest.mark.asyncio
async def test_list_students_filter_by_status(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    r1 = await api_client.post(
        "/students",
        json={"first_name": "Active", "last_name": "User", "student_number": "ACT001"},
        headers=headers,
    )
    s1_id = r1.json()["id"]
    await api_client.post(
        "/students",
        json={"first_name": "Active2", "last_name": "User", "student_number": "ACT002"},
        headers=headers,
    )

    await api_client.patch(f"/students/{s1_id}", json={"status": "inactive"}, headers=headers)

    response = await api_client.get("/students?status=active", headers=headers)
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_update_student(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create_resp = await api_client.post(
        "/students",
        json={"first_name": "Old", "last_name": "Name", "student_number": "UPD001"},
        headers=headers,
    )
    student_id = create_resp.json()["id"]

    response = await api_client.patch(
        f"/students/{student_id}",
        json={"first_name": "New", "email": "new@school.com"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "New"
    assert data["last_name"] == "Name"
    assert data["email"] == "new@school.com"
    assert data["student_number"] == "UPD001"


@pytest.mark.asyncio
async def test_update_student_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.patch(
        "/students/99999", json={"first_name": "Ghost"}, headers=headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_student(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create_resp = await api_client.post(
        "/students",
        json={"first_name": "Delete", "last_name": "Me", "student_number": "DEL001"},
        headers=headers,
    )
    student_id = create_resp.json()["id"]

    response = await api_client.delete(f"/students/{student_id}", headers=headers)
    assert response.status_code == 204

    get_resp = await api_client.get(f"/students/{student_id}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_student_not_found(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    response = await api_client.delete("/students/99999", headers=headers)
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
    assert response.json()["status"] == "ready"
    assert response.json()["components"]["database"]["status"] == "ready"
