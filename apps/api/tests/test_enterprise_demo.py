"""Step 5 — Enterprise Demo Environment tests.

Covers the three-tenant deterministic seeder end-to-end:

- deterministic seed (same anchor + scale => identical structure)
- idempotency (re-running does not duplicate data)
- three isolated tenants with distinct datasets
- API-level tenant isolation (login as A, Tenant B rows are denied)
- RBAC (demo teacher cannot create students; admin can)
- finance consistency (payments == fee-due paid amounts, ledger balances)
- intelligence fixtures (seeded conditions produce real risk findings)
- demo reset safety (production guard; reset removes demo rows)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
    Term,
)
from app.domains.attendance.models import AttendanceRecord
from app.domains.auth.models import User
from app.domains.cases.models import Case
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.institution.models import Campus
from app.domains.notifications.models import Notification
from app.domains.risk.models import RiskFinding
from app.domains.school_finance.models import PaymentReconciliation, TransactionLog
from app.domains.student.models import Student
from app.domains.workflow.models import WorkflowInstance
from app.infrastructure.database import Base, get_session
from scripts.seed_enterprise_demo import (
    DEMO_CODES,
    DEMO_PASSWORD,
    reset_demo_data,
    seed_enterprise_demo,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
ANCHOR = date(2026, 1, 15)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def demo_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Fresh in-memory DB seeded with the three demo tenants (small scale).

    The seed session is closed before returning so every later session
    (fixture or API dependency override) reuses the same pooled SQLite
    connection and therefore the same in-memory database.

    ``run_risk=False`` keeps the shared fixture fast; the intelligence test
    runs its own recompute explicitly.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_enterprise_demo(
            session,
            scale="small",
            run_risk=False,
            anchor_date=ANCHOR,
        )
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def demo_session(
    demo_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Direct DB session over the demo-seeded database."""
    async with demo_factory() as session:
        yield session


