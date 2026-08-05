from __future__ import annotations

import datetime
import hashlib
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security.client_ip import get_client_ip

logger = logging.getLogger(__name__)
from app.domains.auth.dependencies import get_current_user, require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import PLATFORM_MANAGE
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
from app.multi_tenant.dependencies import get_current_tenant, require_tenant_context
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


# Plan pricing / entitlements are PLATFORM data: a tenant ``admin`` (even
# the campus owner) must never be able to create or edit plans, because
# that would let a tenant dictate its own prices and feature limits.
# Only an explicit ``platform.manage`` grant may touch them.


@router.post("/admin/plans", response_model=PlanResponse)
async def create_plan(
    data: PlanCreate,
    _: User = Depends(require_permission(PLATFORM_MANAGE)),
    svc: PlanService = Depends(_get_plan_svc),
) -> PlanResponse:
    plan = await svc.create(data)
    return PlanResponse.model_validate(plan)


@router.patch("/admin/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    _: User = Depends(require_permission(PLATFORM_MANAGE)),
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
    tenant: TenantContext = Depends(get_current_tenant),
    svc: InvoiceService = Depends(_get_inv_svc),
) -> InvoiceResponse:
    if not tenant.is_tenant_scoped:
        raise NotFoundError("No campus context available")
    invoice = await svc.get(invoice_id)
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found")
    # An invoice belongs to a campus; only that campus (or an explicit
    # platform caller) may view it — never a different tenant.
    if invoice.campus_id != tenant.campus_id and not tenant.platform:
        raise NotFoundError(f"Invoice {invoice_id} not found")
    return InvoiceResponse.model_validate(invoice)


# ── Payment links ──────────────────────────────────────────────────────


@router.post("/payment-link", response_model=PaymentLinkResponse)
async def create_payment_link(
    data: PaymentLinkRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    current_user: User = Depends(get_current_user),
) -> PaymentLinkResponse:
    provider = get_provider("razorpay")
    if provider is None:
        raise NotFoundError("No payment provider configured")

    notes: dict[str, str] = {}
    if tenant.is_tenant_scoped:
        # Tag the payment with the billing campus at creation time so the
        # payment.captured webhook can attribute the capture to the right
        # tenant from the provider payload — never from a client header.
        notes["campus_id"] = str(tenant.campus_id)

    result = await provider.create_payment_link(
        amount_inr=data.amount_inr,
        description=data.description,
        customer_email=current_user.email,
        notes=notes,
    )
    return PaymentLinkResponse(url=result["url"], id=result["id"])


# ── Webhook ────────────────────────────────────────────────────────────

#: Razorpay signs webhooks with an ``X-Razorpay-Signature`` header.  Events
#: signed with an unknown provider are rejected before any processing.
ALLOWED_WEBHOOK_PROVIDERS = {"razorpay", "cashfree"}


@router.post("/webhook/{provider_name}")
async def payment_webhook(
    provider_name: str,
    request: Request,
) -> dict[str, str]:
    """Public webhook receiver for payment providers.

    Security posture:
    * Signature is verified cryptographically over the **raw** request body
      (never the re-serialized JSON) with ``hmac.compare_digest``.
    * Timestamp freshness is enforced when the provider signs one — a
      captured-and-replayed event is rejected as stale.
    * Every verified event is recorded under a content-derived idempotency
      key (``sha256(raw_body)``).  Duplicate or replayed deliveries are
      detected and skipped, so a retry can never double-process a payment.
    * The tenant (``campus_id``) is resolved from the payload, never trusted
      from a client-supplied header.
    * No user session is required — the endpoint is public by design, but the
      only side effects allowed are the payment-state transitions below.
    """
    if provider_name not in ALLOWED_WEBHOOK_PROVIDERS:
        raise NotFoundError(f"Unknown payment provider '{provider_name}'")

    provider = get_provider(provider_name)
    if provider is None:
        raise NotFoundError(f"Unknown payment provider '{provider_name}'")

    raw_body = (await request.body()).decode("utf-8")
    signature = request.headers.get("X-Razorpay-Signature") or ""

    try:
        event = await provider.verify_webhook(raw_body, signature)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc

    if provider.signature_is_stale(event):
        logger.warning("Dropping stale webhook event (possible replay)")
        return {"status": "stale", "event": event.get("event", "unknown")}

    event_name = event.get("event", "unknown")
    event_id = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()

    from app.infrastructure.database import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        is_new = await _apply_webhook_event(
            session,
            provider_name=provider_name,
            event_id=event_id,
            event_name=event_name,
            event=event,
        )
        await _audit_webhook(
            session,
            provider_name=provider_name,
            event=event,
            request=request,
            event_id=event_id,
        )

    if is_new:
        return {"status": "processed", "event": event_name}
    return {"status": "duplicate", "event": event_name}


