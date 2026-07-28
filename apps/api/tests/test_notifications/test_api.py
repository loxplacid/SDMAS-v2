from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
async def staff_auth(api_client: AsyncClient) -> str:
    """Register and login a staff user, returning the access token."""
    email = "notifapi@test.com"
    await api_client.post(
        "/auth/register",
        json={
            "email": email,
            "username": "notifapi",
            "password": "Str0ng!Pass",
            "display_name": "Notif API",
        },
    )
    resp = await api_client.post(
        "/auth/login",
        json={"login": email, "password": "Str0ng!Pass"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_unauthenticated_cannot_list(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_cannot_unread_count(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/notifications/unread-count")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_can_list_notifications(
    api_client: AsyncClient, staff_auth: str,
) -> None:
    headers = {"Authorization": f"Bearer {staff_auth}"}
    resp = await api_client.get("/api/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_authenticated_can_get_unread_count(
    api_client: AsyncClient, staff_auth: str,
) -> None:
    headers = {"Authorization": f"Bearer {staff_auth}"}
    resp = await api_client.get(
        "/api/notifications/unread-count", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["count"], int)


@pytest.mark.asyncio
async def test_authenticated_can_mark_all_read(
    api_client: AsyncClient, staff_auth: str,
) -> None:
    headers = {"Authorization": f"Bearer {staff_auth}"}
    resp = await api_client.patch(
        "/api/notifications/read-all", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data


@pytest.mark.asyncio
async def test_unauthenticated_cannot_mark_read(api_client: AsyncClient) -> None:
    resp = await api_client.patch("/api/notifications/1/read")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_cannot_delete(api_client: AsyncClient) -> None:
    resp = await api_client.delete("/api/notifications/1")
    assert resp.status_code == 401
