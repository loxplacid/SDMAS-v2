"""Scheduler tests.

The scheduler runs inside the worker process and enqueues the periodic
maintenance jobs with cycle-scoped identity keys.  These tests prove:

* a cycle enqueues exactly one job per periodic task
* running the cycle again (or from a second scheduler instance) does not
  duplicate — identity-key dedup at enqueue
* the daily / 5-minute keys roll over, so the next cycle creates fresh
  work while the previous cycle stays recorded
* the periodic jobs themselves execute correctly (billing period-end is
  idempotent per subscription; scheduled messages dispatch once)
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager

from sqlalchemy import select

from app.domains.billing.models import Invoice, Plan, Subscription
from app.domains.communications.models import (
    CommunicationMessage,
    MessageSchedule,
)
from app.domains.institution.models import Campus, Institution
from app.domains.jobs.models import Job
from app.domains.jobs.repository import JobRepository
from app.domains.jobs.scheduler import (
    Scheduler,
    _daily_key,
    _five_min_bucket_key,
)
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService
from app.multi_tenant.models import platform_context

NOW = datetime.datetime.now(datetime.timezone.utc)


def _session_ctx(session):
    """A fake session factory returning an async CM yielding *session*."""

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


class TestCycleEnqueue:
    async def test_cycle_enqueues_exactly_one_job_per_task(self, db_session):
        scheduler = Scheduler(
            session_factory=_session_ctx(db_session),
            clock=lambda: NOW,
        )

        # Two cycles back-to-back (idempotent enqueue).
        await scheduler._enqueue_cycle()
        await scheduler._enqueue_cycle()

        rows = (await db_session.execute(select(Job))).scalars().all()
        types = [j.job_type for j in rows]
        assert len(types) == 4
        assert set(types) == {
            "billing.expire_past_due",
            "billing.period_end",
            "cases.escalation",
            "communications.scheduled",
        }
        # Exactly one job per type.
        for t in set(types):
            assert types.count(t) == 1

    async def test_cycle_is_idempotent_across_scheduler_instances(self, db_session):
        """Two scheduler instances racing still produce one row per key."""
        s1 = Scheduler(session_factory=_session_ctx(db_session), clock=lambda: NOW)
        s2 = Scheduler(session_factory=_session_ctx(db_session), clock=lambda: NOW)

        await s1._enqueue_cycle()
        await s2._enqueue_cycle()

        rows = (await db_session.execute(select(Job))).scalars().all()
        assert len(rows) == 4
        assert len({j.identity_key for j in rows}) == 4
        assert "cases.escalation" in {j.job_type for j in rows}

    async def test_keys_roll_over_daily_and_five_minute(self):
        """Keys must be scoped to their cycle so the next cycle gets fresh
        work without colliding with the previous cycle's completed job."""
        day1 = datetime.datetime(2026, 8, 3, 10, 0, tzinfo=datetime.timezone.utc)
        day2 = datetime.datetime(2026, 8, 4, 10, 0, tzinfo=datetime.timezone.utc)
        assert _daily_key("billing.period_end", day1) != _daily_key("billing.period_end", day2)

        bucket_a = datetime.datetime(2026, 8, 3, 10, 4, tzinfo=datetime.timezone.utc)
        bucket_b = datetime.datetime(2026, 8, 3, 10, 7, tzinfo=datetime.timezone.utc)
        # 10:04 floors to the 10:00 window, 10:07 to the 10:05 window.
        assert _five_min_bucket_key("communications.scheduled", bucket_a) != (
            _five_min_bucket_key("communications.scheduled", bucket_b)
        )
        # Same window → same key (10:07 and 10:05 both floor to 10:05).
        same = datetime.datetime(2026, 8, 3, 10, 5, tzinfo=datetime.timezone.utc)
        assert _five_min_bucket_key("communications.scheduled", bucket_b) == (
            _five_min_bucket_key("communications.scheduled", same)
        )
        # Different window → different key (10:04 → 10:00 vs 10:05 → 10:05).
        assert _five_min_bucket_key("communications.scheduled", bucket_a) != (
            _five_min_bucket_key("communications.scheduled", same)
        )

    async def test_completed_cycle_job_does_not_block_next_cycle(self, db_session):
        """After a cycle's job completes, re-enqueuing the same key returns
        the completed row (no crash, no duplicate)."""
        svc = JobService(db_session, platform_context())
        key = _daily_key("billing.period_end", NOW)
        first = await svc.create_job(JobCreate(job_type="billing.period_end", identity_key=key))
        first.status = "completed"
        await db_session.commit()

        again = await svc.create_job(JobCreate(job_type="billing.period_end", identity_key=key))
        await db_session.commit()
        assert again.id == first.id


