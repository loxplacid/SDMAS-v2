from __future__ import annotations

import pytest
from httpx import AsyncClient


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
    api_client: AsyncClient, admin_headers: dict,
) -> None:
    resp = await api_client.get("/api/notifications", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_authenticated_can_get_unread_count(
    api_client: AsyncClient, admin_headers: dict,
) -> None:
    resp = await api_client.get(
        "/api/notifications/unread-count", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["count"], int)


@pytest.mark.asyncio
async def test_authenticated_can_mark_all_read(
    api_client: AsyncClient, admin_headers: dict,
) -> None:
    resp = await api_client.patch(
        "/api/notifications/read-all", headers=admin_headers
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
