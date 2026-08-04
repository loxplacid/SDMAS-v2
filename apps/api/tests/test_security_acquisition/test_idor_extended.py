"""Extended IDOR tests — surfaces beyond the core tenant-isolation suite.

Each test hands Tenant A a valid resource ID owned by Tenant B and proves
the request fails (403/404) with no side effect:

* background jobs — cancel / retry / update
* notifications — mark-read / delete (must NOT leak existence)
* audit entries — read by id
* document shares — revoke
* guardian junction — cross-tenant link (relationship-table write)
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select

from app.domains.documents.models import DocumentShare
from app.domains.parent.models import Guardian

from .conftest import (
    AcqEnv,
    seed_audit,
    seed_document,
    seed_job,
    seed_notification,
    seed_student,
)

pytestmark = pytest.mark.asyncio


async def test_job_cancel_retry_cross_tenant_denied(
    acq_env: AcqEnv, headers_a
):
    """Invariant: Tenant A cannot cancel or retry Tenant B's background
    job — job control is scoped to owner/campus."""
    b_job = await seed_job(acq_env.factory, 2, "xjob", user_id=2)

    for action in ("cancel", "retry"):
        resp = await acq_env.client.post(
            f"/jobs/{b_job}/{action}", headers=headers_a
        )
        assert resp.status_code in (403, 404), f"{action}: {resp.status_code}"

    # The B job is untouched (still pending, not cancelled).
    from app.domains.jobs.models import Job

    async with acq_env.factory() as s:
        job = (await s.execute(
            select(Job).where(Job.id == b_job)
        )).scalar_one()
    assert job.status == "pending"


async def test_notification_mark_read_cross_tenant_denied(
    acq_env: AcqEnv, headers_a
):
    """Invariant: Tenant A cannot mark Tenant B's notification read — and
    the response must not leak that the notification exists (404, not 403
    with a different message)."""
    b_notif = await seed_notification(acq_env.factory, 2, 2, "SECRET-NOTIF-B")

    resp = await acq_env.client.patch(
        f"/api/notifications/{b_notif}/read", headers=headers_a
    )
    assert resp.status_code == 404, resp.text

    resp = await acq_env.client.delete(
        f"/api/notifications/{b_notif}", headers=headers_a
    )
    assert resp.status_code == 404, resp.text

    # Still present and untouched.
    from app.domains.notifications.models import Notification

    async with acq_env.factory() as s:
        n = (await s.execute(
            select(Notification).where(Notification.id == b_notif)
        )).scalar_one()
    assert n is not None
    assert n.title == "SECRET-NOTIF-B"


async def test_audit_entry_read_cross_tenant_denied(
    acq_env: AcqEnv, headers_a
):
    """Invariant: audit entries are tenant-owned — Tenant A cannot read
    Tenant B's audit trail by id."""
    b_entry = await seed_audit(
        acq_env.factory, 2, "CREATE", "student", "ACQ-AUDIT-XB"
    )
    a_entry = await seed_audit(
        acq_env.factory, 1, "CREATE", "student", "ACQ-AUDIT-XA"
    )

    resp = await acq_env.client.get(
        f"/api/admin/audit-logs/{b_entry}", headers=headers_a
    )
    assert resp.status_code in (403, 404), resp.text

    resp = await acq_env.client.get(
        f"/api/admin/audit-logs/{a_entry}", headers=headers_a
    )
    assert resp.status_code == 200, resp.text


async def test_document_share_revoke_cross_tenant_denied(
    acq_env: AcqEnv, headers_a
):
    """Invariant: Tenant A cannot revoke a share on Tenant B's document."""
    b_doc = await seed_document(acq_env.factory, 2, 2, "acq-xid-share")
    async with acq_env.factory() as s:
        share = DocumentShare(
            document_id=b_doc,
            token="acq-xid-share-token",
            created_by=2,
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=1),
            max_downloads=None,
        )
        s.add(share)
        await s.commit()
        share_id = share.id

    resp = await acq_env.client.post(
        f"/api/documents/shares/{share_id}/revoke", headers=headers_a
    )
    assert resp.status_code in (403, 404), resp.text

    async with acq_env.factory() as s:
        share = (await s.execute(
            select(DocumentShare).where(DocumentShare.id == share_id)
        )).scalar_one()
    assert not share.is_revoked


async def test_guardian_junction_cannot_link_cross_tenant(
    acq_env: AcqEnv,
):
    """Invariant: a relationship (junction) row can never be created across
    tenant boundaries — parent linking is campus-scoped."""
    from .conftest import login

    headers_parent = await login(acq_env, "teacher_a")  # any campus-A user
    b_stu = await seed_student(acq_env.factory, 2, "ACQ-XID-GRD", "XGrd")

    resp = await acq_env.client.post(
        "/api/parent/children/link",
        json={"student_id": b_stu, "relationship": "parent"},
        headers=headers_parent,
    )
    assert resp.status_code in (403, 404), resp.text

    async with acq_env.factory() as s:
        rows = (await s.execute(
            select(Guardian).where(Guardian.student_id == b_stu)
        )).scalars().all()
    assert len(rows) == 0, "cross-tenant guardian junction was created!"
