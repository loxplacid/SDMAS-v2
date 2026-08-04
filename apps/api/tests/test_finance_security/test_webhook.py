from __future__ import annotations

import datetime
import hashlib
import hmac
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database import Base, get_async_session_factory, override_async_session_factory

WEBHOOK_SECRET = "whsec_test_secret"


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
async def webhook_env():
    """In-memory DB + registered razorpay provider + factory override.

    The webhook endpoint opens its own session via
    ``get_async_session_factory()`` (it is public and has no user context),
    so this fixture overrides the global factory and registers a razorpay
    provider with a known webhook secret.
    """
    from app.domains.billing.razorpay import RazorpayProvider
    from app.domains.billing.payments import register_provider, _providers

    engine = create_async_engine(
        "sqlite+aiosqlite:///file:webhook_env?mode=memory&cache=shared&uri=true",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    override_async_session_factory(factory)

    register_provider(
        "razorpay",
        RazorpayProvider(
            key_id="key_id",
            key_secret="key_secret",
            webhook_secret=WEBHOOK_SECRET,
        ),
    )

    yield {"engine": engine, "factory": factory}

    _providers.pop("razorpay", None)
    override_async_session_factory(None)
    await engine.dispose()


@pytest.fixture
async def webhook_client(webhook_env):
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def seeded_subscription(webhook_env) -> dict:
    """A campus with a past-due subscription and a pending invoice."""
    from app.domains.billing.models import Invoice, Plan, Subscription
    from app.domains.institution.models import Campus, Institution

    factory = webhook_env["factory"]
    async with factory() as session:
        inst = Institution(name="WH Inst", code="WH-INST")
        session.add(inst)
        await session.flush()
        campus = Campus(
            institution_id=inst.id, name="WH Campus", code="WH-CMP", status="active"
        )
        session.add(campus)
        await session.flush()
        plan = Plan(
            name="Pro",
            code="WH-PRO",
            price_inr=10000,
            billing_interval="monthly",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(plan)
        await session.flush()
        now = datetime.datetime.now(datetime.timezone.utc)
        sub = Subscription(
            campus_id=campus.id,
            plan_id=plan.id,
            status="past_due",
            current_period_start=now,
            current_period_end=now + datetime.timedelta(days=30),
            payment_provider="razorpay",
            payment_provider_subscription_id="sub_wh_1",
            created_at=now,
            updated_at=now,
        )
        session.add(sub)
        await session.flush()
        invoice = Invoice(
            campus_id=campus.id,
            subscription_id=sub.id,
            amount_inr=10000,
            status="pending",
            period_start=now,
            period_end=now + datetime.timedelta(days=30),
            due_at=now + datetime.timedelta(days=7),
            created_at=now,
            updated_at=now,
        )
        session.add(invoice)
        await session.commit()
        return {"campus": campus, "subscription": sub, "invoice": invoice, "plan": plan}


def _captured_event(provider_subscription_id: str | None = None, notes: dict | None = None) -> dict:
    entity_notes = notes or {}
    if provider_subscription_id:
        entity_notes = {**entity_notes, "subscription_id": provider_subscription_id}
    return {
        "entity": "event",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_001",
                    "amount": 1000000,
                    "status": "captured",
                    "notes": entity_notes,
                }
            }
        },
    }


def _failed_event(notes: dict | None = None) -> dict:
    return {
        "entity": "event",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_failed_001",
                    "amount": 10000,
                    "status": "failed",
                    "notes": notes or {},
                }
            }
        },
    }


