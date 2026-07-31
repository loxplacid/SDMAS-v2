from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.billing.gating import get_usage_summary
from app.domains.billing.payments import get_provider
from app.domains.billing.schemas import (
    CancelSubscriptionRequest,
    InvoiceListResponse,
    InvoiceResponse,
    PaymentLinkRequest,
    PaymentLinkResponse,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    SubscriptionChangeRequest,
    SubscriptionResponse,
    UsageSummaryResponse,
)
from app.domains.billing.service import (
    InvoiceService,
    PlanService,
    SubscriptionService,
    UsageService,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_current_tenant
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/billing", tags=["billing"])


# ── Helpers ────────────────────────────────────────────────────────────


async def _get_plan_svc(session: AsyncSession = Depends(get_session)) -> PlanService:
    return PlanService(session)


async def _get_sub_svc(session: AsyncSession = Depends(get_session)) -> SubscriptionService:
    return SubscriptionService(session)


async def _get_inv_svc(session: AsyncSession = Depends(get_session)) -> InvoiceService:
    return InvoiceService(session)


async def _get_usage_svc(session: AsyncSession = Depends(get_session)) -> UsageService:
    return UsageService(session)


# ── Plans (public) ─────────────────────────────────────────────────────


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    svc: PlanService = Depends(_get_plan_svc),
) -> list[PlanResponse]:
    plans = await svc.list_available()
    return [PlanResponse.model_validate(p) for p in plans]


@router.get("/plans/{code}", response_model=PlanResponse)
async def get_plan(
    code: str,
    svc: PlanService = Depends(_get_plan_svc),
) -> PlanResponse:
    plan = await svc.get_by_code(code)
    if plan is None:
        raise NotFoundError(f"Plan '{code}' not found")
    return PlanResponse.model_validate(plan)


# ── Plans (admin) ──────────────────────────────────────────────────────


@router.post("/admin/plans", response_model=PlanResponse)
async def create_plan(
    data: PlanCreate,
    _: User = Depends(require_role("admin")),
    svc: PlanService = Depends(_get_plan_svc),
) -> PlanResponse:
    plan = await svc.create(data)
    return PlanResponse.model_validate(plan)


@router.patch("/admin/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    _: User = Depends(require_role("admin")),
    svc: PlanService = Depends(_get_plan_svc),
) -> PlanResponse:
    plan = await svc.update(plan_id, data)
    return PlanResponse.model_validate(plan)


# ── Subscription (tenant) ──────────────────────────────────────────────


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    tenant: TenantContext = Depends(get_current_tenant),
    svc: SubscriptionService = Depends(_get_sub_svc),
) -> SubscriptionResponse:
    if not tenant.is_tenant_scoped:
        raise NotFoundError("No campus context available")
    sub = await svc.get_or_create_trial(tenant.campus_id)  # type: ignore[arg-type]
    return SubscriptionResponse.model_validate(sub)


@router.post("/subscription/change", response_model=SubscriptionResponse)
async def change_plan(
    data: SubscriptionChangeRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    svc: SubscriptionService = Depends(_get_sub_svc),
) -> SubscriptionResponse:
    if not tenant.is_tenant_scoped:
        raise NotFoundError("No campus context available")
    sub = await svc.change_plan(tenant.campus_id, data)  # type: ignore[arg-type]
    return SubscriptionResponse.model_validate(sub)


@router.post("/subscription/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    data: CancelSubscriptionRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    svc: SubscriptionService = Depends(_get_sub_svc),
) -> SubscriptionResponse:
    if not tenant.is_tenant_scoped:
        raise NotFoundError("No campus context available")
    sub = await svc.cancel(tenant.campus_id, data)  # type: ignore[arg-type]
    return SubscriptionResponse.model_validate(sub)


@router.post("/subscription/renew", response_model=SubscriptionResponse)
async def renew_subscription(
    tenant: TenantContext = Depends(get_current_tenant),
    svc: SubscriptionService = Depends(_get_sub_svc),
) -> SubscriptionResponse:
    if not tenant.is_tenant_scoped:
        raise NotFoundError("No campus context available")
    sub = await svc.renew(tenant.campus_id)  # type: ignore[arg-type]
    return SubscriptionResponse.model_validate(sub)


# ── Usage ──────────────────────────────────────────────────────────────


@router.get("/usage", response_model=list[UsageSummaryResponse])
async def get_usage(
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    return await get_usage_summary(tenant)


# ── Invoices ───────────────────────────────────────────────────────────


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tenant: TenantContext = Depends(get_current_tenant),
    svc: InvoiceService = Depends(_get_inv_svc),
) -> InvoiceListResponse:
    if not tenant.is_tenant_scoped:
        return InvoiceListResponse(items=[], total=0)
    items, total = await svc.list_by_campus(
        tenant.campus_id, skip=skip, limit=limit  # type: ignore[arg-type]
    )
    return InvoiceListResponse(
        items=[InvoiceResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    svc: InvoiceService = Depends(_get_inv_svc),
) -> InvoiceResponse:
    invoice = await svc.get(invoice_id)
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")
    return InvoiceResponse.model_validate(invoice)


# ── Payment links ──────────────────────────────────────────────────────


@router.post("/payment-link", response_model=PaymentLinkResponse)
async def create_payment_link(
    data: PaymentLinkRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
) -> PaymentLinkResponse:
    provider = get_provider("razorpay")
    if provider is None:
        raise NotFoundError("No payment provider configured")

    result = await provider.create_payment_link(
        amount_inr=data.amount_inr,
        description=data.description,
        customer_email=current_user.email,
    )
    return PaymentLinkResponse(url=result["url"], id=result["id"])


# ── Webhook ────────────────────────────────────────────────────────────


@router.post("/webhook/{provider_name}")
async def payment_webhook(
    provider_name: str,
    request: Request,
) -> dict[str, str]:
    provider = get_provider(provider_name)
    if provider is None:
        raise NotFoundError(f"Unknown payment provider '{provider_name}'")

    raw_body = (await request.body()).decode("utf-8")
    signature = request.headers.get("X-Razorpay-Signature") or ""

    event = await provider.verify_webhook(raw_body, signature)
    return {"status": "received", "event": event.get("event", "unknown")}
