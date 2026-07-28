from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["application"] == "SDMAS API"
    assert data["environment"] == "development"
    assert data["status"] == "running"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_response_structure(client: AsyncClient):
    response = await client.get("/")
    data = response.json()
    expected_keys = {"application", "environment", "status", "version"}
    assert set(data.keys()) == expected_keys


@pytest.mark.asyncio
async def test_health_response_structure(client: AsyncClient):
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status"}


@pytest.mark.asyncio
async def test_not_found(client: AsyncClient):
    response = await client.get("/nonexistent")
    assert response.status_code == 404
