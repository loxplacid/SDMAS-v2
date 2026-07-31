from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Plan ──────────────────────────────────────────────────────────────


class PlanCreate(BaseModel):
    name: str
    code: str = Field(..., max_length=50)
    description: str | None = None
    features: dict[str, Any] = {}
    limits: dict[str, Any] = {}
    billing_interval: str = "monthly"
    price_inr: int = Field(default=0, ge=0)
    trial_days: int = Field(default=14, ge=0)
    is_active: bool = True
    sort_order: int = 0


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    features: dict[str, Any] | None = None
    limits: dict[str, Any] | None = None
    billing_interval: str | None = None
    price_inr: int | None = Field(default=None, ge=0)
    trial_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str | None = None
    features: dict[str, Any] = {}
    limits: dict[str, Any] = {}
    billing_interval: str
    price_inr: int
    trial_days: int
    is_active: bool
    sort_order: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Subscription ──────────────────────────────────────────────────────


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: int
    plan_id: int
    status: str
    current_period_start: datetime.datetime
    current_period_end: datetime.datetime
    trial_ends_at: datetime.datetime | None = None
    cancelled_at: datetime.datetime | None = None
    cancel_at_period_end: bool = False
    payment_provider: str | None = None
    payment_provider_subscription_id: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SubscriptionChangeRequest(BaseModel):
    plan_code: str


class CancelSubscriptionRequest(BaseModel):
    cancel_at_period_end: bool = True


# ── Usage ─────────────────────────────────────────────────────────────


class UsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: int
    metric: str
    amount: float
    period_start: datetime.datetime
    period_end: datetime.datetime


class UsageSummaryResponse(BaseModel):
    metric: str
    used: float
    limit: float
    remaining: float
    period_start: datetime.datetime
    period_end: datetime.datetime


# ── Invoice ───────────────────────────────────────────────────────────


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: int
    subscription_id: int
    amount_inr: int
    status: str
    payment_provider: str | None = None
    payment_provider_invoice_id: str | None = None
    period_start: datetime.datetime
    period_end: datetime.datetime
    due_at: datetime.datetime
    paid_at: datetime.datetime | None = None
    created_at: datetime.datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int


# ── Payment ───────────────────────────────────────────────────────────


class PaymentLinkRequest(BaseModel):
    amount_inr: int = Field(..., ge=100, description="Amount in paise (min 100 = 1 INR)")
    description: str = ""


class PaymentLinkResponse(BaseModel):
    url: str
    id: str


class WebhookEvent(BaseModel):
    provider: str
    raw_body: str
    signature: str | None = None