# ---------------------------------------------------------------------------
# Billing period-end job
# ---------------------------------------------------------------------------


async def _seed_plan_and_subscription(
    db_session,
    *,
    campus_id: int,
    status: str = "active",
    period_end_offset: datetime.timedelta | None = None,
) -> tuple[Plan, Subscription]:
    plan = Plan(
        name="Standard",
        code=f"standard-{campus_id}",
        billing_interval="monthly",
        price_inr=10000,
        trial_days=0,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(plan)
    await db_session.flush()

    end = NOW - (period_end_offset or datetime.timedelta(days=1))
    sub = Subscription(
        campus_id=campus_id,
        plan_id=plan.id,
        status=status,
        current_period_start=end - datetime.timedelta(days=30),
        current_period_end=end,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(sub)
    await db_session.flush()
    return plan, sub


class TestPeriodicJobs:
    async def test_billing_period_end_invoices_each_due_subscription(self, db_session):
        """billing.period_end rolls each due subscription into a fresh
        invoice exactly once (idempotent under re-execution)."""
        inst = Institution(name="Test District", code="TST")
        db_session.add(inst)
        await db_session.flush()
        c1 = Campus(institution_id=inst.id, name="C1", code="C1")
        db_session.add(c1)
        await db_session.flush()

        await _seed_plan_and_subscription(db_session, campus_id=c1.id)

        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())
        job = await svc.create_job(
            JobCreate(
                job_type="billing.period_end",
                identity_key=_daily_key("billing.period_end", NOW),
                max_retries=2,
            )
        )
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        invoices = (await db_session.execute(select(Invoice))).scalars().all()
        assert len(invoices) == 1
        assert invoices[0].campus_id == c1.id
        assert invoices[0].status == "pending"

        # Re-execution must not double-invoice (pending-invoice guard).
        row = (await db_session.execute(select(Job).where(Job.id == job.id))).scalar_one()
        row.status = "pending"
        row.scheduled_at = NOW
        await db_session.commit()
        claimed2 = await repo.acquire_next()
        assert claimed2 is not None
        await svc.execute_job(claimed2.id)

        invoices = (await db_session.execute(select(Invoice))).scalars().all()
        assert len(invoices) == 1

    async def test_billing_expire_past_due_expires_overdue_subscriptions(self, db_session):
        inst = Institution(name="Test District", code="TST2")
        db_session.add(inst)
        await db_session.flush()
        c1 = Campus(institution_id=inst.id, name="C1", code="C1")
        db_session.add(c1)
        await db_session.flush()

        await _seed_plan_and_subscription(
            db_session,
            campus_id=c1.id,
            status="past_due",
            period_end_offset=datetime.timedelta(days=10),
        )

        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())
        await svc.create_job(
            JobCreate(
                job_type="billing.expire_past_due",
                identity_key=_daily_key("billing.expire_past_due", NOW),
            )
        )
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        subs = (await db_session.execute(select(Subscription))).scalars().all()
        assert all(s.status == "expired" for s in subs)

    async def test_communications_scheduled_dispatches_due_messages(self, db_session):
        """communications.scheduled delivers messages whose schedule is due,
        marks the schedule completed, and never double-delivers."""
        inst = Institution(name="Test District", code="TST3")
        db_session.add(inst)
        await db_session.flush()
        c1 = Campus(institution_id=inst.id, name="C1", code="C1")
        db_session.add(c1)
        await db_session.flush()

        msg = CommunicationMessage(
            subject="Reminder",
            body="Your reminder",
            message_type="announcement",
            priority="normal",
            channels=["in_app"],
            status="scheduled",
            campus_id=c1.id,
            sender_id=1,
        )
        db_session.add(msg)
        await db_session.flush()
        db_session.add(
            MessageSchedule(
                message_id=msg.id,
                scheduled_at=NOW - datetime.timedelta(minutes=5),
                status="pending",
            )
        )
        await db_session.commit()

        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())
        job = await svc.create_job(
            JobCreate(
                job_type="communications.scheduled",
                identity_key=_five_min_bucket_key("communications.scheduled", NOW),
            )
        )
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        schedules = (await db_session.execute(select(MessageSchedule))).scalars().all()
        assert len(schedules) == 1
        assert schedules[0].status == "completed"

        # Re-running the job must not re-dispatch a completed schedule.
        row = (await db_session.execute(select(Job).where(Job.id == job.id))).scalar_one()
        row.status = "pending"
        row.scheduled_at = NOW
        await db_session.commit()
        claimed2 = await repo.acquire_next()
        assert claimed2 is not None
        await svc.execute_job(claimed2.id)
        schedules = (await db_session.execute(select(MessageSchedule))).scalars().all()
        assert len(schedules) == 1
        assert schedules[0].status == "completed"

    async def test_communications_skips_future_schedules(self, db_session):
        inst = Institution(name="Test District", code="TST4")
        db_session.add(inst)
        await db_session.flush()
        c1 = Campus(institution_id=inst.id, name="C1", code="C1")
        db_session.add(c1)
        await db_session.flush()

        msg = CommunicationMessage(
            subject="Later",
            body="Not yet",
            message_type="announcement",
            priority="normal",
            channels=["in_app"],
            status="scheduled",
            campus_id=c1.id,
            sender_id=1,
        )
        db_session.add(msg)
        await db_session.flush()
        db_session.add(
            MessageSchedule(
                message_id=msg.id,
                scheduled_at=NOW + datetime.timedelta(hours=2),
                status="pending",
            )
        )
        await db_session.commit()

        svc = JobService(db_session, platform_context())
        repo = JobRepository(db_session, platform_context())
        await svc.create_job(
            JobCreate(
                job_type="communications.scheduled",
                identity_key=_five_min_bucket_key("communications.scheduled", NOW),
            )
        )
        claimed = await repo.acquire_next()
        assert claimed is not None
        await svc.execute_job(claimed.id)

        schedules = (await db_session.execute(select(MessageSchedule))).scalars().all()
        assert schedules[0].status == "pending"  # untouched


