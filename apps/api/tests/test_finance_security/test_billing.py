"""Billing security tests.

Covers the school-billing surface (plans, subscriptions, invoices,
payment links) that a tenant must not be able to abuse:

* Plan pricing / entitlements are PLATFORM data — a tenant ``admin``
  (even the campus owner) must never create or edit them.
* A cancelled / expired subscription cannot be reactivated for free via
  ``renew`` — that would bypass billing entirely.
* Period-end invoicing is idempotent — a pending invoice blocks a second
  invoice for the same subscription, even across concurrent workers.
* Payment links are tagged with the billing campus so webhook captures
  can be attributed to the right tenant.
"""

from __future__ import annotations

import datetime
from unittest import mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database import Base, get_session


@pytest_asyncio.fixture
async def billing_env() -> dict:
    """Two-campus env + tenant admin (campus 1) + platform admin (unscoped).

    * badmin  — role ``admin``, member of campus 1 → tenant-scoped
    * bplat   — role ``platform_admin``, no campus → explicit platform
    """
    from app.main import app  # registers every model with Base.metadata
    from app.domains.auth.models import User, UserSchoolMembership
    from app.domains.auth.security import hash_password
    from app.domains.institution.models import Institution, Campus

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as seed:
        inst = Institution(name="Billing Inst", code="BILL-INST")
        seed.add(inst)
        await seed.flush()
        campus_a = Campus(
            institution_id=inst.id, name="BILL A", code="BILL-A", status="active"
        )
        campus_b = Campus(
            institution_id=inst.id, name="BILL B", code="BILL-B", status="active"
        )
        seed.add_all([campus_a, campus_b])
        await seed.flush()

        admin = User(
            username="badmin", email="badmin@test.local",
            password_hash=hash_password("BAdmin123!"), display_name="B Admin",
            role="admin", campus_id=campus_a.id, is_active=True,
        )
        plat = User(
            username="bplat", email="bplat@test.local",
            password_hash=hash_password("BPlat123!"), display_name="B Plat",
            role="platform_admin", campus_id=None, is_active=True,
        )
        seed.add_all([admin, plat])
        await seed.flush()
        seed.add(UserSchoolMembership(
            user_id=admin.id, campus_id=campus_a.id,
            role="admin", is_default=True, is_active=True,
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
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Plan administration is platform-only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_admin_cannot_create_plan(billing_env):
    """A tenant admin must never be able to define its own pricing."""
    client = billing_env["client"]
    headers = await _login(client, "badmin", "BAdmin123!")
    resp = await client.post(
        "/billing/admin/plans",
        json={"name": "Tenant-Priced", "code": "TENANT-PRICE", "price_inr": 1},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_tenant_admin_cannot_update_plan(billing_env):
    """A tenant admin must never be able to lower its own price or raise
    its own feature limits."""
    client = billing_env["client"]
    plat_headers = await _login(client, "bplat", "BPlat123!")
    created = await client.post(
        "/billing/admin/plans",
        json={"name": "Pro", "code": "PRO-BILL", "price_inr": 10000},
        headers=plat_headers,
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["id"]

    admin_headers = await _login(client, "badmin", "BAdmin123!")
    resp = await client.patch(
        f"/billing/admin/plans/{plan_id}", json={"price_inr": 1}, headers=admin_headers
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_platform_admin_can_manage_plans(billing_env):
    """The explicit platform permission is the ONLY path to plan admin."""
    client = billing_env["client"]
    headers = await _login(client, "bplat", "BPlat123!")
    created = await client.post(
        "/billing/admin/plans",
        json={
            "name": "Enterprise", "code": "ENT-BILL",
            "price_inr": 500000, "billing_interval": "yearly",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["id"]
    assert created.json()["price_inr"] == 500000

    updated = await client.patch(
        f"/billing/admin/plans/{plan_id}", json={"price_inr": 600000}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["price_inr"] == 600000


# ---------------------------------------------------------------------------
# Subscription lifecycle integrity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renew_rejects_cancelled_subscription(billing_env):
    """A cancelled subscription must not be reactivated for free."""
    from app.core.exceptions import ConflictError
    from app.domains.billing.models import Plan, Subscription
    from app.domains.billing.service import SubscriptionService

    factory = billing_env["factory"]
    now = datetime.datetime.now(datetime.timezone.utc)
    async with factory() as s:
        plan = Plan(
            name="Starter", code="START-BILL", price_inr=10000,
            billing_interval="monthly",
            created_at=now, updated_at=now,
        )
        s.add(plan)
        await s.flush()
        sub = Subscription(
            campus_id=billing_env["campus_a"], plan_id=plan.id,
            status="cancelled",
            current_period_start=now,
            current_period_end=now + datetime.timedelta(days=30),
            cancelled_at=now, created_at=now, updated_at=now,
        )
        s.add(sub)
        await s.commit()

        svc = SubscriptionService(s)
        with pytest.raises(ConflictError, match="new subscription"):
            await svc.renew(billing_env["campus_a"])


@pytest.mark.asyncio
async def test_renew_rejects_expired_subscription(billing_env):
    from app.core.exceptions import ConflictError
    from app.domains.billing.models import Plan, Subscription
    from app.domains.billing.service import SubscriptionService

    factory = billing_env["factory"]
    now = datetime.datetime.now(datetime.timezone.utc)
    async with factory() as s:
        plan = Plan(
            name="Starter", code="START-EXP", price_inr=10000,
            billing_interval="monthly",
            created_at=now, updated_at=now,
        )
        s.add(plan)
        await s.flush()
        sub = Subscription(
            campus_id=billing_env["campus_b"], plan_id=plan.id,
            status="expired",
            current_period_start=now - datetime.timedelta(days=60),
            current_period_end=now - datetime.timedelta(days=30),
            created_at=now, updated_at=now,
        )
        s.add(sub)
        await s.commit()

        svc = SubscriptionService(s)
        with pytest.raises(ConflictError, match="new subscription"):
            await svc.renew(billing_env["campus_b"])


@pytest.mark.asyncio
async def test_period_end_invoices_once(billing_env):
    """A single period end produces exactly one invoice per subscription."""
    from app.domains.billing.models import Invoice, Plan, Subscription
    from app.domains.billing.service import SubscriptionService

    factory = billing_env["factory"]
    now = datetime.datetime.now(datetime.timezone.utc)
    async with factory() as s:
        plan = Plan(
            name="Starter", code="START-IDEM", price_inr=20000,
            billing_interval="monthly",
            created_at=now, updated_at=now,
        )
        s.add(plan)
        await s.flush()
        past = now - datetime.timedelta(days=5)
        sub = Subscription(
            campus_id=billing_env["campus_a"], plan_id=plan.id,
            status="active",
            current_period_start=past - datetime.timedelta(days=25),
            current_period_end=past,
            created_at=past, updated_at=past,
        )
        s.add(sub)
        await s.commit()
        sub_id = sub.id

        svc = SubscriptionService(s)
        results = await svc.process_period_end()
        assert len(results) == 1

        results2 = await svc.process_period_end()
        assert results2 == []

        invoices = (
            await s.execute(
                select(Invoice).where(Invoice.subscription_id == sub_id)
            )
        ).scalars().all()
        assert len(invoices) == 1, "period was invoiced more than once"


@pytest.mark.asyncio
async def test_period_end_skips_when_pending_invoice_exists(billing_env):
    """A subscription with an unpaid pending invoice is never double-invoiced
    (protects against two concurrent workers billing the same period)."""
    from app.domains.billing.models import Invoice, Plan, Subscription
    from app.domains.billing.service import SubscriptionService

    factory = billing_env["factory"]
    now = datetime.datetime.now(datetime.timezone.utc)
    async with factory() as s:
        plan = Plan(
            name="Starter", code="START-PEND", price_inr=20000,
            billing_interval="monthly",
            created_at=now, updated_at=now,
        )
        s.add(plan)
        await s.flush()
        past = now - datetime.timedelta(days=5)
        sub = Subscription(
            campus_id=billing_env["campus_b"], plan_id=plan.id,
            status="active",
            current_period_start=past - datetime.timedelta(days=25),
            current_period_end=past,
            created_at=past, updated_at=past,
        )
        s.add(sub)
        await s.flush()
        # A worker already invoiced (and billed) this period — still unpaid.
        s.add(Invoice(
            campus_id=billing_env["campus_b"], subscription_id=sub.id,
            amount_inr=20000, status="pending",
            period_start=sub.current_period_start, period_end=sub.current_period_end,
            due_at=now + datetime.timedelta(days=7),
            created_at=now, updated_at=now,
        ))
        await s.commit()
        sub_id = sub.id

        svc = SubscriptionService(s)
        results = await svc.process_period_end()
        assert results == [], "pending invoice must block a second invoice"

        invoices = (
            await s.execute(
                select(Invoice).where(Invoice.subscription_id == sub_id)
            )
        ).scalars().all()
        assert len(invoices) == 1


# ---------------------------------------------------------------------------
# Payment links carry the billing campus (tenant-safe webhook attribution)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_link_includes_campus_notes():
    from unittest.mock import AsyncMock

    from app.domains.billing.razorpay import RazorpayProvider

    provider = RazorpayProvider("key_id", "key_secret", "wh_secret")
    with mock.patch.object(
        provider, "_post",
        new=AsyncMock(
            return_value={"short_url": "https://rzp.test/link", "id": "plink_1"}
        ),
    ) as mocked:
        result = await provider.create_payment_link(
            10000, "Term fee", customer_email="a@b.c", notes={"campus_id": "7"}
        )

    mocked.assert_awaited_once()
    sent = mocked.call_args.args[1]
    assert sent["notes"] == {"campus_id": "7"}
    assert sent["amount"] == 10000
    assert sent["currency"] == "INR"
    assert result["url"] == "https://rzp.test/link"


@pytest.mark.asyncio
async def test_create_subscription_includes_notes():
    from unittest.mock import AsyncMock

    from app.domains.billing.razorpay import RazorpayProvider

    provider = RazorpayProvider("key_id", "key_secret", "wh_secret")
    with mock.patch.object(
        provider, "_post", new=AsyncMock(return_value={"id": "sub_prov_1"}),
    ) as mocked:
        result = await provider.create_subscription(
            "plan_prov", "c@d.e", 50000, "monthly", 14,
            notes={"campus_id": "7"},
        )

    mocked.assert_awaited_once()
    sent = mocked.call_args.args[1]
    assert sent["notes"] == {"campus_id": "7"}
    assert result["id"] == "sub_prov_1"
