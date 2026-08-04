"""Database-level invoice invariant: one invoice per subscription billing period.

The unique constraint ``uq_invoices_subscription_period`` is the structural
backstop on top of the application-level row lock in
``SubscriptionService.process_period_end``.  These tests prove:

* a normal invoice insert succeeds
* a duplicate (subscription_id, period_start) insert is rejected by the DB
* the invariant holds across separate sessions/transactions (the realistic
  concurrency case: a second worker racing to invoice the same period)
* ``process_period_end`` stays idempotent (app lock + DB invariant)
* a failed duplicate attempt can be rolled back and retried cleanly
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domains.billing.models import Invoice, Plan, Subscription
from app.domains.billing.service import SubscriptionService
from app.domains.institution.models import Campus, Institution
from app.infrastructure.database import Base

NOW = datetime.datetime(2026, 8, 4, 12, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    return eng


async def _seed(engine) -> tuple[async_sessionmaker, int, datetime.datetime, int]:
    """Create schema and one institution/campus/plan/subscription.

    Returns ``(factory, subscription_id, period_start, campus_id)``.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        inst = Institution(name="Inv District", code="INV")
        session.add(inst)
        await session.flush()
        campus = Campus(institution_id=inst.id, name="C", code="C")
        session.add(campus)
        await session.flush()

        plan = Plan(
            name="Standard",
            code="std-inv",
            billing_interval="monthly",
            price_inr=10000,
            trial_days=0,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(plan)
        await session.flush()

        sub = Subscription(
            campus_id=campus.id,
            plan_id=plan.id,
            status="active",
            current_period_start=NOW - datetime.timedelta(days=30),
            current_period_end=NOW - datetime.timedelta(days=1),
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(sub)
        await session.commit()
        return factory, sub.id, sub.current_period_start, campus.id


async def _insert_invoice(session: AsyncSession, *, subscription_id, period_start) -> Invoice:
    invoice = Invoice(
        campus_id=1,
        subscription_id=subscription_id,
        amount_inr=10000,
        status="pending",
        period_start=period_start,
        period_end=period_start + datetime.timedelta(days=30),
        due_at=period_start + datetime.timedelta(days=37),
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(invoice)
    await session.flush()
    return invoice


class TestInvoiceUniqueConstraint:
    async def test_normal_invoice_creation_succeeds(self, engine):
        factory, sub_id, period_start, campus_id = await _seed(engine)
        async with factory() as session:
            invoice = await _insert_invoice(
                session, subscription_id=sub_id, period_start=period_start
            )
            invoice.campus_id = campus_id
            await session.commit()
            rows = (await session.execute(select(Invoice))).scalars().all()
            assert len(rows) == 1
            assert rows[0].subscription_id == sub_id

    async def test_duplicate_period_insert_rejected_by_db(self, engine):
        factory, sub_id, period_start, campus_id = await _seed(engine)
        async with factory() as session:
            invoice = await _insert_invoice(
                session, subscription_id=sub_id, period_start=period_start
            )
            invoice.campus_id = campus_id
            await session.commit()

        # Second invoice for the SAME subscription + period must fail at the
        # database, even though the application layer has no guard here.
        async with factory() as session:
            with pytest.raises(IntegrityError):
                await _insert_invoice(
                    session, subscription_id=sub_id, period_start=period_start
                )
            await session.rollback()

        # Exactly one invoice survived.
        async with factory() as session:
            rows = (await session.execute(select(Invoice))).scalars().all()
            assert len(rows) == 1

    async def test_invariant_holds_across_separate_sessions(self, engine):
        """The realistic race: a second worker session tries to invoice the
        same period after the first already committed."""
        factory, sub_id, period_start, campus_id = await _seed(engine)

        async with factory() as s1:
            inv = await _insert_invoice(s1, subscription_id=sub_id, period_start=period_start)
            inv.campus_id = campus_id
            await s1.commit()

        # Fresh session (simulates a second worker replica).
        async with factory() as s2:
            with pytest.raises(IntegrityError):
                await _insert_invoice(s2, subscription_id=sub_id, period_start=period_start)
            await s2.rollback()

        # Exactly one invoice survived.
        async with factory() as s3:
            rows = (await s3.execute(select(Invoice))).scalars().all()
            assert len(rows) == 1

    async def test_process_period_end_is_idempotent(self, engine):
        """The billing job never double-invoices a period: app-level
        pending-invoice guard + DB unique constraint."""
        factory, sub_id, period_start, campus_id = await _seed(engine)

        async with factory() as session:
            svc = SubscriptionService(session)
            first = await svc.process_period_end()
            assert len(first) == 1
            await session.commit()

            # Re-running the same cycle must not create a second invoice.
            again = await svc.process_period_end()
            assert again == []
            await session.commit()

            rows = (await session.execute(select(Invoice))).scalars().all()
            assert len(rows) == 1

    async def test_retry_after_failed_duplicate_is_clean(self, engine):
        """After a duplicate insert fails and the session rolls back, a new
        period can be invoiced without leftover state."""
        factory, sub_id, period_start, campus_id = await _seed(engine)

        async with factory() as session:
            inv = await _insert_invoice(session, subscription_id=sub_id, period_start=period_start)
            inv.campus_id = campus_id
            await session.commit()

        async with factory() as session:
            with pytest.raises(IntegrityError):
                await _insert_invoice(session, subscription_id=sub_id, period_start=period_start)
            await session.rollback()

            # A different period for the same subscription is fine.
            next_period = period_start + datetime.timedelta(days=30)
            ok = await _insert_invoice(session, subscription_id=sub_id, period_start=next_period)
            ok.campus_id = campus_id
            await session.commit()

            rows = (await session.execute(select(Invoice))).scalars().all()
            assert len(rows) == 2
