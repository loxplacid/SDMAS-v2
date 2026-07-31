from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PaymentRequiredError
from app.domains.auth.models import User
from app.domains.billing.repository import PlanRepository, SubscriptionRepository, UsageRepository
from app.domains.billing.service import UsageService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_current_tenant
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


class require_feature:
    """FastAPI dependency that checks if the tenant's plan entitles
    them to a specific feature.

    Usage::

        @router.get("/reports")
        async def generate_report(
            _: User = Depends(require_feature("advanced_reports")),
            ...
        ): ...

    Returns a 402 Payment Required response when the feature is not
    available on the tenant's current plan.
    """

    def __init__(self, feature_name: str) -> None:
        self.feature_name = feature_name

    async def __call__(
        self,
        request: Request,
        tenant: TenantContext = Depends(get_current_tenant),
        session: AsyncSession = Depends(get_session),
    ) -> None:
        if not tenant.is_tenant_scoped:
            return

        from app.domains.billing.repository import PlanRepository, SubscriptionRepository

        sub_repo = SubscriptionRepository(session)
        plan_repo = PlanRepository(session)

        sub = await sub_repo.get_by_campus(tenant.campus_id)  # type: ignore[arg-type]
        if sub is None:
            raise PaymentRequiredError(
                detail="No active subscription for this campus"
            )

        if sub.status not in ("trial", "active"):
            raise PaymentRequiredError(
                detail=f"Subscription is {sub.status}. "
                       f"Please renew to access this feature."
            )

        plan = await plan_repo.get_by_id(sub.plan_id)
        if plan is None:
            raise NotFoundError("Associated plan not found")

        features = plan.features or {}
        if not features.get(self.feature_name, False):
            raise PaymentRequiredError(
                detail=f"Feature '{self.feature_name}' is not available "
                       f"on your current plan ({plan.name}). "
                       f"Please upgrade to access it."
            )


class require_usage_limit:
    """FastAPI dependency that checks a usage metric against the plan limit.

    Usage::

        @router.post("/students")
        async def create_student(
            _: None = Depends(require_usage_limit("students", delta=1)),
            ...
        ): ...

    The dependency increments the usage counter *after* the handler
    completes successfully.  If the new total would exceed the plan
    limit, a 402 Payment Required is raised *before* the handler runs.
    """

    def __init__(self, metric: str, delta: float = 1.0) -> None:
        self.metric = metric
        self.delta = delta

    async def __call__(
        self,
        request: Request,
        tenant: TenantContext = Depends(get_current_tenant),
        session: AsyncSession = Depends(get_session),
    ) -> None:
        if not tenant.is_tenant_scoped:
            return

        from app.domains.billing.repository import PlanRepository, SubscriptionRepository

        sub_repo = SubscriptionRepository(session)
        plan_repo = PlanRepository(session)
        usage_repo = UsageRepository(session)

        sub = await sub_repo.get_by_campus(tenant.campus_id)  # type: ignore[arg-type]
        if sub is None:
            raise PaymentRequiredError(
                detail="No active subscription for this campus"
            )

        plan = await plan_repo.get_by_id(sub.plan_id)
        if plan is None:
            raise NotFoundError("Associated plan not found")

        limits = plan.limits or {}
        limit = limits.get(self.metric)
        if limit is None:
            return

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        current_usage = await usage_repo.get_usage(
            campus_id=tenant.campus_id,  # type: ignore[arg-type]
            metric=self.metric,
            period_start=period_start,
        )

        if (current_usage + self.delta) > limit:
            raise PaymentRequiredError(
                detail=f"Usage limit reached for '{self.metric}': "
                       f"{current_usage:.0f}/{limit:.0f}. "
                       f"Please upgrade your plan."
            )


async def get_usage_summary(
    tenant: TenantContext = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict[str, dict[str, Any]]:
    """Return a summary of current usage vs plan limits for the tenant."""
    if not tenant.is_tenant_scoped:
        return {}

    sub_repo = SubscriptionRepository(session)
    plan_repo = PlanRepository(session)
    usage_repo = UsageRepository(session)

    sub = await sub_repo.get_by_campus(tenant.campus_id)  # type: ignore[arg-type]
    if sub is None:
        return {}

    plan = await plan_repo.get_by_id(sub.plan_id)
    if plan is None:
        return {}

    limits = plan.limits or {}
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    summary: dict[str, dict[str, Any]] = {}
    for metric, limit_val in limits.items():
        used = await usage_repo.get_usage(
            campus_id=tenant.campus_id,  # type: ignore[arg-type]
            metric=metric,
            period_start=period_start,
        )
        summary[metric] = {
            "used": used,
            "limit": limit_val,
            "remaining": max(0.0, limit_val - used),
        }
    return summary
