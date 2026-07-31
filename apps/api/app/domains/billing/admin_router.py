from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_role
from app.domains.auth.models import User
from app.domains.billing.repository import PlanRepository, SubscriptionRepository
from app.domains.billing.schemas import PlanResponse, SubscriptionResponse
from app.domains.billing.service import SubscriptionService
from app.infrastructure.database import get_session

router = APIRouter(prefix="/billing/admin", tags=["billing-admin"])


@router.get("/plans", response_model=list[PlanResponse])
async def list_all_plans(
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> list[PlanResponse]:
    repo = PlanRepository(session)
    plans = await repo.list_all()
    return [PlanResponse.model_validate(p) for p in plans]


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    status: str | None = Query(None),
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> list[SubscriptionResponse]:
    repo = SubscriptionRepository(session)
    if status:
        subs = await repo.list_by_status(status)
    else:
        subs = await repo.list_active_and_trial()
    return [SubscriptionResponse.model_validate(s) for s in subs]


@router.post("/subscriptions/{sub_id}/expire")
async def expire_subscription(
    sub_id: int,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    repo = SubscriptionRepository(session)
    sub = await repo.get_by_id(sub_id)
    if sub is None:
        return {"error": "not_found"}
    await repo.update_status(sub_id, "expired")
    return {"status": "expired"}


@router.post("/subscriptions/{sub_id}/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    sub_id: int,
    _: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    repo = SubscriptionRepository(session)
    sub = await repo.get_by_id(sub_id)
    if sub is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Subscription {sub_id} not found")
    svc = SubscriptionService(session)
    updated = await svc.renew(sub.campus_id)
    return SubscriptionResponse.model_validate(updated)
