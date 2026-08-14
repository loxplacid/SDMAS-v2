"""Adversarial outbox tests.

Closes the remaining gaps in the event-lifecycle matrix:

* **Poison message** — an event whose type has no registered handler /
  class must be retried and dead-lettered with a clear error, never
  silently dropped.
* **Partial-write handler** — a handler that mutates state and then
  raises (crash after partial work) must not leak its partial writes;
  the delivery boundary is a SAVEPOINT, so the retry starts clean.
* **Financial event replay** — re-delivering a ``PaymentReceivedEvent``
  must not create a duplicate notification (consumer-side dedup on the
  payment id).
"""

from __future__ import annotations

import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.events.outbox import (
    OUTBOX_STATUS_DEAD_LETTER,
    OUTBOX_STATUS_PENDING,
    OutboxDispatcher,
    OutboxEvent,
    OutboxRepository,
    publish_durable,
)
from app.domains.events.outbox_handlers import register_outbox_handlers
from app.domains.notifications.events import PaymentReceivedEvent
from app.domains.notifications.models import Notification
from app.domains.notifications.repository import NotificationRepository
from app.multi_tenant.models import platform_context

NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest_asyncio.fixture
async def session_factory() -> async_sessionmaker:
    """A session factory bound to a fresh in-memory DB (mirrors the
    async-hardening suite fixture — the root conftest only provides
    ``db_session``)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.infrastructure.database import Base
    from app.main import app  # noqa: F401  (registers every model)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


class TestPoisonMessage:
    async def test_unknown_event_type_retries_then_dead_letters(
        self, session_factory
    ) -> None:
        """An event with no registered class is a poison message: it must
        be retried with backoff and dead-lettered with a clear error —
        never dropped silently, never stuck in 'processing' forever."""
        async with session_factory() as s:
            repo = OutboxRepository(s)
            await repo.enqueue(
                event_id="poison:1",
                event_type="unknown.poison",
                entity_type=None,
                entity_id=None,
                school_id=None,
                actor_user_id=None,
                correlation_id=None,
                occurred_at=NOW,
                payload={},
                max_attempts=2,
                now=NOW,
            )
            await s.commit()

            dispatcher = OutboxDispatcher()  # no handlers registered
            claimed = await repo.claim_next(max_attempts=2)
            assert claimed is not None

            with pytest.raises(ValueError):
                await dispatcher.deliver(claimed, s)
            await repo.fail(
                "poison:1",
                "No outbox handler registered for event type 'unknown.poison'",
                max_attempts=2,
            )

            row = await repo.get_by_event_id("poison:1")
            assert row.status == OUTBOX_STATUS_PENDING
            assert row.attempts == 1
            assert row.next_attempt_at is not None  # backoff scheduled

            # Backoff elapses (worker poll cadence).
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.event_id == "poison:1")
                .values(next_attempt_at=None)
            )
            await s.commit()

            claimed2 = await repo.claim_next(max_attempts=2)
            assert claimed2 is not None
            with pytest.raises(ValueError):
                await dispatcher.deliver(claimed2, s)
            await repo.fail(
                "poison:1",
                "No outbox handler registered for event type 'unknown.poison'",
                max_attempts=2,
            )

            row = await repo.get_by_event_id("poison:1")
            assert row.status == OUTBOX_STATUS_DEAD_LETTER
            assert "unknown.poison" in (row.last_error or "")


class TestPartialWriteHandler:
    async def test_failed_handler_does_not_leak_partial_notification(
        self, session_factory
    ) -> None:
        """A handler that writes a notification and then raises (crash
        after partial work) must not leave the notification behind —
        the delivery boundary is a SAVEPOINT, so a retry starts clean."""
        dispatcher = OutboxDispatcher()

        async def _partial_then_boom(event, *, session):  # noqa: ANN001
            session.add(
                Notification(
                    user_id=999,
                    type="poison",
                    title="partial",
                    message="should not persist",
                )
            )
            await session.flush()
            raise RuntimeError("boom after partial notification")

        dispatcher.register("FeeDueCreatedEvent", _partial_then_boom)

        from app.domains.notifications.events import FeeDueCreatedEvent

        async with session_factory() as s:
            await publish_durable(
                FeeDueCreatedEvent(
                    student_id=999,
                    academic_year_id=2026,
                    due_ids=[1],
                    total_amount=500.0,
                    due_count=1,
                ),
                session=s,
                event_id="partial:1",
            )
            await s.commit()

            repo = OutboxRepository(s)
            claimed = await repo.claim_next(max_attempts=2)
            assert claimed is not None
            try:
                await dispatcher.deliver(claimed, s)
                await repo.complete(claimed.event_id)
            except Exception:
                await repo.fail("partial:1", "boom", max_attempts=2)
            await s.commit()

            # The partial notification must NOT have been persisted.
            rows = (
                await s.execute(
                    select(Notification).where(Notification.user_id == 999)
                )
            ).scalars().all()
            assert rows == []

            row = await repo.get_by_event_id("partial:1")
            assert row.status == OUTBOX_STATUS_PENDING  # retried, not lost


class TestFinancialEventReplay:
    async def test_payment_event_replay_single_notification(self, db_session) -> None:
        """Re-delivering a PaymentReceivedEvent (duplicate webhook /
        retry) must not create a duplicate payment notification."""
        from app.domains.events.outbox import outbox_dispatcher

        register_outbox_handlers(outbox_dispatcher)
        try:
            await publish_durable(
                PaymentReceivedEvent(
                    student_id=301,
                    fee_due_id=1,
                    payment_id=77,
                    amount=500.0,
                    payment_method="cash",
                    receipt_number="R-77",
                ),
                session=db_session,
                event_id="pay:77",
            )
            repo = OutboxRepository(db_session)
            claimed = await repo.claim_next(max_attempts=10)
            assert claimed is not None
            await outbox_dispatcher.deliver(claimed, db_session)
            await repo.complete(claimed.event_id)

            notif_repo = NotificationRepository(db_session, platform_context())
            items, _ = await notif_repo.find_by_user(301)
            assert len(items) == 1

            # Replay the same row (duplicate delivery).
            replayed = await repo.get_by_event_id("pay:77")
            await outbox_dispatcher.deliver(replayed, db_session)

            items, _ = await notif_repo.find_by_user(301)
            assert len(items) == 1  # still exactly one
        finally:
            outbox_dispatcher.clear()
