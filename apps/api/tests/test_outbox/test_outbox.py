"""Tests for the durable event outbox.

Covers:
  - ``OutboxRepository``: enqueue with ``event_id`` dedup, the atomic
    ``claim_next`` (race-safe across workers), ``complete``, ``fail`` with
    exponential backoff and dead-lettering, and the stale-``processing``
    reaper.
  - ``OutboxDispatcher``: ``publish_durable`` writes a row in the caller's
    transaction (rolls back atomically), ``deliver`` rehydrates the event
    and restores tenant context, and unknown event types are rejected.
  - End-to-end: a published event is delivered to its notification handler
    exactly once per row; replay is idempotent at the consumer.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events.context import (
    event_context,
    get_actor_user_id,
    get_correlation_id,
    get_school_id,
)
from app.domains.events.outbox import (
    OUTBOX_STATUS_COMPLETED,
    OUTBOX_STATUS_DEAD_LETTER,
    OUTBOX_STATUS_PENDING,
    OUTBOX_STATUS_PROCESSING,
    OutboxDispatcher,
    OutboxEvent,
    OutboxRepository,
    publish_durable,
)
from app.domains.events.outbox_handlers import register_outbox_handlers
from app.domains.notifications.events import FeeDueCreatedEvent
from app.domains.notifications.repository import NotificationRepository

NOW = datetime.datetime.now(datetime.timezone.utc)


def _due_event(**overrides) -> FeeDueCreatedEvent:
    fields = dict(
        student_id=1,
        academic_year_id=2026,
        due_ids=[10],
        total_amount=500.0,
        due_count=1,
    )
    fields.update(overrides)
    return FeeDueCreatedEvent(**fields)


async def _enqueue(
    session: AsyncSession,
    repo: OutboxRepository,
    *,
    event_id: str = "evt-1",
    event_type: str = "FeeDueCreatedEvent",
    payload: dict | None = None,
    max_attempts: int = 10,
    school_id: int | None = None,
) -> OutboxEvent:
    return await repo.enqueue(
        event_id=event_id,
        event_type=event_type,
        entity_type="fee_due",
        entity_id=10,
        school_id=school_id,
        actor_user_id=5,
        correlation_id="corr-1",
        occurred_at=NOW,
        payload=payload or {"student_id": 1},
        max_attempts=max_attempts,
        now=NOW,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class TestRepository:
    async def test_enqueue_creates_pending_row(self, db_session: AsyncSession) -> None:
        repo = OutboxRepository(db_session)
        row = await _enqueue(db_session, repo)
        assert row.status == OUTBOX_STATUS_PENDING
        assert row.attempts == 0
        assert row.event_id == "evt-1"

    async def test_enqueue_dedups_event_id(self, db_session: AsyncSession) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, event_id="dup")
        second = await _enqueue(db_session, repo, event_id="dup")
        rows = (
            (await db_session.execute(select(OutboxEvent))).scalars().all()
        )
        assert len(rows) == 1
        assert second.id == rows[0].id

    async def test_claim_next_marks_processing_and_is_exclusive(
        self, db_session: AsyncSession
    ) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, event_id="a")
        await _enqueue(db_session, repo, event_id="b")

        claimed_a = await repo.claim_next(max_attempts=10)
        claimed_b = await repo.claim_next(max_attempts=10)
        claimed_none = await repo.claim_next(max_attempts=10)

        assert {claimed_a.event_id, claimed_b.event_id} == {"a", "b"}
        assert claimed_none is None
        assert claimed_a.status == OUTBOX_STATUS_PROCESSING
        assert claimed_b.status == OUTBOX_STATUS_PROCESSING

    async def test_claim_next_respects_backoff(self, db_session: AsyncSession) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, event_id="deferred")
        await db_session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == "deferred")
            .values(next_attempt_at=NOW + datetime.timedelta(hours=1))
        )
        await db_session.flush()
        claimed = await repo.claim_next(max_attempts=10)
        assert claimed is None

    async def test_complete(self, db_session: AsyncSession) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo)
        claimed = await repo.claim_next(max_attempts=10)
        await repo.complete(claimed.event_id)
        row = await repo.get_by_event_id(claimed.event_id)
        assert row.status == OUTBOX_STATUS_COMPLETED
        assert row.processed_at is not None

    async def test_fail_requeues_with_exponential_backoff(
        self, db_session: AsyncSession
    ) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, max_attempts=10)
        claimed = await repo.claim_next(max_attempts=10)
        await repo.fail(claimed.event_id, "boom", max_attempts=10)
        row = await repo.get_by_event_id(claimed.event_id)
        assert row.status == OUTBOX_STATUS_PENDING
        assert row.last_error == "boom"
        assert row.next_attempt_at is not None
        assert row.next_attempt_at > NOW

    async def test_fail_dead_letters_after_max_attempts(
        self, db_session: AsyncSession
    ) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, max_attempts=1)
        claimed = await repo.claim_next(max_attempts=1)
        assert claimed.attempts == 1
        await repo.fail(claimed.event_id, "boom", max_attempts=1)
        row = await repo.get_by_event_id(claimed.event_id)
        assert row.status == OUTBOX_STATUS_DEAD_LETTER
        assert row.last_error == "boom"

    async def test_reclaim_stale_processing(self, db_session: AsyncSession) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, event_id="stale", max_attempts=10)
        await _enqueue(db_session, repo, event_id="exhausted", max_attempts=2)
        # Mark both as processing long ago (as if a worker died mid-delivery).
        stale_before = NOW - datetime.timedelta(seconds=10)
        await db_session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id.in_(["stale", "exhausted"]))
            .values(
                status=OUTBOX_STATUS_PROCESSING,
                attempts=1,
                updated_at=NOW - datetime.timedelta(hours=1),
            )
        )
        await db_session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == "exhausted")
            .values(attempts=2)
        )
        await db_session.flush()

        requeued, dead_lettered = await repo.reclaim_stale_processing(
            stale_before, max_attempts=2
        )
        assert requeued == 1  # "stale" (attempts 1 < 2) requeued
        assert dead_lettered == 1  # "exhausted" (attempts 2 >= 2) dead-lettered

    async def test_count_pending(self, db_session: AsyncSession) -> None:
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, event_id="p1")
        await _enqueue(db_session, repo, event_id="p2")
        await db_session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == "p2")
            .values(next_attempt_at=NOW + datetime.timedelta(hours=1))
        )
        await db_session.flush()
        assert await repo.count_pending() == 1


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestDispatcher:
    async def test_publish_durable_writes_within_transaction(
        self, db_session: AsyncSession
    ) -> None:
        row = await publish_durable(
            _due_event(), session=db_session, event_id="payment:42"
        )
        assert row is not None
        assert row.event_id == "payment:42"
        assert row.event_type == "FeeDueCreatedEvent"
        # Rollback the surrounding transaction -> the outbox row vanishes.
        await db_session.rollback()
        rows = (await db_session.execute(select(OutboxEvent))).scalars().all()
        assert rows == []

    async def test_publish_durable_is_idempotent(self, db_session: AsyncSession) -> None:
        await publish_durable(_due_event(), session=db_session, event_id="x")
        await publish_durable(_due_event(), session=db_session, event_id="x")
        rows = (await db_session.execute(select(OutboxEvent))).scalars().all()
        assert len(rows) == 1

    async def test_deliver_rehydrates_and_restores_tenant_context(
        self, db_session: AsyncSession
    ) -> None:
        dispatcher = OutboxDispatcher()
        captured: dict = {}

        async def handler(event, *, session):
            captured["event"] = event
            captured["session"] = session
            captured["school_id"] = get_school_id()
            captured["actor_user_id"] = get_actor_user_id()
            captured["correlation_id"] = get_correlation_id()

        dispatcher.register("FeeDueCreatedEvent", handler)
        with event_context(
            correlation_id="corr-99", actor_user_id=7, school_id=33
        ):
            row = await publish_durable(
                _due_event(), session=db_session, event_id="ctx"
            )

        claimed = await OutboxRepository(db_session).claim_next(max_attempts=10)
        assert claimed is not None
        await dispatcher.deliver(claimed, db_session)

        assert isinstance(captured["event"], FeeDueCreatedEvent)
        assert captured["event"].student_id == 1
        assert captured["event"].tenant_id == 33
        assert captured["session"] is db_session
        assert captured["school_id"] == 33
        assert captured["actor_user_id"] == 7
        assert captured["correlation_id"] == "corr-99"

    async def test_deliver_unknown_event_type_raises(
        self, db_session: AsyncSession
    ) -> None:
        dispatcher = OutboxDispatcher()
        await _enqueue(
            db_session,
            OutboxRepository(db_session),
            event_id="unknown",
            event_type="totally.unknown",
        )
        claimed = await OutboxRepository(db_session).claim_next(max_attempts=10)
        with pytest.raises(ValueError):
            await dispatcher.deliver(claimed, db_session)

    async def test_deliver_unregistered_type_raises(self, db_session: AsyncSession) -> None:
        dispatcher = OutboxDispatcher()
        row = await publish_durable(
            _due_event(), session=db_session, event_id="unregistered"
        )
        claimed = await OutboxRepository(db_session).claim_next(max_attempts=10)
        assert row is not None and claimed is not None
        with pytest.raises(ValueError):
            await dispatcher.deliver(claimed, db_session)


# ---------------------------------------------------------------------------
# End-to-end: publish -> claim -> deliver -> notification, idempotent replay
# ---------------------------------------------------------------------------


class TestEndToEnd:
    async def test_delivery_creates_notification_and_replay_is_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        from app.domains.events.outbox import outbox_dispatcher

        register_outbox_handlers(outbox_dispatcher)
        try:
            await publish_durable(
                _due_event(student_id=99),
                session=db_session,
                event_id="fee:99:2026",
            )

            repo = OutboxRepository(db_session)
            claimed = await repo.claim_next(max_attempts=10)
            assert claimed is not None
            await outbox_dispatcher.deliver(claimed, db_session)
            await repo.complete(claimed.event_id)

            repo_notif = NotificationRepository(db_session)
            items, _ = await repo_notif.find_by_user(99)
            assert len(items) == 1

            # Replay the same row -> consumer dedups, no duplicate notification.
            row = await repo.get_by_event_id("fee:99:2026")
            assert row.status == OUTBOX_STATUS_COMPLETED
            replayed = await repo.get_by_event_id("fee:99:2026")
            await outbox_dispatcher.deliver(replayed, db_session)

            items, _ = await repo_notif.find_by_user(99)
            assert len(items) == 1
        finally:
            outbox_dispatcher.clear()

    async def test_publish_to_delivery_survives_worker_death_via_reaper(
        self, db_session: AsyncSession
    ) -> None:
        """A delivery claimed but abandoned (worker crash) is reclaimed."""
        repo = OutboxRepository(db_session)
        await _enqueue(db_session, repo, event_id="crashed", max_attempts=10)
        claimed = await repo.claim_next(max_attempts=10)
        assert claimed is not None
        assert claimed.status == OUTBOX_STATUS_PROCESSING

        # Simulate a worker that died mid-delivery: row sits in processing
        # far beyond the staleness window.
        await db_session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == "crashed")
            .values(updated_at=NOW - datetime.timedelta(hours=1))
        )
        await db_session.flush()

        stale_before = NOW
        requeued, dead_lettered = await repo.reclaim_stale_processing(
            stale_before, max_attempts=10
        )
        assert requeued == 1
        assert dead_lettered == 0
        db_session.expire_all()
        row = await repo.get_by_event_id("crashed")
        assert row.status == OUTBOX_STATUS_PENDING
