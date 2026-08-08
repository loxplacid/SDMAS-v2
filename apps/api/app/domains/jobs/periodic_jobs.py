"""Periodic maintenance job implementations.

These jobs are enqueued by the :class:`Scheduler` (worker process only)
with deterministic identity keys scoped to the current cycle, so no
matter how many scheduler instances run (or how often the worker
restarts), each cycle produces exactly one durable job per maintenance
task.  They then execute with the normal job guarantees: atomic claim,
retry with backoff, dead-lettering, tenant-context restoration and the
WORKER system actor.

All three jobs are *platform-level* operations — they iterate across
every tenant's data (billing period ends, past-due subscriptions,
scheduled messages).  That is the explicit trust boundary of the worker
process: the caller that enqueued them is the scheduler (system), and
each row they touch keeps its own ``campus_id``.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job
from app.domains.jobs.registry import BaseJob, register_job

logger = logging.getLogger(__name__)


@register_job
class BillingPeriodEndJob(BaseJob):
    """Roll each due subscription into a new invoice + period.

    The underlying ``process_period_end`` is idempotent per subscription
    (row lock + pending-invoice check), so even a duplicated execution
    cannot double-invoice a period.
    """

    job_type = "billing.period_end"

    async def run(self, job: Job, session: AsyncSession) -> dict[str, Any]:
        from app.domains.billing.service import SubscriptionService

        svc = SubscriptionService(session)
        results = await svc.process_period_end()
        logger.info("billing.period_end: %d subscription(s) invoiced", len(results))
        return {"invoices_created": len(results)}


@register_job
class BillingExpirePastDueJob(BaseJob):
    """Expire subscriptions stuck in ``past_due`` beyond their period end."""

    job_type = "billing.expire_past_due"

    async def run(self, job: Job, session: AsyncSession) -> dict[str, Any]:
        from app.domains.billing.service import SubscriptionService

        svc = SubscriptionService(session)
        expired = await svc.expire_past_due()
        logger.info("billing.expire_past_due: %d subscription(s) expired", len(expired))
        return {"expired": len(expired)}


@register_job
class CommunicationsScheduledJob(BaseJob):
    """Dispatch every due scheduled message (announcements, reminders)."""

    job_type = "communications.scheduled"

    async def run(self, job: Job, session: AsyncSession) -> dict[str, Any]:
        from app.domains.communications.service import CommunicationService

        svc = CommunicationService(session)
        summary = await svc.dispatch_due_schedules()
        logger.info("communications.scheduled: %s", summary)
        return summary


@register_job
class CasesEscalationJob(BaseJob):
    """Escalate open cases past their configured escalation deadline.

    Deterministic rule from the case engine: an open, non-terminal case
    whose ``now - due_at`` exceeds its priority/type escalation window is
    escalated with an immutable event + leadership notification.  The
    underlying ``run_escalation`` is idempotent (already-escalated cases
    are never re-notified), so a duplicated execution is safe.
    """

    job_type = "cases.escalation"

    async def run(self, job: Job, session: AsyncSession) -> dict[str, Any]:
        from app.domains.cases.service import CaseService

        svc = CaseService(session)
        result = await svc.run_escalation(None, actor_name="System")
        logger.info(
            "cases.escalation: %d case(s) escalated",
            result.get("count", 0),
        )
        return result
