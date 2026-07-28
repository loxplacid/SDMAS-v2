from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
async def staff_auth(api_client: AsyncClient) -> str:
    """Register and login a staff user, returning the access token."""
    email = "repstaff@test.com"
    await api_client.post(
        "/auth/register",
        json={
            "email": email,
            "username": "repstaff",
            "password": "Str0ng!Pass",
            "display_name": "Rep Staff",
        },
    )
    resp = await api_client.post(
        "/auth/login",
        json={"login": email, "password": "Str0ng!Pass"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_get_attendance_class_report_requires_auth(api_client: AsyncClient):
    """Verify attendance report endpoint requires authentication."""
    response = await api_client.get("/api/reports/attendance/class/1", params={"academic_year_id": 1})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_collection_report_requires_auth(api_client: AsyncClient):
    """Verify collection report endpoint requires authentication."""
    response = await api_client.get("/api/reports/fees/collection", params={"academic_year_id": 1})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_outstanding_report_requires_auth(api_client: AsyncClient):
    """Verify outstanding report endpoint requires authentication."""
    response = await api_client.get("/api/reports/fees/outstanding", params={"academic_year_id": 1})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_export_requires_auth(api_client: AsyncClient):
    """Verify export endpoints require authentication."""
    # Student export
    r = await api_client.get("/api/reports/export/students")
    assert r.status_code in (401, 403)

    # Attendance export
    r = await api_client.get("/api/reports/export/attendance")
    assert r.status_code in (401, 403)

    # Payments export
    r = await api_client.get("/api/reports/export/payments")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_mutation_endpoints_require_auth(api_client: AsyncClient):
    """Verify mutation endpoints require authentication."""
    endpoints = [
        ("POST", "/api/reports/rollover/preview"),
        ("POST", "/api/reports/rollover/execute"),
        ("POST", "/api/reports/batch/enroll"),
        ("POST", "/api/reports/batch/fee-dues"),
    ]
    for method, path in endpoints:
        if method == "POST":
            r = await api_client.post(path, json={})
        else:
            r = await api_client.get(path)
        assert r.status_code in (401, 403), f"{method} {path} returned {r.status_code}"


@pytest.mark.asyncio
async def test_authenticated_access_to_reports(api_client: AsyncClient, staff_auth: str):
    """Verify authenticated users can access report endpoints."""
    headers = {"Authorization": f"Bearer {staff_auth}"}

    # Reports with invalid data should return 404, not 401
    for path in [
        "/api/reports/attendance/class/99999?academic_year_id=99999",
        "/api/reports/fees/collection?academic_year_id=99999",
        "/api/reports/fees/outstanding?academic_year_id=99999",
    ]:
        r = await api_client.get(path, headers=headers)
        assert r.status_code in (200, 404, 422), f"GET {path} returned {r.status_code}"


@pytest.mark.asyncio
async def test_export_with_auth(api_client: AsyncClient, staff_auth: str):
    """Test export endpoint with proper authentication returns CSV."""
    headers = {"Authorization": f"Bearer {staff_auth}"}
    response = await api_client.get(
        "/api/reports/export/students",
        headers=headers,
    )
    # With auth but no data, should still return CSV (possibly empty)
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_receipt_endpoint_requires_auth(api_client: AsyncClient):
    """Verify receipt lookup endpoint requires authentication."""
    response = await api_client.get("/api/reports/receipts/1")
    assert response.status_code in (401, 403)
