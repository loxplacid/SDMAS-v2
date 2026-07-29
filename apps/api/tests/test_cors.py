from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_headers_on_get_request(client: AsyncClient):
    """A GET request should include CORS headers when Origin is present."""
    response = await client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_headers_on_post_request(api_client: AsyncClient):
    """A POST with JSON body should include CORS headers (covers login path)."""
    response = await api_client.post(
        "/auth/login",
        json={"login": "nonexistent", "password": "irrelevant"},
        headers={"Origin": "http://localhost:5173"},
    )
    # Expect 401 because credentials are wrong, but CORS headers must be present
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_preflight_returns_methods_and_headers(client: AsyncClient):
    """An OPTIONS preflight request should advertise allowed methods and headers."""
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    # Preflight responses must include CORS headers
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers
    assert "access-control-max-age" in response.headers


@pytest.mark.asyncio
async def test_cors_disallowed_origin_omits_cors_header(client: AsyncClient):
    """A disallowed origin should not receive a CORS origin header."""
    response = await client.get(
        "/health",
        headers={"Origin": "http://untrusted-site.com"},
    )
    assert response.status_code == 200
    cors_origin = response.headers.get("access-control-allow-origin")
    assert cors_origin is None, (
        f"Expected no CORS origin header for disallowed origin, got {cors_origin!r}"
    )


@pytest.mark.asyncio
async def test_cors_credentials_allowed(client: AsyncClient):
    """The allow-credentials header should be present."""
    response = await client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers.get("access-control-allow-credentials") == "true"
