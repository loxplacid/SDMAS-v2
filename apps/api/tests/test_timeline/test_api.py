"""API-level tests for GET /api/timeline.

Covers: auth required, tenant isolation via the endpoint, RBAC (finance
hidden for staff), entity scoping, and the response shape.

Note: data must be seeded through the *app's* session dependency (the
``get_session`` override installed by the ``api_client`` fixture) — the
``db_session`` fixture uses its own in-memory engine that the running
app cannot see.
"""

from __future__ import annotations

import datetime
from datetime import timezone

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session

NOW = datetime.datetime.now(timezone.utc)


@asynccontextmanager
async def _app_session() -> AsyncIterator[AsyncSession]:
    """Yield a live session bound to the app's test engine.

    Must be used as ``async with``. Keeping the ``get_session`` override
    generator suspended at its ``yield`` is what keeps the underlying
    session open — returning from inside an ``async for`` (or letting the
    generator be garbage-collected) throws ``GeneratorExit`` at the
    yield, which closes the session mid-test and raises
    ``ResourceClosedError``.
    """
    from app.main import app

    override = app.dependency_overrides[get_session]
    gen = override()
    try:
        session = await gen.__anext__()
        yield session
        await session.commit()
    finally:
        await gen.aclose()


async def _login(client, username: str, password: str) -> str:
    res = await client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_campus_student(session: AsyncSession, campus_id: int | None, prefix: str) -> dict:
    from app.domains.academic.models import AcademicYear, Class, Enrollment, Section
    from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
    from app.domains.student.models import Student

    year = AcademicYear(
        name=f"{prefix} Year", start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31), campus_id=campus_id, status="active",
    )
    session.add(year)
    await session.flush()
    cls = Class(name=f"{prefix} Grade 10", academic_year_id=year.id, campus_id=campus_id, status="active")
    session.add(cls)
    await session.flush()
    sec = Section(name=f"{prefix} A", class_id=cls.id, campus_id=campus_id, status="active")
    session.add(sec)
    await session.flush()
    student = Student(
        first_name=f"{prefix}S", last_name="Api",
        student_number=f"{prefix.upper()}001", campus_id=campus_id, status="active",
    )
    session.add(student)
    await session.flush()

    ft = FeeType(name=f"Tuition {prefix}", campus_id=campus_id, status="active")
    session.add(ft)
    await session.flush()
    fs = FeeStructure(
        academic_year_id=year.id, class_id=cls.id, fee_type_id=ft.id,
        campus_id=campus_id, amount=50_000_00, frequency="annual", status="active",
    )
    session.add(fs)
    await session.flush()
    due = FeeDue(
        student_id=student.id, academic_year_id=year.id, fee_structure_id=fs.id,
        original_amount=50_000_00, campus_id=campus_id, amount_paid=50_000_00, status="paid",
    )
    session.add(due)
    await session.flush()
    payment = Payment(
        student_id=student.id, fee_due_id=due.id, campus_id=campus_id,
        amount=50_000_00, payment_date=datetime.date.today().isoformat(),
        payment_method="cash", receipt_number=f"API-{prefix}",
        created_at=NOW - datetime.timedelta(days=1),
    )
    session.add(payment)
    await session.flush()

    enrollment = Enrollment(
        student_id=student.id, academic_year_id=year.id, class_id=cls.id,
        section_id=sec.id, campus_id=campus_id, status="active",
        enrolled_at=NOW - datetime.timedelta(days=2),
    )
    session.add(enrollment)
    await session.flush()
    return {"student": student, "year": year, "class": cls}


@pytest.mark.asyncio
async def test_timeline_requires_auth(client):
    res = await client.get("/api/timeline")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_timeline_role_guard(client):
    res = await client.get(
        "/api/timeline",
        headers={"Authorization": "Bearer not-a-token"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_sees_aggregated_timeline(api_client):
    # The seeded admin is a member of campus 1, so seed the events there.
    async with _app_session() as session:
        await _seed_campus_student(session, 1, "A")

    token = await _login(api_client, "admin", "AdminPass123!")
    res = await api_client.get("/api/timeline", headers=_auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "total" in body
    assert "sources" in body
    assert body["page"] == 1
    # At least the seeded payment + enrollment events appear.
    event_sources = {i["source"] for i in body["items"]}
    assert "fees" in event_sources
    assert "academic" in event_sources
    # Reverse-chronological
    stamps = [i["timestamp"] for i in body["items"]]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.asyncio
async def test_student_scope_via_api(api_client):
    async with _app_session() as session:
        data = await _seed_campus_student(session, 1, "B")

    token = await _login(api_client, "admin", "AdminPass123!")
    res = await api_client.get(
        "/api/timeline",
        params={"entity_type": "student", "entity_id": data["student"].id},
        headers=_auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    for item in body["items"]:
        if item["source"] in ("fees", "academic"):
            assert item["metadata"]["student_id"] == data["student"].id


@pytest.mark.asyncio
async def test_timeline_tenant_isolation_via_api(api_client):
    """A campus-scoped staff user only sees their own campus's events."""
    from app.domains.auth.models import User
    from app.domains.auth.security import hash_password
    from app.domains.student.models import Student
    from sqlalchemy import select

    async with _app_session() as session:
        await _seed_campus_student(session, 1, "X")
        await _seed_campus_student(session, 2, "Y")
        # Staff user pinned to campus 1 (legacy column path — no memberships).
        existing = await session.execute(select(User).where(User.username == "staff1"))
        if existing.scalar_one_or_none() is None:
            session.add(
                User(
                    username="staff1", email="staff1@test.local",
                    password_hash=hash_password("AdminPass123!"),
                    display_name="Staff One", role="staff", campus_id=1, is_active=True,
                )
            )
        await session.commit()

        token = await _login(api_client, "staff1", "AdminPass123!")
        res = await api_client.get("/api/timeline", headers=_auth_headers(token))
        assert res.status_code == 200, res.text
        body = res.json()
        # Staff cannot see financial events at all (RBAC).
        for item in body["items"]:
            assert item["source"] != "fees"
        # Only campus-1 academic rows reach the feed (no campus-2 enrollments).
        enrolled = {
            i["metadata"]["student_id"]
            for i in body["items"]
            if i["source"] == "academic"
        }
        x_student = await session.execute(
            select(Student.id).where(Student.student_number == "X001")
        )
        y_student = await session.execute(
            select(Student.id).where(Student.student_number == "Y001")
        )
        x_id = x_student.scalar_one()
        y_id = y_student.scalar_one()
        assert x_id in enrolled
        assert y_id not in enrolled