# ---------------------------------------------------------------------------
# Worker separation
# ---------------------------------------------------------------------------


class TestWorkerSeparation:
    def test_api_does_not_start_workers_by_default(self):
        """The API must never launch its own competing worker replicas."""
        from app.config import settings

        assert settings.worker_in_process is False

    def test_dedicated_worker_entrypoint_runs_scheduler(self, monkeypatch):
        """The worker entrypoint wires job worker + outbox worker + scheduler."""
        import app.domains.events.outbox as outbox_module
        import app.domains.jobs.scheduler as scheduler_module
        import app.domains.jobs.worker as worker_module

        started: list[str] = []

        def _fake_class(name: str):
            """Build a fake worker class that records when it starts."""

            def __init__(self, *a, **k):
                pass

            def start(self):
                started.append(name)

            async def stop(self):
                pass

            return type(name, (), {"__init__": __init__, "start": start, "stop": stop})

        monkeypatch.setattr(worker_module, "JobWorker", _fake_class("JobWorker"))
        monkeypatch.setattr(outbox_module, "OutboxWorker", _fake_class("OutboxWorker"))
        monkeypatch.setattr(scheduler_module, "Scheduler", _fake_class("Scheduler"))

        import asyncio
        import signal

        monkeypatch.setattr(signal, "signal", lambda *a, **k: None)
        original_wait = asyncio.Event.wait

        async def _immediate_wait(self, *a, **k):
            if started:
                return True
            return await original_wait(self, *a, **k)

        monkeypatch.setattr(asyncio.Event, "wait", _immediate_wait)

        worker_module.main()
        assert "JobWorker" in started
        assert "OutboxWorker" in started
        assert "Scheduler" in started
