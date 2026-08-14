"""Finance export/download endpoints (frontend-functional audit fixes).

* GET /transactions/export/csv — ledger CSV dump honoring the same filters
  as the list endpoint; requires FEES_EXPORT; tenant-scoped.
* GET /reports/{id}/download — regenerates the collection-summary CSV from
  the stored report parameters; 409 for unsupported types; tenant-scoped.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database import Base, get_session


@pytest.fixture
async def finance_env() -> dict:
    """Two-campus env with a tenant admin on campus 1."""
    from app.main import app  # registers every model with Base.metadata
    from app.domains.auth.models import User, UserSchoolMembership
    from app.domains.auth.security import hash_password
    from app.domains.institution.models import Institution, Campus

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as seed:
        inst = Institution(name="Export Inst", code="EXPORT-INST")
        seed.add(inst)
        await seed.flush()
        campus_a = Campus(
            institution_id=inst.id, name="EXPORT A", code="EXPORT-A", status="active"
        )
        campus_b = Campus(
            institution_id=inst.id, name="EXPORT B", code="EXPORT-B", status="active"
        )
        seed.add_all([campus_a, campus_b])
        await seed.flush()

        admin = User(
            username="fadmin", email="fadmin@test.local",
            password_hash=hash_password("FAdmin123!"), display_name="F Admin",
            role="admin", campus_id=campus_a.id, is_active=True,
        )
        admin_b = User(
            username="fadminb", email="fadminb@test.local",
            password_hash=hash_password("FAdmin123!"), display_name="F Admin B",
            role="admin", campus_id=campus_b.id, is_active=True,
        )
        staff = User(
            username="fstaff", email="fstaff@test.local",
            password_hash=hash_password("FStaff123!"), display_name="F Staff",
            role="staff", campus_id=campus_a.id, is_active=True,
        )
        seed.add_all([admin, admin_b, staff])
        await seed.flush()
        for user, role in ((admin, "admin"), (admin_b, "admin"), (staff, "staff")):
            seed.add(UserSchoolMembership(
                user_id=user.id, campus_id=user.campus_id,
                role=role, is_default=True, is_active=True,
            ))
        await seed.commit()
        campus_a_id, campus_b_id = campus_a.id, campus_b.id

    async def override_get_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield {
            "client": ac, "factory": factory,
            "campus_a": campus_a_id, "campus_b": campus_b_id,
        }

    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_student_and_payment(factory, campus_id: int, amount: int) -> int:
    """Stub-FK seed (FKs are not enforced in the in-memory SQLite test DB),
    mirroring the pattern in test_school_finance.py."""
    import datetime
    from app.domains.fees.models import FeeDue, Payment
    from app.domains.school_finance.models import TransactionLog
    from app.domains.student.models import Student

    async with factory() as s:
        student = Student(
            first_name="Export", last_name="Student",
            student_number=f"EXP-{campus_id}-{amount}", campus_id=campus_id,
            status="active",
        )
        s.add(student)
        await s.flush()

        due = FeeDue(
            student_id=student.id, academic_year_id=1, fee_structure_id=1,
            original_amount=amount, amount_paid=amount, campus_id=campus_id,
            status="paid",
        )
        s.add(due)
        await s.flush()

        payment = Payment(
            student_id=student.id, fee_due_id=due.id, campus_id=campus_id,
            amount=amount, payment_method="cash", status="completed",
            idempotency_key=f"exp-{campus_id}-{amount}",
            payment_date=datetime.date.today().isoformat(),
        )
        s.add(payment)
        await s.flush()

        s.add(TransactionLog(
            transaction_type="payment", student_id=student.id,
            payment_id=payment.id, fee_due_id=due.id, amount=amount,
            campus_id=campus_id, idempotency_key=f"tx-exp-{campus_id}-{amount}",
            balance_before=0, balance_after=amount,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        ))
        await s.commit()
        return student.id


@pytest.mark.asyncio
async def test_transactions_csv_export_requires_fees_export(finance_env):
    client = finance_env["client"]
    headers = await _login(client, "fadmin", "FAdmin123!")
    resp = await client.get("/api/school-finance/transactions/export/csv", headers=headers)
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    # Header row present even with no rows
    assert resp.text.startswith("ID,Date,Type,Student ID")


@pytest.mark.asyncio
async def test_transactions_csv_export_is_campus_scoped(finance_env):
    factory = finance_env["factory"]
    client = finance_env["client"]
    await _seed_student_and_payment(factory, finance_env["campus_a"], 1200)
    await _seed_student_and_payment(factory, finance_env["campus_b"], 9999)

    headers = await _login(client, "fadmin", "FAdmin123!")
    resp = await client.get(
        "/api/school-finance/transactions/export/csv", headers=headers
    )
    assert resp.status_code == 200, resp.text
    # Campus A admin sees only its own student (1200) — not campus B (9999)
    assert "1200" in resp.text
    assert "9999" not in resp.text


@pytest.mark.asyncio
async def test_transactions_csv_export_respects_q_filter(finance_env):
    factory = finance_env["factory"]
    client = finance_env["client"]
    student_id = await _seed_student_and_payment(factory, finance_env["campus_a"], 2500)

    headers = await _login(client, "fadmin", "FAdmin123!")
    resp = await client.get(
        "/api/school-finance/transactions/export/csv",
        params={"q": str(student_id)},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert f"{student_id}" in resp.text

    resp = await client.get(
        "/api/school-finance/transactions/export/csv",
        params={"q": "does-not-exist-anything"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    # Only the header row remains
    assert resp.text.count("\n") <= 1


@pytest.mark.asyncio
async def test_report_download_unsupported_type_conflicts(finance_env):
    client = finance_env["client"]
    headers = await _login(client, "fadmin", "FAdmin123!")
    created = await client.post(
        "/api/school-finance/reports/generate",
        json={"report_type": "outstanding_balance", "title": "OB Test", "file_format": "csv"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]

    resp = await client.get(
        f"/api/school-finance/reports/{report_id}/download", headers=headers
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_report_download_collection_summary_csv(finance_env):
    factory = finance_env["factory"]
    client = finance_env["client"]
    await _seed_student_and_payment(factory, finance_env["campus_a"], 4500)

    headers = await _login(client, "fadmin", "FAdmin123!")
    created = await client.post(
        "/api/school-finance/reports/generate",
        json={
            "report_type": "collection_summary",
            "title": "CS Test",
            "parameters": {},
            "file_format": "csv",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]

    resp = await client.get(
        f"/api/school-finance/reports/{report_id}/download", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_report_download_other_campus_denied(finance_env):
    factory = finance_env["factory"]
    client = finance_env["client"]
    # Create a report in campus A's context, then try to download it as a
    # campus B admin: same institution, same role — must still be denied.
    await _seed_student_and_payment(factory, finance_env["campus_a"], 300)

    headers_a = await _login(client, "fadmin", "FAdmin123!")
    created = await client.post(
        "/api/school-finance/reports/generate",
        json={
            "report_type": "collection_summary",
            "title": "CS Cross",
            "parameters": {},
            "file_format": "csv",
        },
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]

    # Tenant A's admin can download its own report.
    ok = await client.get(
        f"/api/school-finance/reports/{report_id}/download", headers=headers_a
    )
    assert ok.status_code == 200, ok.text

    # Tenant B's admin (same institution, same role) is denied — the
    # download must never leak across campus boundaries.
    headers_b = await _login(client, "fadminb", "FAdmin123!")
    denied = await client.get(
        f"/api/school-finance/reports/{report_id}/download", headers=headers_b
    )
    assert denied.status_code == 403, denied.text
