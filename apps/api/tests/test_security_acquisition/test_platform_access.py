"""Platform-access boundary tests.

Three invariants:

1. An authenticated user with no tenant membership and no explicit
   platform permission is DENIED on tenant-scoped routes (default-deny).
2. A tenant admin (even full ``admin`` inside their campus) is DENIED
   platform-only operations — a tenant role never implies platform power.
3. A user holding an explicit platform permission (``platform.access`` /
   ``platform.manage``) IS allowed cross-tenant operations.

These encode the rule: "unscoped" must never imply access; platform power
must always be explicit.
"""

from __future__ import annotations

import pytest

from .conftest import AcqEnv, seed_student

pytestmark = pytest.mark.asyncio


async def test_unscoped_user_denied_on_tenant_routes(
    acq_env: AcqEnv, headers_staff_none
):
    """Invariant: an authenticated user without any campus membership and
    without platform access gets 403, never a global view."""
    for path in ("/students", "/api/classes", "/api/documents", "/jobs"):
        resp = await acq_env.client.get(path, headers=headers_staff_none)
        assert resp.status_code == 403, f"{path}: {resp.status_code}"


async def test_unscoped_user_cannot_read_tenant_resource(
    acq_env: AcqEnv, headers_staff_none
):
    """Invariant: the unscoped user cannot even fetch a resource by ID."""
    student_id = await seed_student(acq_env.factory, 1, "ACQ-PL-1", "Plat")
    resp = await acq_env.client.get(
        f"/students/{student_id}", headers=headers_staff_none
    )
    assert resp.status_code == 403, resp.text


async def test_tenant_admin_denied_platform_manage(
    acq_env: AcqEnv, headers_a
):
    """Invariant: a tenant ``admin`` (full permissions inside their campus)
    still cannot create billing plans — that requires the explicit
    ``platform.manage`` permission.  Tenant power must never cross into
    platform power."""
    resp = await acq_env.client.post(
        "/billing/admin/plans",
        json={
            "name": "Escalation Plan",
            "code": "esc-plan",
            "billing_interval": "monthly",
            "price_inr": 100,
            "trial_days": 0,
        },
        headers=headers_a,
    )
    assert resp.status_code == 403, resp.text


async def test_platform_user_without_permission_denied(
    acq_env: AcqEnv, headers_staff_none
):
    """Invariant: a plain authenticated user hitting a platform-only
    endpoint is denied — platform endpoints are not reachable by role
    guessing or unscoped status."""
    resp = await acq_env.client.get("/billing/plans", headers=headers_staff_none)
    # Public plan catalog remains public by design:
    assert resp.status_code == 200

    resp = await acq_env.client.post(
        "/billing/admin/plans",
        json={"name": "X", "code": "x-plan"},
        headers=headers_staff_none,
    )
    assert resp.status_code == 403, resp.text


async def test_platform_user_with_explicit_permission_allowed(
    acq_env: AcqEnv, headers_platform
):
    """Invariant: the ONLY path to cross-tenant operation is an explicit
    platform grant — ``platform_admin`` may read across campuses and manage
    platform resources."""
    b_stu = await seed_student(acq_env.factory, 2, "ACQ-PLAT-B", "PlatB")

    resp = await acq_env.client.get(
        f"/students/{b_stu}", headers=headers_platform
    )
    assert resp.status_code == 200, resp.text

    resp = await acq_env.client.post(
        "/billing/admin/plans",
        json={
            "name": "Platform Plan",
            "code": "plat-plan",
            "billing_interval": "monthly",
            "price_inr": 0,
            "trial_days": 0,
        },
        headers=headers_platform,
    )
    assert resp.status_code == 200, resp.text


async def test_platform_cross_tenant_list_visibility(
    acq_env: AcqEnv, headers_platform
):
    """Invariant: a platform user sees records from EVERY campus in lists."""
    await seed_student(acq_env.factory, 1, "ACQ-PLA-A", "PlatLA")
    await seed_student(acq_env.factory, 2, "ACQ-PLA-B", "PlatLB")
    resp = await acq_env.client.get("/students", headers=headers_platform)
    assert resp.status_code == 200, resp.text
    assert "ACQ-PLA-A" in resp.text
    assert "ACQ-PLA-B" in resp.text
