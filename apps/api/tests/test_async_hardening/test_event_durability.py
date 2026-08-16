"""Event durability and replay tests.

Proves the durable-event guarantees across process restarts:

* an event published in a transaction survives the API process restart
  (it lives in the outbox table, not process memory)
* delivery claims are atomic — two workers can't deliver the same row
* a worker that dies mid-delivery is reclaimed and re-delivered
* replaying a delivery is idempotent at the consumer (in-app
  notifications dedup on ``event_key``)
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select, update

from app.domains.events.outbox import (
    OUTBOX_STATUS_DEAD_LETTER,
    OUTBOX_STATUS_PENDING,
    OUTBOX_STATUS_PROCESSING,
    OutboxEvent,
    OutboxRepository,
    publish_durable,
)
from app.domains.events.outbox_handlers import register_outbox_handlers
from app.domains.notifications.events import FeeDueCreatedEvent
from app.domains.notifications.repository import NotificationRepository
from app.multi_tenant.models import platform_context

NOW = datetime.datetime.now(datetime.timezone.utc)


def _due_event(student_id: int = 101) -> FeeDueCreatedEvent:
    return FeeDueCreatedEvent(
        student_id=student_id,
        academic_year_id=2026,
        due_ids=[1],
        total_amount=500.0,
        due_count=1,
    )


class TestPersistenceAcrossRestart:
    async def test_event_survives_api_restart(self, session_factory):
        """An event published inside a request transaction persists in the
        outbox table; a fresh process (new session) still sees it pending."""
        async with session_factory() as s:
            row = await publish_durable(
                _due_event(), session=s, event_id="restart:1"
            )
            await s.commit()
            assert row.status == OUTBOX_STATUS_PENDING

        # Simulate a restarted API process: brand-new session.
        async with session_factory() as s2:
            repo = OutboxRepository(s2)
            claimed = await repo.claim_next(max_attempts=10)
            assert claimed is not None
            assert claimed.event_id == "restart:1"

    async def test_rolled_back_transaction_loses_event(self, db_session):
        """If the business transaction rolls back, the outbox row goes with
        it — the event is never delivered (no ghost side effects)."""
        await publish_durable(_due_event(), session=db_session, event_id="rb:1")
        await db_session.rollback()
        rows = (await db_session.execute(select(OutboxEvent))).scalars().all()
        assert rows == []


class TestWorkerCrashReclaim:
    async def test_delivery_claim_is_atomic_across_workers(
        self, session_factory
    ):
        """Two worker sessions racing for the same event: one wins."""
        async with session_factory() as s1, session_factory() as s2:
            await publish_durable(_due_event(), session=s1, event_id="race:1")
            await s1.commit()

            r1 = OutboxRepository(s1)
            r2 = OutboxRepository(s2)
            claimed1 = await r1.claim_next(max_attempts=10)
            claimed2 = await r2.claim_next(max_attempts=10)
            assert claimed1 is not None
            assert claimed2 is None

    async def test_crashed_delivery_is_reclaimed_and_redelivered(
        self, session_factory
    ):
        """A worker that dies mid-delivery (row stuck 'processing') is
        reclaimed by the reaper and delivered by a fresh worker."""
        async with session_factory() as s:
            await publish_durable(_due_event(), session=s, event_id="crash:1")
            await s.commit()

            repo = OutboxRepository(s)
            claimed = await repo.claim_next(max_attempts=10)
            assert claimed is not None
            assert claimed.status == OUTBOX_STATUS_PROCESSING

            # Simulate the worker dying before completing: row stays in
            # processing with a stale updated_at.
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.event_id == "crash:1")
                .values(updated_at=NOW - datetime.timedelta(hours=1))
            )
            await s.commit()

            # Reaper requeues it.
            requeued, dead_lettered = await repo.reclaim_stale_processing(
                NOW, max_attempts=10
            )
            assert requeued == 1
            assert dead_lettered == 0

            # A fresh worker session can now claim and complete it.
            async with session_factory() as s2:
                repo2 = OutboxRepository(s2)
                re_claimed = await repo2.claim_next(max_attempts=10)
                assert re_claimed is not None
                assert re_claimed.event_id == "crash:1"


class TestReplayIdempotency:
    async def test_replay_delivers_notification_exactly_once(
        self, db_session
    ):
        """Delivering the same outbox event twice must not create duplicate
        notifications — the consumer dedups on the event key."""
        from app.domains.events.outbox import outbox_dispatcher

        register_outbox_handlers(outbox_dispatcher)
        try:
            await publish_durable(
                _due_event(student_id=201),
                session=db_session,
                event_id="replay:201",
            )
            repo = OutboxRepository(db_session)
            claimed = await repo.claim_next(max_attempts=10)
            assert claimed is not None
            await outbox_dispatcher.deliver(claimed, db_session)
            await repo.complete(claimed.event_id)

            notif_repo = NotificationRepository(db_session, platform_context())
            items, _ = await notif_repo.find_by_user(201)
            assert len(items) == 1

            # Replay the same row (as a duplicated webhook/retry would).
            replayed = await repo.get_by_event_id("replay:201")
            await outbox_dispatcher.deliver(replayed, db_session)

            items, _ = await notif_repo.find_by_user(201)
            assert len(items) == 1  # still exactly one
        finally:
            outbox_dispatcher.clear()

    async def test_crash_reclaim_redeliver_exactly_once(
        self, session_factory
    ):
        """End-to-end recovery loop: worker claims → dies mid-delivery →
        reaper requeues → fresh worker delivers → exactly one side effect.

        This is the full crash-recovery path in one test: a delivery that
        was claimed but never completed must be redelivered exactly once
        (not zero — the effect would be lost — and not twice — the
        consumer dedups on ``event_key``).
        """
        from app.domains.events.outbox import outbox_dispatcher

        register_outbox_handlers(outbox_dispatcher)
        try:
            # Worker A: publish + claim, then "crash" (row stuck in
            # processing, stale updated_at).
            async with session_factory() as s1:
                await publish_durable(
                    _due_event(student_id=401),
                    session=s1,
                    event_id="crash-loop:401",
                )
                await s1.commit()

                repo = OutboxRepository(s1)
                claimed = await repo.claim_next(max_attempts=10)
                assert claimed is not None
                assert claimed.status == OUTBOX_STATUS_PROCESSING

                await s1.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.event_id == "crash-loop:401")
                    .values(updated_at=NOW - datetime.timedelta(hours=2))
                )
                await s1.commit()

            # Reaper: reclaims the stale delivery.
            async with session_factory() as s2:
                repo2 = OutboxRepository(s2)
                requeued, dead_lettered = await repo2.reclaim_stale_processing(
                    NOW, max_attempts=10
                )
                assert requeued == 1
                assert dead_lettered == 0

                # Observable: the reclaim recorded WHY it happened.
                row = await repo2.get_by_event_id("crash-loop:401")
                assert row.status == OUTBOX_STATUS_PENDING
                assert "Reclaimed: worker stopped" in (row.last_error or "")
                await s2.commit()

            # Worker B: fresh session claims and delivers to completion.
            async with session_factory() as s3:
                repo3 = OutboxRepository(s3)
                re_claimed = await repo3.claim_next(max_attempts=10)
                assert re_claimed is not None
                assert re_claimed.event_id == "crash-loop:401"
                await outbox_dispatcher.deliver(re_claimed, s3)
                await repo3.complete(re_claimed.event_id)
                await s3.commit()

                notif_repo = NotificationRepository(s3, platform_context())
                items, _ = await notif_repo.find_by_user(401)
                assert len(items) == 1, "crash recovery lost or duplicated the effect"
        finally:
            outbox_dispatcher.clear()

    async def test_reaper_records_observable_reasons(self, session_factory):
        """Recovery is observable: reclaim and reaper-dead-letter write a
        distinct ``last_error`` reason so operators can tell why a delivery
        was requeued versus abandoned."""
        async with session_factory() as s:
            repo = OutboxRepository(s)
            await publish_durable(
                _due_event(student_id=501), session=s, event_id="reap:501"
            )
            await publish_durable(
                _due_event(student_id=502), session=s, event_id="reap:502"
            )
            await s.commit()

            # Both stuck in processing (two crashed workers); the second is
            # past its retry budget.
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.event_id == "reap:501")
                .values(
                    status=OUTBOX_STATUS_PROCESSING, attempts=1,
                    updated_at=NOW - datetime.timedelta(hours=2),
                )
            )
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.event_id == "reap:502")
                .values(
                    status=OUTBOX_STATUS_PROCESSING, attempts=10,
                    updated_at=NOW - datetime.timedelta(hours=2),
                )
            )
            await s.commit()

            requeued, dead_lettered = await repo.reclaim_stale_processing(
                NOW, max_attempts=10
            )
            assert requeued == 1
            assert dead_lettered == 1

            requeued_row = await repo.get_by_event_id("reap:501")
            assert requeued_row.status == OUTBOX_STATUS_PENDING
            assert requeued_row.last_error == (
                "Reclaimed: worker stopped before completion"
            )

            dead_row = await repo.get_by_event_id("reap:502")
            assert dead_row.status == OUTBOX_STATUS_DEAD_LETTER
            assert dead_row.last_error == (
                "Reclaimed after max attempts: worker stopped before completion"
            )

    async def test_dead_letter_after_max_attempts(self, session_factory):
        """A handler that always fails dead-letters the event after
        max_attempts — the event is never silently dropped."""
        from app.domains.events.outbox import OutboxDispatcher

        dispatcher = OutboxDispatcher()

        async def _failing_handler(event, *, session):  # noqa: ANN001
            raise RuntimeError("handler boom")

        dispatcher.register("FeeDueCreatedEvent", _failing_handler)

        async with session_factory() as s:
            await publish_durable(_due_event(), session=s, event_id="dl:1")
            await s.commit()

            repo = OutboxRepository(s)
            # Attempt 1 → fails → scheduled for retry with backoff.
            claimed = await repo.claim_next(max_attempts=2)
            assert claimed is not None
            with pytest.raises(RuntimeError):
                await dispatcher.deliver(claimed, s)
            await repo.fail("dl:1", "handler boom", max_attempts=2)

            row = await repo.get_by_event_id("dl:1")
            assert row.status == OUTBOX_STATUS_PENDING
            assert row.attempts == 1
            assert row.next_attempt_at is not None  # backoff scheduled

            # Let the backoff elapse (as the worker would between polls).
            await s.execute(
                update(OutboxEvent)
                .where(OutboxEvent.event_id == "dl:1")
                .values(next_attempt_at=None)
            )
            await s.commit()

            # Attempt 2 → fails again → dead-letter (max attempts reached).
            claimed2 = await repo.claim_next(max_attempts=2)
            assert claimed2 is not None
            with pytest.raises(RuntimeError):
                await dispatcher.deliver(claimed2, s)
            await repo.fail("dl:1", "handler boom", max_attempts=2)

            row = await repo.get_by_event_id("dl:1")
            assert row.status == OUTBOX_STATUS_DEAD_LETTER
            assert "handler boom" in (row.last_error or "")
