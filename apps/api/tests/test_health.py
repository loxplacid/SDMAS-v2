from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_response_structure(client: AsyncClient):
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {
        "status", "version", "environment", "uptime_seconds", "components",
    }
    assert "database" in data["components"]
    assert data["components"]["database"]["status"] in ("healthy", "unhealthy")


@pytest.mark.asyncio
async def test_ready_with_sqlite(client: AsyncClient):
    """With SQLite as the application URL, /ready succeeds (SQLite creates on demand)."""
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["components"]["database"]["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_response_structure(client: AsyncClient):
    response = await client.get("/ready")
    data = response.json()
    assert set(data.keys()) == {"status", "components"}


@pytest.mark.asyncio
async def test_not_found_returns_404(client: AsyncClient):
    response = await client.get("/nonexistent")
    assert response.status_code == 404