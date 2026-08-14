"""Durable integration event outbox.

Distinguishes two delivery classes:

1. **In-process domain events** — the fast path (``events.event_bus`` /
   ``notifications.dispatcher``). Handlers run synchronously inside the
   request's transaction; failures are best-effort and non-fatal.
2. **Durable integration events** — written to the ``outbox_events`` table
   *in the same transaction* as the business mutation that caused them
   (transactional outbox), then delivered exactly once per row by the
   background worker process.  Critical events (payment recorded, fee dues
   created, batch completed, academic-year rollover) use this path so they
   survive an API crash, are retried with backoff, dead-letter after
   ``max_attempts``, and can be replayed.

Guarantees
----------
* **Reliable persistence** — the outbox row commits atomically with the
  business change; the event is never lost if the request process dies.
* **Idempotent producer** — ``event_id`` is UNIQUE; re-enqueueing the same
  event collapses to one row.
* **At-least-once delivery** — the worker claims rows with an atomic
  ``UPDATE ... RETURNING`` (race-safe across multiple workers, same pattern
  as the job queue) and marks them ``completed`` after delivery.  A crash
  between side-effects and completion is safe because consumers are
  idempotent (unique ``event_id`` + DB-level notification dedup).
* **Retry / dead-letter** — a failed delivery is re-queued with exponential
  backoff and dead-lettered after ``max_attempts``.  Stale ``processing``
  rows (worker died mid-delivery) are re-claimed by the reaper.
* **Tenancy** — the tenant (``school_id``) is captured at publish time from
  the event/request context and restored around delivery, so a delivery
  never inherits a different tenant's context.
* **System actor** — deliveries are attributed to ``AuditActor.worker()``
  when they write audit entries.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Callable, Coroutine

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, async_session_factory

logger = logging.getLogger(__name__)

OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_PROCESSING = "processing"
OUTBOX_STATUS_COMPLETED = "completed"
OUTBOX_STATUS_DEAD_LETTER = "dead_letter"


# Works with both PostgreSQL (JSONB) and SQLite (Text-based JSON) — mirrors
# ``app.domains.jobs.models`` so the two durable queues share behaviour.
class _JSON(TypeDecorator):
    impl = JSONB

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
            return dialect.type_descriptor(_PG_JSONB())
        from sqlalchemy import JSON as _SA_JSON
        return dialect.type_descriptor(_SA_JSON())

    def process_bind_param(self, value: Any, dialect) -> str | None:
        import json
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value: Any, dialect) -> Any:
        import json
        if isinstance(value, str):
            return json.loads(value)
        return value


JSONType = _JSON


class OutboxEvent(Base):
    """A durable integration event awaiting delivery."""

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    school_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default=OUTBOX_STATUS_PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_outbox_events_event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OutboxEvent id={self.id} type={self.event_type} "
            f"status={self.status} attempts={self.attempts}>"
        )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class OutboxRepository:
    """Data access for the outbox table.

    Constructed with a session only — the outbox is a platform-level queue
    and is never tenant-scoped at the repository layer.  Tenancy is enforced
    at *delivery* time by restoring the stored ``school_id``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        event_id: str,
        event_type: str,
        entity_type: str | None,
        entity_id: int | None,
        school_id: int | None,
        actor_user_id: int | None,
        correlation_id: str | None,
        occurred_at: datetime.datetime,
        payload: dict[str, Any] | None,
        max_attempts: int,
        now: datetime.datetime,
    ) -> OutboxEvent:
        """Insert a durable event, skipping a duplicate ``event_id``.

        Returns the (possibly pre-existing) row.  The unique constraint is
        the cross-instance backstop; the pre-check avoids poisoning the
        caller's transaction with an integrity error for a duplicate.
        """
        existing = await self.get_by_event_id(event_id)
        if existing is not None:
            logger.debug("Outbox event %s already enqueued — skipping", event_id)
            return existing

        row = OutboxEvent(
            event_id=event_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            school_id=school_id,
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            payload=payload,
            status=OUTBOX_STATUS_PENDING,
            attempts=0,
            max_attempts=max_attempts,
            next_attempt_at=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_event_id(self, event_id: str) -> OutboxEvent | None:
        result = await self.session.execute(
            select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        )
        return result.scalar_one_or_none()

    async def claim_next(self, max_attempts: int) -> OutboxEvent | None:
        """Atomically claim the next deliverable event.

        Single ``UPDATE ... WHERE id = (SELECT ...) AND status = 'pending' ...
        RETURNING`` — race-safe across multiple worker processes (see the
        job queue's ``acquire_next`` for the same reasoning).
        """
        now = _now()
        candidate = (
            select(OutboxEvent.id)
            .where(
                OutboxEvent.status == OUTBOX_STATUS_PENDING,
                (OutboxEvent.next_attempt_at.is_(None))
                | (OutboxEvent.next_attempt_at <= now),
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )
        claimed_id = await self.session.scalar(
            update(OutboxEvent)
            .where(OutboxEvent.id == candidate, OutboxEvent.status == OUTBOX_STATUS_PENDING)
            .values(
                status=OUTBOX_STATUS_PROCESSING,
                attempts=OutboxEvent.attempts + 1,
                updated_at=now,
            )
            .returning(OutboxEvent.id)
            .execution_options(synchronize_session=False)
        )
        if claimed_id is None:
            return None
        event = await self.session.get(OutboxEvent, claimed_id)
        if event is not None:
            await self.session.refresh(event)
        return event

    async def complete(self, event_id: str) -> None:
        now = _now()
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == event_id)
            .values(
                status=OUTBOX_STATUS_COMPLETED,
                processed_at=now,
                last_error=None,
                updated_at=now,
            )
        )
        await self.session.flush()

    async def fail(
        self,
        event_id: str,
        error: str,
        *,
        max_attempts: int,
        now: datetime.datetime | None = None,
    ) -> None:
        now = now or _now()
        row = await self.get_by_event_id(event_id)
        if row is None:
            return
        if row.attempts >= max_attempts:
            values: dict[str, Any] = {
                "status": OUTBOX_STATUS_DEAD_LETTER,
                "last_error": error,
                "updated_at": now,
            }
        else:
            delay = min(60 * (2 ** (max(row.attempts - 1, 1))), 86400)
            values = {
                "status": OUTBOX_STATUS_PENDING,
                "next_attempt_at": now + datetime.timedelta(seconds=delay),
                "last_error": error,
                "updated_at": now,
            }
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.event_id == event_id)
            .values(**values)
        )
        await self.session.flush()

    async def reclaim_stale_processing(
        self,
        stale_before: datetime.datetime,
        max_attempts: int,
    ) -> tuple[int, int]:
        """Re-queue (or dead-letter) deliveries stuck in ``processing``.

        A worker that dies mid-delivery leaves its row in ``processing``
        forever.  This pass reclaims them — retrying while retry budget
        remains and dead-lettering after ``max_attempts``.  Race-safe via
        the same ``status`` predicate + row-lock reasoning as the job reaper.
        """
        now = _now()
        stale_conditions = [
            OutboxEvent.status == OUTBOX_STATUS_PROCESSING,
            OutboxEvent.updated_at < stale_before,
        ]

        requeued = await self.session.scalars(
            update(OutboxEvent)
            .where(*stale_conditions, OutboxEvent.attempts < max_attempts)
            .values(
                status=OUTBOX_STATUS_PENDING,
                next_attempt_at=now,
                attempts=OutboxEvent.attempts + 1,
                last_error="Reclaimed: worker stopped before completion",
                updated_at=now,
            )
            .returning(OutboxEvent.id)
            .execution_options(synchronize_session=False)
        )
        requeued_ids = list(requeued.all())

        dead_lettered = await self.session.scalars(
            update(OutboxEvent)
            .where(*stale_conditions, OutboxEvent.attempts >= max_attempts)
            .values(
                status=OUTBOX_STATUS_DEAD_LETTER,
                last_error=(
                    "Reclaimed after max attempts: worker stopped before completion"
                ),
                updated_at=now,
            )
            .returning(OutboxEvent.id)
            .execution_options(synchronize_session=False)
        )
        dead_lettered_ids = list(dead_lettered.all())

        return len(requeued_ids), len(dead_lettered_ids)

    async def count_pending(self) -> int:
        now = _now()
        result = await self.session.execute(
            select(OutboxEvent.id)
            .where(
                OutboxEvent.status == OUTBOX_STATUS_PENDING,
                (OutboxEvent.next_attempt_at.is_(None))
                | (OutboxEvent.next_attempt_at <= now),
            )
        )
        return len(result.all())


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