@pytest_asyncio.fixture
async def demo_api_client(
    demo_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """API client bound to the demo-seeded DB, with dependency overrides."""
    from app.main import app

    factory = demo_factory

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
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
        yield ac
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, username: str) -> dict[str, str]:
    """Return Authorization headers for a demo user."""
    resp = await client.post(
        "/auth/login",
        json={"login": username, "password": DEMO_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _campus_id(session: AsyncSession, code: str) -> int:
    row = await session.execute(select(Campus.id).where(Campus.code == code))
    return row.scalar_one()


async def _count(session: AsyncSession, model, campus_id: int) -> int:
    row = await session.execute(
        select(func.count(model.id)).where(model.campus_id == campus_id)
    )
    return int(row.scalar_one() or 0)


# ═══════════════════════════════════════════════════════════════════════
# 1. Determinism
# ═══════════════════════════════════════════════════════════════════════


async def _seed_snapshot() -> dict:
    """Seed a fresh small DB and return per-tenant structural snapshots."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_enterprise_demo(
            session, scale="small", run_risk=False, anchor_date=ANCHOR
        )
        snapshot: dict = {}
        for code in DEMO_CODES:
            cid = await _campus_id(session, code)
            snapshot[code] = {
                "students": await _count(session, Student, cid),
                "classes": await _count(session, Class, cid),
                "attendance": await _count(session, AttendanceRecord, cid),
                "fee_dues": await _count(session, FeeDue, cid),
                "payments": await _count(session, Payment, cid),
                "cases": await _count(session, Case, cid),
            }
            nums = (
                await session.execute(
                    select(Student.student_number)
                    .where(Student.campus_id == cid)
                    .order_by(Student.student_number)
                )
            ).scalars().all()
            snapshot[code]["numbers"] = list(nums)
    await engine.dispose()
    return snapshot


async def test_seed_is_deterministic() -> None:
    """Two identical runs produce identical tenant structures and counts."""
    first = await _seed_snapshot()
    second = await _seed_snapshot()
    assert first == second, "Demo seed must be deterministic"


async def test_three_tenants_have_distinct_datasets() -> None:
    """Each tenant exists, has data, and differs from the others."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_enterprise_demo(
            session, scale="small", run_risk=False, anchor_date=ANCHOR
        )
        profiles = {}
        for code in DEMO_CODES:
            cid = await _campus_id(session, code)
            campus = await session.get(Campus, cid)
            profiles[code] = {
                "campus": campus.name,
                "students": await _count(session, Student, cid),
                "classes": await _count(session, Class, cid),
                "teachers": await _count(session, Teacher, cid),
            }
            assert profiles[code]["students"] > 0
            assert profiles[code]["classes"] > 0
            assert profiles[code]["teachers"] > 0

        # Distinct class names per tenant (globally unique constraint).
        names = (
            await session.execute(select(Class.name))
        ).scalars().all()
        assert len(names) == len(set(names)), "Class names must be globally unique"
    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
# 2. Idempotency
# ═══════════════════════════════════════════════════════════════════════


async def test_seed_is_idempotent() -> None:
    """Re-running the seeder must not duplicate demo data."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_enterprise_demo(
            session, scale="small", run_risk=False, anchor_date=ANCHOR
        )
        before = {}
        for code in DEMO_CODES:
            cid = await _campus_id(session, code)
            before[code] = {
                "students": await _count(session, Student, cid),
                "attendance": await _count(session, AttendanceRecord, cid),
                "payments": await _count(session, Payment, cid),
            }

        # Second run: no-op for already-seeded tenants.
        await seed_enterprise_demo(
            session, scale="small", run_risk=False, anchor_date=ANCHOR
        )

        for code in DEMO_CODES:
            cid = await _campus_id(session, code)
            assert await _count(session, Student, cid) == before[code]["students"]
            assert (
                await _count(session, AttendanceRecord, cid)
                == before[code]["attendance"]
            )
            assert await _count(session, Payment, cid) == before[code]["payments"]

        total_campuses = (
            await session.execute(select(func.count(Campus.id)))
        ).scalar_one()
        assert total_campuses == 3
    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
# 3. API-level tenant isolation
# ═══════════════════════════════════════════════════════════════════════


async def test_api_tenant_isolation_students(demo_api_client: AsyncClient) -> None:
    """Login as Apex admin: own students visible, St. Jude students denied."""
    headers = await _login(demo_api_client, "apex.admin")

    # Apex student is visible.
    apex_list = await demo_api_client.get(
        "/students", headers=headers, params={"page": 1, "size": 500}
    )
    assert apex_list.status_code == 200, apex_list.text
    apex_items = apex_list.json()["items"]
    assert apex_items, "Apex admin must see its own students"
    assert all(item["student_number"].startswith("APX-") for item in apex_items), (
        "Apex admin must only see Apex students"
    )

    # Direct GET of a St. Jude student (fetched with a St. Jude token) is
    # denied when requested with the Apex token.
    stj_headers = await _login(demo_api_client, "stjude.admin")
    stj = await demo_api_client.get(
        "/students", headers=stj_headers, params={"page": 1, "size": 1}
    )
    assert stj.status_code == 200, stj.text
    foreign_student_id = stj.json()["items"][0]["id"]
    resp = await demo_api_client.get(f"/students/{foreign_student_id}", headers=headers)
    # Tenant-scoped queries return 404 (no row) — isolation holds either way.
    assert resp.status_code in (403, 404), (
        f"Expected 403/404, got {resp.status_code}: {resp.text}"
    )


async def test_api_tenant_isolation_fees(demo_api_client: AsyncClient) -> None:
    """Tenant A cannot read or mutate Tenant B fee dues."""
    apex_headers = await _login(demo_api_client, "apex.admin")
    stj_headers = await _login(demo_api_client, "stjude.admin")

    stj_dues = await demo_api_client.get(
        "/api/fees/dues", headers=stj_headers, params={"page": 1, "size": 1}
    )
    assert stj_dues.status_code == 200, stj_dues.text
    stj_due_id = stj_dues.json()["items"][0]["id"]

    # Apex token cannot fetch St. Jude's fee due.
    resp = await demo_api_client.get(f"/api/fees/dues/{stj_due_id}", headers=apex_headers)
    # Tenant-scoped queries return 404 (no row) — isolation holds either way.
    assert resp.status_code in (403, 404), (
        f"Expected 403/404, got {resp.status_code}: {resp.text}"
    )

    # Apex list contains no St. Jude dues (identify by receipt/campus tag).
    apex_dues = await demo_api_client.get(
        "/api/fees/dues", headers=apex_headers, params={"page": 1, "size": 500}
    )
    assert apex_dues.status_code == 200
    apex_due_ids = {d["id"] for d in apex_dues.json()["items"]}
    assert stj_due_id not in apex_due_ids


async def test_api_tenant_isolation_audit(demo_api_client: AsyncClient) -> None:
    """Tenant A cannot read Tenant B audit log entries."""
    apex_headers = await _login(demo_api_client, "apex.admin")
    stj_headers = await _login(demo_api_client, "stjude.admin")

    # St. Jude's audit log lists entries; Apex's list must not include them.
    stj_log = await demo_api_client.get(
        "/api/admin/audit-logs", headers=stj_headers, params={"page": 1, "size": 500}
    )
    assert stj_log.status_code == 200, stj_log.text
    stj_entries = stj_log.json()["items"]
    stj_ids = {e["id"] for e in stj_entries}

    apex_log = await demo_api_client.get(
        "/api/admin/audit-logs", headers=apex_headers, params={"page": 1, "size": 500}
    )
    assert apex_log.status_code == 200
    apex_ids = {e["id"] for e in apex_log.json()["items"]}
    assert not (stj_ids & apex_ids), "Tenant A must never see Tenant B audit entries"


# ═══════════════════════════════════════════════════════════════════════
# 4. RBAC
# ═══════════════════════════════════════════════════════════════════════


async def test_rbac_demo_teacher_cannot_create_student(
    demo_api_client: AsyncClient,
) -> None:
    """Demo teacher lacks students.create; demo admin has it."""
    teacher_headers = await _login(demo_api_client, "apex.teacherT01")
    resp = await demo_api_client.post(
        "/students",
        headers=teacher_headers,
        json={
            "first_name": "Test",
            "last_name": "Unauthorized",
            "student_number": "APX-DENIED-0001",
        },
    )
    assert resp.status_code == 403, f"Expected 403 for teacher, got {resp.status_code}"

    admin_headers = await _login(demo_api_client, "apex.admin")
    resp = await demo_api_client.post(
        "/students",
        headers=admin_headers,
        json={
            "first_name": "Test",
            "last_name": "Authorized",
            "student_number": "APX-OK-0001",
        },
    )
    assert resp.status_code == 201, f"Expected 201 for admin, got {resp.status_code}: {resp.text}"


# ═══════════════════════════════════════════════════════════════════════
# 5. Finance consistency
# ═══════════════════════════════════════════════════════════════════════


async def test_finance_consistency(demo_session: AsyncSession) -> None:
    """Fee-due paid amounts == sum of payments; ledger balances chain."""
    # Per fee_due: amount_paid == sum(payment.amount)
    dues = (await demo_session.execute(select(FeeDue))).scalars().all()
    assert dues, "Demo seed must create fee dues"

    for due in dues:
        assert 0 <= due.amount_paid <= due.original_amount, (
            f"FeeDue {due.id} paid {due.amount_paid} outside [0, {due.original_amount}]"
        )
        paid_total = (
            await demo_session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.fee_due_id == due.id
                )
            )
        ).scalar_one()
        assert int(paid_total) == due.amount_paid, (
            f"FeeDue {due.id}: payments sum {paid_total} != amount_paid {due.amount_paid}"
        )

    # Ledger: per-student final balance == sum of payments (no negative).
    students = (await demo_session.execute(select(Student.id))).scalars().all()
    for sid in students:
        logs = (
            await demo_session.execute(
                select(TransactionLog)
                .where(TransactionLog.student_id == sid)
                .order_by(TransactionLog.id)
            )
        ).scalars().all()
        if not logs:
            continue
        balance = 0
        for log in logs:
            assert log.balance_after == log.balance_before + (
                -log.amount
                if log.transaction_type in ("refund", "waiver", "discount")
                else log.amount
            )
            balance = log.balance_after
        total_paid = (
            await demo_session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.student_id == sid
                )
            )
        ).scalar_one()
        assert balance == int(total_paid), (
            f"Student {sid}: ledger balance {balance} != payments {total_paid}"
        )

    # Reconciliation rows exist and are internally consistent.
    recs = (
        await demo_session.execute(
            select(PaymentReconciliation).where(PaymentReconciliation.campus_id.isnot(None))
        )
    ).scalars().all()
    assert recs, "Each tenant should have a reconciliation scenario"
    for rec in recs:
        total = (
            await demo_session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.campus_id == rec.campus_id
                )
            )
        ).scalar_one()
        assert rec.total_amount == int(total), (
            f"Reconciliation {rec.id} total {rec.total_amount} != payments {total}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 6. Intelligence fixtures
# ═══════════════════════════════════════════════════════════════════════


async def test_risk_findings_generated_from_seeded_data() -> None:
    """Seeded conditions produce real risk findings via the real engine.

    The risk evaluator computes its 30-day window against ``date.today()``,
    so this test seeds relative to the current date (no anchor).
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_enterprise_demo(
            session, scale="small", run_risk=True, anchor_date=None
        )
        findings_by_rule: dict[str, int] = {}
        for code in DEMO_CODES:
            cid = await _campus_id(session, code)
            rows = (
                await session.execute(
                    select(RiskFinding.rule_code).where(
                        RiskFinding.campus_id == cid,
                        RiskFinding.status == "open",
                    )
                )
            ).scalars().all()
            for rule in rows:
                findings_by_rule[rule] = findings_by_rule.get(rule, 0) + 1

        # Seeded engineers: low attendance + overdue/high-outstanding fees +
        # low academic performance + missing guardians.
        assert findings_by_rule.get("attendance_below_threshold", 0) >= 1, (
            "Low-attendance engineered students must trigger the attendance rule"
        )
        assert findings_by_rule.get("fees_overdue", 0) >= 1, (
            "Overdue fee dues must trigger the finance rule"
        )
        assert findings_by_rule.get("operational_no_guardian", 0) >= 1, (
            "Students without guardians must trigger the operational rule"
        )
    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
# 7. Reset safety
# ═══════════════════════════════════════════════════════════════════════


def test_reset_refuses_without_force() -> None:
    """Reset must fail closed without an explicit --force (guard)."""
    from scripts.seed_enterprise_demo import _guard

    with pytest.raises(SystemExit):
        _guard(reset=True, force=False)


async def test_reset_removes_demo_data(demo_session: AsyncSession) -> None:
    """reset_demo_data wipes demo rows; demo campuses no longer exist."""
    deleted = await reset_demo_data(demo_session)
    assert deleted, "Reset should delete demo rows"

    remaining_campuses = (
        await demo_session.execute(
            select(func.count(Campus.id)).where(Campus.code.in_(DEMO_CODES))
        )
    ).scalar_one()
    assert remaining_campuses == 0

    remaining_students = (
        await demo_session.execute(select(func.count(Student.id)))
    ).scalar_one()
    assert remaining_students == 0

    remaining_users = (
        await demo_session.execute(
            select(func.count(User.id)).where(User.campus_id.isnot(None))
        )
    ).scalar_one()
    assert remaining_users == 0


async def test_reseed_after_reset_is_clean(demo_session: AsyncSession) -> None:
    """Reset → reseed produces a complete three-tenant environment again."""
    await reset_demo_data(demo_session)
    await seed_enterprise_demo(
        demo_session, scale="small", run_risk=False, anchor_date=ANCHOR
    )
    for code in DEMO_CODES:
        cid = await _campus_id(demo_session, code)
        assert await _count(demo_session, Student, cid) > 0
        assert await _count(demo_session, AttendanceRecord, cid) > 0
        assert await _count(demo_session, FeeDue, cid) > 0


# ═══════════════════════════════════════════════════════════════════════
# 8. Environment completeness
# ═══════════════════════════════════════════════════════════════════════


async def test_demo_environment_is_complete(demo_session: AsyncSession) -> None:
    """Each tenant has the full operational surface the demo walkthrough needs."""
    for code in DEMO_CODES:
        cid = await _campus_id(demo_session, code)
        # Academic structure.
        assert await _count(demo_session, AcademicYear, cid) >= 1
        assert await _count(demo_session, Class, cid) >= 1
        assert await _count(demo_session, Section, cid) >= 1
        assert await _count(demo_session, Subject, cid) >= 1
        assert await _count(demo_session, Term, cid) >= 1
        assert await _count(demo_session, Enrollment, cid) >= 1
        # People + attendance + finance.
        assert await _count(demo_session, Student, cid) >= 1
        assert await _count(demo_session, Teacher, cid) >= 1
        assert await _count(demo_session, AttendanceRecord, cid) >= 1
        assert await _count(demo_session, FeeType, cid) >= 1
        assert await _count(demo_session, FeeStructure, cid) >= 1
        assert await _count(demo_session, Payment, cid) >= 1
        # Operational layers (cases + workflows exist even before risk run).
        assert await _count(demo_session, Case, cid) >= 1
        assert await _count(demo_session, WorkflowInstance, cid) >= 1
        assert await _count(demo_session, Notification, cid) >= 1
        # Demo users exist.
        users = (
            await demo_session.execute(
                select(func.count(User.id)).where(
                    User.campus_id == cid,
                    User.role.in_(("admin", "principal", "accountant", "teacher", "parent")),
                )
            )
        ).scalar_one()
        assert users >= 5


async def test_demo_users_can_login(demo_api_client: AsyncClient) -> None:
    """Documented demo credentials work against the real auth flow."""
    for username in ("apex.admin", "stjude.admin", "mit.admin", "apex.teacherT01"):
        resp = await demo_api_client.post(
            "/auth/login",
            json={"login": username, "password": DEMO_PASSWORD},
        )
        assert resp.status_code == 200, f"{username} failed: {resp.text}"
        assert resp.json()["access_token"]
