from __future__ import annotations

import datetime
import logging
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PaymentRequiredError
from app.domains.billing.models import Invoice, Plan, Subscription, UsageRecord
from app.domains.billing.repository import (
    InvoiceRepository,
    PlanRepository,
    SubscriptionRepository,
    UsageRepository,
)
from app.domains.billing.schemas import (
    PlanCreate,
    PlanUpdate,
    SubscriptionChangeRequest,
    CancelSubscriptionRequest,
)

logger = logging.getLogger(__name__)


# ── Plan Service ──────────────────────────────────────────────────────


class PlanService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PlanRepository(session)

    async def create(self, data: PlanCreate) -> Plan:
        now = datetime.datetime.now(datetime.timezone.utc)
        plan = Plan(
            name=data.name,
            code=data.code,
            description=data.description,
            features=data.features or {},
            limits=data.limits or {},
            billing_interval=data.billing_interval,
            price_inr=data.price_inr,
            trial_days=data.trial_days,
            is_active=data.is_active,
            sort_order=data.sort_order,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create(plan)

    async def update(self, plan_id: int, data: PlanUpdate) -> Plan:
        plan = await self.repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError(f"Plan {plan_id} not found")

        for field in ("name", "description", "billing_interval", "trial_days"):
            val = getattr(data, field, None)
            if val is not None:
                setattr(plan, field, val)

        if data.features is not None:
            plan.features = data.features
        if data.limits is not None:
            plan.limits = data.limits
        if data.price_inr is not None:
            plan.price_inr = data.price_inr
        if data.is_active is not None:
            plan.is_active = data.is_active
        if data.sort_order is not None:
            plan.sort_order = data.sort_order

        plan.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.flush()
        return plan

    async def get_by_code(self, code: str) -> Plan | None:
        return await self.repo.get_by_code(code)

    async def list_available(self) -> Sequence[Plan]:
        return await self.repo.list_active()


# ── Subscription Service ──────────────────────────────────────────────


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sub_repo = SubscriptionRepository(session)
        self.plan_repo = PlanRepository(session)

    async def get_or_create_trial(
        self, campus_id: int, plan_code: str = "starter"
    ) -> Subscription:
        existing = await self.sub_repo.get_by_campus(campus_id)
        if existing is not None:
            return existing

        plan = await self.plan_repo.get_by_code(plan_code)
        if plan is None:
            raise NotFoundError(f"Plan '{plan_code}' not found")

        now = datetime.datetime.now(timezone.utc)
        trial_end = now + datetime.timedelta(days=plan.trial_days) if plan.trial_days > 0 else now

        sub = Subscription(
            campus_id=campus_id,
            plan_id=plan.id,
            status="trial" if plan.trial_days > 0 else "active",
            current_period_start=now,
            current_period_end=await self._period_end(now, plan),
            trial_ends_at=trial_end if plan.trial_days > 0 else None,
            created_at=now,
            updated_at=now,
        )
        created = await self.sub_repo.create(sub)
        logger.info("Created trial subscription for campus %d (plan=%s)", campus_id, plan_code)
        return created

    async def get_by_campus(self, campus_id: int) -> Subscription | None:
        return await self.sub_repo.get_by_campus(campus_id)

    async def change_plan(
        self, campus_id: int, data: SubscriptionChangeRequest
    ) -> Subscription:
        sub = await self.sub_repo.get_by_campus(campus_id)
        if sub is None:
            raise NotFoundError("No subscription found for this campus")

        plan = await self.plan_repo.get_by_code(data.plan_code)
        if plan is None:
            raise NotFoundError(f"Plan '{data.plan_code}' not found")

        sub.plan_id = plan.id
        sub.updated_at = datetime.datetime.now(timezone.utc)
        await self.session.flush()
        logger.info("Campus %d changed plan to %s", campus_id, data.plan_code)
        return sub

    async def cancel(
        self, campus_id: int, data: CancelSubscriptionRequest
    ) -> Subscription:
        sub = await self.sub_repo.get_by_campus(campus_id)
        if sub is None:
            raise NotFoundError("No subscription found for this campus")

        now = datetime.datetime.now(timezone.utc)

        if data.cancel_at_period_end:
            sub.cancel_at_period_end = True
            sub.cancelled_at = now
            logger.info(
                "Campus %d subscription will cancel at period end (%s)",
                campus_id, sub.current_period_end,
            )
        else:
            sub.status = "cancelled"
            sub.cancelled_at = now
            sub.cancel_at_period_end = False
            logger.info("Campus %d subscription cancelled immediately", campus_id)

        sub.updated_at = now
        await self.session.flush()
        return sub

    async def renew(self, campus_id: int) -> Subscription:
        sub = await self.sub_repo.get_by_campus(campus_id)
        if sub is None:
            raise NotFoundError("No subscription found for this campus")

        if sub.status == "active" and not sub.cancel_at_period_end:
            return sub

        now = datetime.datetime.now(timezone.utc)
        plan = await self.plan_repo.get_by_id(sub.plan_id)
        if plan is None:
            raise NotFoundError("Associated plan not found")

        sub.status = "active"
        sub.cancel_at_period_end = False
        sub.cancelled_at = None
        sub.current_period_start = now
        sub.current_period_end = await self._period_end(now, plan)
        sub.updated_at = now
        await self.session.flush()
        logger.info("Campus %d subscription renewed", campus_id)
        return sub

    async def expire_past_due(self) -> list[Subscription]:
        now = datetime.datetime.now(timezone.utc)
        expired = await self.sub_repo.list_by_status("past_due")
        expired_list: list[Subscription] = []
        for sub in expired:
            if sub.current_period_end < now:
                await self.sub_repo.update_status(sub.id, "expired")
                expired_list.append(sub)
                logger.info("Subscription %d expired (past_due beyond period end)", sub.id)
        return expired_list

    async def process_period_end(self) -> list[tuple[Subscription, Invoice]]:
        now = datetime.datetime.now(timezone.utc)
        active = await self.sub_repo.list_active_and_trial()
        results: list[tuple[Subscription, Invoice]] = []
        for sub in active:
            if sub.current_period_end > now:
                continue
            plan = await self.plan_repo.get_by_id(sub.plan_id)
            if plan is None:
                continue

            invoice = Invoice(
                campus_id=sub.campus_id,
                subscription_id=sub.id,
                amount_inr=plan.price_inr,
                status="pending",
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                due_at=sub.current_period_end + datetime.timedelta(days=7),
                created_at=now,
                updated_at=now,
            )
            self.session.add(invoice)

            new_start = sub.current_period_end
            new_end = await self._period_end(new_start, plan)
            sub.current_period_start = new_start
            sub.current_period_end = new_end
            sub.updated_at = now

            if sub.cancel_at_period_end:
                sub.status = "cancelled"
                logger.info("Subscription %d cancelled at period end", sub.id)

            results.append((sub, invoice))

        if results:
            await self.session.flush()
        return results

    async def _period_end(
        self,
        from_date: datetime.datetime,
        plan: Plan,
    ) -> datetime.datetime:
        if plan.billing_interval == "yearly":
            return from_date + datetime.timedelta(days=365)
        return from_date + datetime.timedelta(days=30)


# ── Usage Service ─────────────────────────────────────────────────────


class UsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UsageRepository(session)

    async def track(
        self,
        campus_id: int,
        subscription_id: int,
        metric: str,
        delta: float = 1.0,
    ) -> float:
        now = datetime.datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)

        await self.repo.record_usage(
            campus_id=campus_id,
            subscription_id=subscription_id,
            metric=metric,
            delta=delta,
            period_start=period_start,
            period_end=period_end,
        )
        return await self.repo.get_usage(
            campus_id=campus_id,
            metric=metric,
            period_start=period_start,
        )

    async def get_usage(
        self,
        campus_id: int,
        metric: str,
    ) -> float:
        now = datetime.datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return await self.repo.get_usage(
            campus_id=campus_id,
            metric=metric,
            period_start=period_start,
        )


# ── Invoice Service ───────────────────────────────────────────────────


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InvoiceRepository(session)

    async def list_by_campus(
        self,
        campus_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Invoice], int]:
        return await self.repo.list_by_campus(campus_id, skip=skip, limit=limit)

    async def get(self, invoice_id: int) -> Invoice | None:
        return await self.repo.get_by_id(invoice_id)

    async def mark_paid(
        self,
        invoice_id: int,
        provider: str,
        provider_invoice_id: str,
    ) -> Invoice:
        invoice = await self.repo.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        await self.repo.update_status(
            invoice_id,
            "paid",
            payment_provider=provider,
            payment_provider_invoice_id=provider_invoice_id,
            paid_at=datetime.datetime.now(timezone.utc),
        )
        return await self.repo.get_by_id(invoice_id)  # type: ignore[return-value]


import datetime as _dt_mod
timezone = _dt_mod.timezone