OutboxHandler = Callable[..., Coroutine[Any, Any, Any]]


class OutboxDispatcher:
    """Delivers durable outbox events to registered handlers.

    Handlers are registered by ``event_type`` string and receive the
    rehydrated event object plus the worker session.  A raising handler
    fails the delivery (retry/dead-letter); a handler that swallows its own
    errors (e.g. the best-effort notification handlers) completes it.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[OutboxHandler]] = {}

    def register(self, event_type: str, handler: OutboxHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("Registered outbox handler %s for %s", handler.__name__, event_type)

    @property
    def handler_count(self) -> int:
        return sum(len(h) for h in self._handlers.values())

    def clear(self) -> None:
        self._handlers.clear()

    # ------------------------------------------------------------------
    # Producer side
    # ------------------------------------------------------------------

    async def publish_durable(
        self,
        event: Any,
        session: AsyncSession,
        **context: Any,
    ) -> OutboxEvent | None:
        """Persist *event* into the outbox within the caller's transaction.

        This is the durable publish path: call it with the same session that
        performs the business mutation so the outbox row commits atomically
        with it.  Does **not** dispatch in-process — delivery is performed by
        the worker (single delivery path, no double side-effects).
        """
        from app.domains.events.base import (
            event_type_of,
            new_correlation_id,
            new_event_id,
            now_utc,
            serialize_event,
        )
        from app.domains.events.context import (
            get_actor_user_id,
            get_correlation_id,
            get_school_id,
        )

        event_id = (
            context.get("event_id")
            or getattr(event, "event_id", None)
            or new_event_id()
        )
        occurred_at = getattr(event, "occurred_at", None) or now_utc()
        event_type = event_type_of(event)
        entity_type = getattr(event, "entity_type", None) or getattr(
            type(event), "ENTITY_TYPE", ""
        )
        entity_id = getattr(event, "entity_id", None)

        school_id = context.get("school_id")
        if school_id is None:
            school_id = (
                getattr(event, "school_id", None)
                or getattr(event, "tenant_id", None)
                or get_school_id()
            )
        if "actor_user_id" in context:
            actor_user_id = context["actor_user_id"]
        else:
            actor_user_id = getattr(event, "actor_user_id", None) or get_actor_user_id()
        correlation_id = (
            context.get("correlation_id")
            or getattr(event, "correlation_id", None)
            or get_correlation_id()
            or new_correlation_id()
        )

        envelope = serialize_event(event)
        repo = OutboxRepository(session)
        return await repo.enqueue(
            event_id=event_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            school_id=school_id,
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at,
            payload=envelope.get("payload"),
            max_attempts=int(getattr(self, "_max_attempts", 10) or 10),
            now=_now(),
        )

    # ------------------------------------------------------------------
    # Consumer side (worker process)
    # ------------------------------------------------------------------

    async def deliver(
        self,
        outbox_event: OutboxEvent,
        session: AsyncSession,
    ) -> bool:
        """Deliver one claimed event to its handlers under tenant context.

        Returns ``True`` when at least one handler ran (or the event has no
        handlers — see below).  Raises when a handler raises so the worker
        can retry / dead-letter the delivery.
        """
        handlers = self._handlers.get(outbox_event.event_type, [])
        if not handlers:
            logger.error(
                "No outbox handler registered for '%s' (event %s) — dead-lettering",
                outbox_event.event_type, outbox_event.event_id,
            )
            raise ValueError(
                f"No outbox handler registered for event type '{outbox_event.event_type}'"
            )

        event = self._rehydrate(outbox_event)

        from app.domains.events.context import event_context

        with event_context(
            correlation_id=outbox_event.correlation_id or None,
            actor_user_id=outbox_event.actor_user_id,
            school_id=outbox_event.school_id,
        ):
            for handler in handlers:
                # Handler work is a SAVEPOINT: if the handler raises, its
                # partial writes roll back so the delivery's retry starts
                # clean — a poisoned delivery can never leave half-applied
                # side effects (e.g. an orphan notification) committed by
                # the worker's poll-cycle commit.
                savepoint = await session.begin_nested()
                try:
                    await handler(event, session=session)
                except BaseException:
                    # BaseException (not just Exception): a worker shutdown
                    # cancel mid-delivery must still roll the savepoint back.
                    try:
                        await savepoint.rollback()
                    except Exception:
                        pass
                    raise
                else:
                    try:
                        await savepoint.commit()
                    except Exception:
                        pass
        return True

    def _rehydrate(self, outbox_event: OutboxEvent) -> Any:
        from app.domains.events.outbox_handlers import EVENT_CLASS_MAP

        cls = EVENT_CLASS_MAP.get(outbox_event.event_type)
        if cls is None:
            raise ValueError(
                f"No event class for outbox event type '{outbox_event.event_type}'"
            )
        payload = dict(outbox_event.payload or {})
        event = cls(**payload)

        # Restore the envelope on events that carry envelope fields (the
        # standard DomainEvent dataclasses).  Legacy notification events
        # don't — their ``tenant_id`` is restored below.
        for attr in (
            "event_id",
            "school_id",
            "actor_user_id",
            "occurred_at",
            "correlation_id",
        ):
            if hasattr(event, attr):
                setattr(event, attr, getattr(outbox_event, attr))
        if hasattr(event, "tenant_id") and event.tenant_id is None:
            event.tenant_id = outbox_event.school_id
        return event


# Global outbox dispatcher.  The worker process registers handlers at
# startup (see ``register_outbox_handlers``) and runs the consumption loop.
outbox_dispatcher: OutboxDispatcher = OutboxDispatcher()


async def publish_durable(
    event: Any,
    session: AsyncSession,
    **context: Any,
) -> OutboxEvent | None:
    """Module-level helper mirroring ``publish_event`` for durable events."""
    return await outbox_dispatcher.publish_durable(event, session, **context)


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------


class OutboxWorker:
    """Background loop that delivers durable outbox events.

    Runs only inside the dedicated worker process (never inside the API —
    see ``app.main``).  Polls for pending events, delivers them to the
    registered handlers, and periodically reclaims deliveries stuck in
    ``processing`` (worker crash reaper).  Race-safe across multiple worker
    replicas via the atomic claim.
    """

    def __init__(
        self,
        *,
        poll_interval: float = 2.0,
        batch_size: int = 10,
        max_attempts: int = 10,
        reap_interval: float | None = None,
        stale_after: float | None = None,
    ) -> None:
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._reap_interval = (
            reap_interval if reap_interval is not None else 60.0
        )
        self._stale_after = stale_after if stale_after is not None else 600.0
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()
        self._last_reap_at = 0.0

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.is_running:
            logger.warning("OutboxWorker is already running")
            return
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "OutboxWorker started (poll=%ss batch=%d max_attempts=%d "
            "reap=%ss stale=%ss)",
            self._poll_interval, self._batch_size, self._max_attempts,
            self._reap_interval, self._stale_after,
        )

    async def stop(self) -> None:
        if not self.is_running:
            return
        logger.info("OutboxWorker stopping…")
        self._shutdown_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("OutboxWorker stopped")

    async def _run_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                await self._poll()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Outbox poll cycle failed")
            await self._maybe_reap()
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._poll_interval,
                )
            except asyncio.TimeoutError:
                pass

    async def _poll(self) -> None:
        async with _outbox_worker_session() as session:
            repo = OutboxRepository(session)
            for _ in range(self._batch_size):
                event = await repo.claim_next(self._max_attempts)
                if event is None:
                    return
                try:
                    await outbox_dispatcher.deliver(event, session)
                    await repo.complete(event.event_id)
                    logger.info(
                        "Outbox delivered %s [%s]", event.event_id, event.event_type
                    )
                except Exception as exc:
                    logger.warning(
                        "Outbox delivery failed for %s [%s]: %s",
                        event.event_id, event.event_type, exc,
                    )
                    await repo.fail(
                        event.event_id,
                        str(exc)[:2000],
                        max_attempts=self._max_attempts,
                    )

    async def _maybe_reap(self) -> None:
        import time

        now = time.monotonic()
        if now - self._last_reap_at < self._reap_interval:
            return
        self._last_reap_at = now

        stale_before = _now() - datetime.timedelta(seconds=self._stale_after)
        try:
            async with _outbox_worker_session() as session:
                repo = OutboxRepository(session)
                requeued, dead_lettered = await repo.reclaim_stale_processing(
                    stale_before, self._max_attempts
                )
                if requeued or dead_lettered:
                    logger.warning(
                        "Outbox reaper reclaimed %d stuck delivery(s): "
                        "%d requeued, %d dead-lettered",
                        requeued + dead_lettered, requeued, dead_lettered,
                    )
        except Exception:
            logger.exception("Outbox reaper pass failed (non-fatal)")


@asynccontextmanager
async def _outbox_worker_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def new_outbox_event_id() -> str:
    """Generate a unique outbox event id (UUID hex)."""
    return uuid.uuid4().hex