async def _apply_webhook_event(
    session: AsyncSession,
    provider_name: str,
    event_id: str,
    event_name: str,
    event: dict,
) -> bool:
    """Persist and (first time only) apply a verified webhook event.

    Returns ``True`` when the event was processed for the first time,
    ``False`` for a duplicate delivery.

    The unique ``(provider_name, event_id)`` constraint is the final guard:
    even two concurrently-delivered copies of the same event collapse to a
    single processed record.
    """
    import datetime as _dt
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.domains.billing.models import Subscription, WebhookEvent

    payload = event.get("payload", {}) or {}
    payment_entity = (payload.get("payment") or {}).get("entity") or {}
    notes = payment_entity.get("notes") or {}

    # ── Tenant association: resolved from provider data, never from the client.
    campus_id: int | None = None
    raw_campus = notes.get("campus_id")
    if raw_campus is not None:
        try:
            campus_id = int(raw_campus)
        except (TypeError, ValueError):
            campus_id = None
    if campus_id is None:
        sub_entity = (payload.get("subscription") or {}).get("entity") or {}
        provider_sub_id = sub_entity.get("id")
        if provider_sub_id:
            sub = (
                await session.execute(
                    select(Subscription).where(
                        Subscription.payment_provider_subscription_id
                        == provider_sub_id
                    )
                )
            ).scalar_one_or_none()
            if sub is not None:
                campus_id = sub.campus_id

    # ── Dedup check.
    existing = (
        await session.execute(
            select(WebhookEvent).where(
                WebhookEvent.provider_name == provider_name,
                WebhookEvent.event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Duplicate delivery.  The row always has processed=True because the
        # insert + side effects + flag are committed atomically.
        return False

    try:
        async with session.begin_nested():
            row = WebhookEvent(
                provider_name=provider_name,
                event_id=event_id,
                event_name=event_name,
                payload=event,
                processed=False,
                campus_id=campus_id,
                received_at=_dt.datetime.now(_dt.timezone.utc),
            )
            session.add(row)
            await session.flush()

            if event_name == "payment.captured":
                await _apply_payment_captured(
                    session, payment_entity, campus_id, provider_name
                )
            elif event_name == "payment.failed":
                await _apply_payment_failed(
                    session, payment_entity, campus_id, provider_name
                )

            row.processed = True
        await session.commit()
        return True
    except IntegrityError:
        # A concurrent delivery of the same event won the insert race.
        await session.rollback()
        return False


async def _apply_payment_captured(
    session: AsyncSession,
    payment_entity: dict,
    campus_id: int | None,
    provider_name: str,
) -> None:
    """Idempotent side effects for ``payment.captured``.

    Locates the tenant's subscription from the payment (by provider
    subscription id in notes, or the campus's current subscription) and marks
    the pending invoice paid and the subscription active.
    """
    from sqlalchemy import select

    from app.domains.billing.models import Invoice, Subscription

    sub: Subscription | None = None
    notes = payment_entity.get("notes") or {}
    provider_sub_id = notes.get("subscription_id")
    if provider_sub_id:
        sub = (
            await session.execute(
                select(Subscription).where(
                    Subscription.payment_provider_subscription_id
                    == provider_sub_id
                )
            )
        ).scalar_one_or_none()
    if sub is None and campus_id is not None:
        sub = (
            await session.execute(
                select(Subscription)
                .where(Subscription.campus_id == campus_id)
                .order_by(Subscription.id.desc())
            )
        ).scalars().first()

    if sub is None:
        logger.warning(
            "payment.captured: no subscription found for payment %s",
            payment_entity.get("id"),
        )
        return

    if sub.status in ("cancelled", "expired"):
        logger.warning(
            "payment.captured: ignoring payment for terminated subscription %s",
            sub.id,
        )
        return

    # ── Monetary integrity: never treat the provider's "captured" flag as
    # authoritative on its own.  The captured amount (paise) must cover the
    # invoice being settled — a partial or mismatched capture must not mark
    # an invoice paid or re-activate the subscription.
    payment_amount: int | None = None
    try:
        payment_amount = int(payment_entity.get("amount") or 0)
    except (TypeError, ValueError):
        payment_amount = None

    pending_invoices = (
        await session.execute(
            select(Invoice)
            .where(
                Invoice.subscription_id == sub.id,
                Invoice.status == "pending",
            )
            .order_by(Invoice.id.desc())
        )
    ).scalars().all()

    # Fail CLOSED: an unparseable amount with an unpaid invoice on the line
    # must never settle it — the "captured" flag alone is not authoritative.
    if pending_invoices and payment_amount is None:
        logger.warning(
            "payment.captured: payment %s has no parseable amount — "
            "invoice not marked paid",
            payment_entity.get("id"),
        )
        return

    invoice = None
    if pending_invoices:
        # Prefer the invoice whose amount exactly matches the capture;
        # otherwise fall back to the most recent pending invoice.
        for candidate in pending_invoices:
            if payment_amount is not None and candidate.amount_inr == payment_amount:
                invoice = candidate
                break
        if invoice is None:
            invoice = pending_invoices[0]

        if payment_amount is not None and payment_amount < invoice.amount_inr:
            logger.warning(
                "payment.captured: payment %s amount %s < invoice %s amount %s — "
                "invoice not marked paid",
                payment_entity.get("id"), payment_amount,
                invoice.id, invoice.amount_inr,
            )
            return

    sub.status = "active"
    sub.cancel_at_period_end = False
    sub.payment_provider = provider_name
    sub.updated_at = datetime.datetime.now(datetime.timezone.utc)

    if invoice is not None:
        invoice.status = "paid"
        invoice.paid_at = datetime.datetime.now(datetime.timezone.utc)
        invoice.updated_at = datetime.datetime.now(datetime.timezone.utc)


async def _apply_payment_failed(
    session: AsyncSession,
    payment_entity: dict,
    campus_id: int | None,
    provider_name: str,
) -> None:
    """Idempotent side effects for ``payment.failed``.

    Marks the tenant's subscription ``past_due``.  A later successful
    ``payment.captured`` returns it to ``active``.
    """
    from sqlalchemy import select

    from app.domains.billing.models import Subscription

    if campus_id is None:
        logger.warning(
            "payment.failed: cannot attribute payment %s to a tenant",
            payment_entity.get("id"),
        )
        return

    sub = (
        await session.execute(
            select(Subscription)
            .where(Subscription.campus_id == campus_id)
            .order_by(Subscription.id.desc())
        )
    ).scalars().first()
    if sub is None or sub.status in ("cancelled", "expired"):
        return
    if sub.status == "active":
        # A late / out-of-order ``payment.failed`` must not downgrade a
        # subscription that a captured payment already activated — money
        # received is more authoritative than money not received, and the
        # billing worker downgrades via unpaid invoices at period end.
        return

    sub.status = "past_due"
    sub.updated_at = datetime.datetime.now(datetime.timezone.utc)


async def _audit_webhook(
    session: AsyncSession,
    provider_name: str,
    event: dict,
    request: Request,
    event_id: str,
) -> None:
    """Record a signature-verified webhook delivery (best-effort).

    The actor is explicitly the ``WEBHOOK`` integration — never a user.
    """
    from app.domains.audit.actors import AuditActor
    from app.domains.audit.service import AuditService

    try:
        svc = AuditService(session)
        event_name = event.get("event", "unknown")
        payload = event.get("payload", {}) or {}
        payment = payload.get("payment", {}) or {}
        await svc.record(
            action="WEBHOOK_RECEIVED",
            resource_type="billing",
            resource_id=payment.get("id"),
            actor=AuditActor.webhook(provider=provider_name),
            # Each delivery is its own audit event; ``event_id`` must be
            # unique even when the payload is a duplicate delivery.
            event_id=hashlib.sha256(
                f"{event_id}:{uuid.uuid4().hex}".encode("utf-8")
            ).hexdigest(),
            details={
                "provider": provider_name,
                "event": event_name,
                "payment_id": payment.get("id"),
                "status": payment.get("status"),
            },
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            commit=True,
        )
    except Exception:
        logger.warning(
            "Failed to write audit entry for webhook (non-fatal)", exc_info=True
        )
