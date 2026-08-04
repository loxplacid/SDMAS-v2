from __future__ import annotations

import datetime
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.billing.models import Invoice, Plan, Subscription, UsageRecord


class PlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, plan: Plan) -> Plan:
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def get_by_id(self, plan_id: int) -> Plan | None:
        result = await self.session.execute(
            select(Plan).where(Plan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Plan | None:
        result = await self.session.execute(
            select(Plan).where(Plan.code == code)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Plan]:
        result = await self.session.execute(
            select(Plan)
            .where(Plan.is_active == True)
            .order_by(Plan.sort_order.asc(), Plan.price_inr.asc())
        )
        return list(result.scalars().all())

    async def list_all(self) -> Sequence[Plan]:
        result = await self.session.execute(
            select(Plan).order_by(Plan.sort_order.asc(), Plan.price_inr.asc())
        )
        return list(result.scalars().all())


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, sub: Subscription) -> Subscription:
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def get_by_id(self, sub_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        return result.scalar_one_or_none()

    async def get_by_campus(self, campus_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.campus_id == campus_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, sub_id: int) -> Subscription | None:
        """Lock a subscription row for the current transaction (SELECT ...
        FOR UPDATE) — used to serialize period-end invoicing so concurrent
        workers cannot double-invoice a billing period."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.id == sub_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        sub_id: int,
        status: str,
        **extra: Any,
    ) -> None:
        values: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc),
        }
        values.update(extra)
        await self.session.execute(
            update(Subscription).where(Subscription.id == sub_id).values(**values)
        )
        await self.session.flush()

    async def list_by_status(self, status: str) -> Sequence[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.status == status)
        )
        return list(result.scalars().all())

    async def list_active_and_trial(self) -> Sequence[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.status.in_(["trial", "active"])
            )
        )
        return list(result.scalars().all())


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_usage(
        self,
        campus_id: int,
        subscription_id: int,
        metric: str,
        delta: float,
        period_start: datetime.datetime,
        period_end: datetime.datetime,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)

        stmt = pg_insert(UsageRecord).values(
            campus_id=campus_id,
            subscription_id=subscription_id,
            metric=metric,
            amount=delta,
            period_start=period_start,
            period_end=period_end,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["campus_id", "metric", "period_start"],
            set_={
                "amount": UsageRecord.amount + delta,
                "updated_at": now,
            },
        )

        try:
            await self.session.execute(stmt)
            await self.session.flush()
        except Exception:
            from sqlalchemy import text
            await self.session.execute(
                text("""
                    INSERT INTO usage_records
                        (campus_id, subscription_id, metric, amount,
                         period_start, period_end, created_at, updated_at)
                    VALUES
                        (:campus_id, :subscription_id, :metric, :delta,
                         :period_start, :period_end, :now, :now)
                    ON CONFLICT (campus_id, metric, period_start)
                    DO UPDATE SET
                        amount = usage_records.amount + :delta,
                        updated_at = :now
                """),
                {
                    "campus_id": campus_id,
                    "subscription_id": subscription_id,
                    "metric": metric,
                    "delta": delta,
                    "period_start": period_start,
                    "period_end": period_end,
                    "now": now,
                },
            )
            await self.session.flush()

    async def get_usage(
        self,
        campus_id: int,
        metric: str,
        period_start: datetime.datetime,
    ) -> float:
        result = await self.session.execute(
            select(func.coalesce(UsageRecord.amount, 0.0)).where(
                UsageRecord.campus_id == campus_id,
                UsageRecord.metric == metric,
                UsageRecord.period_start == period_start,
            )
        )
        return result.scalar() or 0.0

    async def list_usage_for_period(
        self,
        campus_id: int,
        period_start: datetime.datetime,
    ) -> Sequence[UsageRecord]:
        result = await self.session.execute(
            select(UsageRecord).where(
                UsageRecord.campus_id == campus_id,
                UsageRecord.period_start == period_start,
            )
        )
        return list(result.scalars().all())


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def get_by_id(self, invoice_id: int) -> Invoice | None:
        result = await self.session.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def list_by_campus(
        self,
        campus_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Invoice], int]:
        query = select(Invoice).where(Invoice.campus_id == campus_id)
        count_query = select(func.count(Invoice.id)).where(
            Invoice.campus_id == campus_id
        )

        query = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)

        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def update_status(
        self,
        invoice_id: int,
        status: str,
        **extra: Any,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        values: dict[str, Any] = {"status": status, "updated_at": now}
        values.update(extra)
        await self.session.execute(
            update(Invoice).where(Invoice.id == invoice_id).values(**values)
        )
        await self.session.flush()