# ---------------------------------------------------------------------------
# Signature / provider validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(webhook_client, seeded_subscription):
    body = _captured_event("sub_does_not_matter")
    raw = __import__("json").dumps(body).encode("utf-8")
    bad_signature = _sign(raw, "wrong_secret")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": bad_signature},
    )
    assert resp.status_code == 404
    assert "signature" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_unknown_provider(webhook_client, seeded_subscription):
    resp = await webhook_client.post("/billing/webhook/unknownprovider", content=b"{}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Replay protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_stale_event_rejected(webhook_env, webhook_client, seeded_subscription):
    event = _captured_event("sub_xyz")
    event["timestamp"] = int(time.time()) - 3600  # one hour old
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "stale"

    # Nothing recorded in the idempotency ledger.
    factory = webhook_env["factory"]
    async with factory() as session:
        from app.domains.billing.models import WebhookEvent

        count = (
            await session.execute(select(WebhookEvent))
        ).scalars().all()
        assert len(count) == 0


@pytest.mark.asyncio
async def test_webhook_duplicate_delivery_deduped(
    webhook_env, webhook_client, seeded_subscription
):
    from app.domains.billing.models import Subscription, WebhookEvent

    raw = __import__("json").dumps(_captured_event("sub_wh_1")).encode("utf-8")
    sig = _sign(raw)

    first = await webhook_client.post(
        "/billing/webhook/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    second = await webhook_client.post(
        "/billing/webhook/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    factory = webhook_env["factory"]
    async with factory() as session:
        events = (await session.execute(select(WebhookEvent))).scalars().all()
        assert len(events) == 1
        assert events[0].processed is True

        # Side effects applied exactly once.
        from sqlalchemy import func

        sub_id = seeded_subscription["subscription"].id
        active_subscriptions = (
            await session.execute(
                select(Subscription)
                .where(
                    Subscription.id == sub_id,
                    Subscription.status == "active",
                )
            )
        ).scalars().all()
        assert len(active_subscriptions) == 1


@pytest.mark.asyncio
async def test_webhook_payment_captured_activates_subscription(
    webhook_env, webhook_client, seeded_subscription
):
    from app.domains.billing.models import Invoice, Subscription

    sub = seeded_subscription["subscription"]
    event = _captured_event(provider_subscription_id="sub_wh_1")
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    factory = webhook_env["factory"]
    async with factory() as session:
        refreshed = await session.get(Subscription, sub.id)
        assert refreshed.status == "active"

        invoice = (
            await session.execute(
                select(Invoice).where(
                    Invoice.subscription_id == sub.id, Invoice.status == "pending"
                )
            )
        ).scalar_one_or_none()
        assert invoice is None
        paid_invoice = (
            await session.execute(
                select(Invoice).where(
                    Invoice.subscription_id == sub.id, Invoice.status == "paid"
                )
            )
        ).scalar_one_or_none()
        assert paid_invoice is not None
        assert paid_invoice.paid_at is not None


@pytest.mark.asyncio
async def test_webhook_payment_captured_resolves_tenant_from_notes(
    webhook_env, webhook_client, seeded_subscription
):
    from app.domains.billing.models import WebhookEvent

    campus = seeded_subscription["campus"]
    event = _captured_event(notes={"campus_id": str(campus.id)})
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200

    factory = webhook_env["factory"]
    async with factory() as session:
        event_row = (await session.execute(select(WebhookEvent))).scalars().first()
        assert event_row is not None
        assert event_row.campus_id == campus.id


# ---------------------------------------------------------------------------
# Monetary integrity: the captured amount must cover the invoice
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_underpayment_does_not_mark_invoice_paid(
    webhook_env, webhook_client, seeded_subscription
):
    """A ``payment.captured`` for less than the invoice amount must NOT
    mark the invoice paid or re-activate the subscription — the provider's
    "captured" flag alone is never authoritative for money movement."""
    from app.domains.billing.models import Invoice, Subscription

    sub = seeded_subscription["subscription"]
    invoice = seeded_subscription["invoice"]

    event = _captured_event(provider_subscription_id="sub_wh_1")
    # The invoice is 10000 paise; capture only 1000 paise (₹10 vs ₹100).
    event["payload"]["payment"]["entity"]["amount"] = 1000
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    factory = webhook_env["factory"]
    async with factory() as session:
        refreshed = await session.get(Subscription, sub.id)
        assert refreshed.status == "past_due", \
            "underpaid capture must not activate the subscription"
        inv = await session.get(Invoice, invoice.id)
        assert inv.status == "pending", \
            "underpaid capture must not mark the invoice paid"


@pytest.mark.asyncio
async def test_webhook_overpayment_marks_invoice_paid(
    webhook_env, webhook_client, seeded_subscription
):
    """A capture that covers (or exceeds) the invoice settles it."""
    from app.domains.billing.models import Invoice, Subscription

    sub = seeded_subscription["subscription"]
    invoice = seeded_subscription["invoice"]

    event = _captured_event(provider_subscription_id="sub_wh_1")
    event["payload"]["payment"]["entity"]["amount"] = 100000  # ₹1,000 ≥ ₹100
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200

    factory = webhook_env["factory"]
    async with factory() as session:
        refreshed = await session.get(Subscription, sub.id)
        assert refreshed.status == "active"
        inv = await session.get(Invoice, invoice.id)
        assert inv.status == "paid"


@pytest.mark.asyncio
async def test_webhook_capture_for_unknown_campus_is_inert(
    webhook_env, webhook_client, seeded_subscription
):
    """A capture attributed (via notes) to a campus that does not exist
    must not activate ANY other tenant's subscription."""
    from app.domains.billing.models import Subscription

    sub = seeded_subscription["subscription"]

    event = _captured_event(notes={"campus_id": "424242"})  # no such campus
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    factory = webhook_env["factory"]
    async with factory() as session:
        refreshed = await session.get(Subscription, sub.id)
        assert refreshed.status == "past_due", \
            "unattributable capture must not touch another tenant"


@pytest.mark.asyncio
async def test_webhook_capture_without_amount_fails_closed(
    webhook_env, webhook_client, seeded_subscription
):
    """A ``payment.captured`` with a missing / unparseable amount must NOT
    mark the invoice paid — fail closed, never open."""
    from app.domains.billing.models import Invoice, Subscription

    sub = seeded_subscription["subscription"]
    invoice = seeded_subscription["invoice"]

    event = _captured_event(provider_subscription_id="sub_wh_1")
    del event["payload"]["payment"]["entity"]["amount"]
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    factory = webhook_env["factory"]
    async with factory() as session:
        refreshed = await session.get(Subscription, sub.id)
        assert refreshed.status == "past_due", \
            "amount-less capture must not activate the subscription"
        inv = await session.get(Invoice, invoice.id)
        assert inv.status == "pending", \
            "amount-less capture must not mark the invoice paid"


@pytest.mark.asyncio
async def test_webhook_payment_failed_marks_past_due(
    webhook_env, webhook_client, seeded_subscription
):
    """A verified ``payment.failed`` for a trial subscription moves it to
    ``past_due`` (idempotent — replay is deduped)."""
    from app.domains.billing.models import Subscription

    sub = seeded_subscription["subscription"]
    campus = seeded_subscription["campus"]
    factory = webhook_env["factory"]
    async with factory() as s:
        db_sub = await s.get(Subscription, sub.id)
        db_sub.status = "trial"
        await s.commit()

    event = _failed_event(notes={"campus_id": str(campus.id)})
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    async with factory() as session:
        assert (await session.get(Subscription, sub.id)).status == "past_due"


@pytest.mark.asyncio
async def test_webhook_payment_failed_does_not_downgrade_active(
    webhook_env, webhook_client, seeded_subscription
):
    """A late / out-of-order ``payment.failed`` must not downgrade a
    subscription that a captured payment already activated."""
    from app.domains.billing.models import Subscription

    sub = seeded_subscription["subscription"]
    campus = seeded_subscription["campus"]
    factory = webhook_env["factory"]
    async with factory() as s:
        db_sub = await s.get(Subscription, sub.id)
        db_sub.status = "active"
        await s.commit()

    event = _failed_event(notes={"campus_id": str(campus.id)})
    raw = __import__("json").dumps(event).encode("utf-8")
    resp = await webhook_client.post(
        "/billing/webhook/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert resp.status_code == 200

    async with factory() as session:
        assert (await session.get(Subscription, sub.id)).status == "active"
