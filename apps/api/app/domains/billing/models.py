from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domains.jobs.models import JSONType
from app.infrastructure.database import Base


class Plan(Base):
    """A predefined subscription plan with feature entitlements and limits.

    Plans are created by the platform admin and cannot be modified by
    tenants.  Each plan defines:
    * ``features`` — a dict of boolean feature flags
    * ``limits`` — a dict of numeric capacity limits (users, students,
      storage, AI requests, etc.)
    * ``price_inr`` — price in Indian Rupee **paise** (1 INR = 100 paise)
      to avoid floating-point rounding errors.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    features: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=False, default={})
    limits: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=False, default={})

    billing_interval: Mapped[str] = mapped_column(
        String(10), nullable=False, default="monthly"
    )
    price_inr: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Plan id={self.id} code={self.code} price={self.price_inr}>"


class Subscription(Base):
    """A tenant's active (or historical) subscription to a plan.

    Status lifecycle::

        trial  ──>  active  ──>  past_due  ──>  cancelled / expired
          │                                    ▲
          └────────────────────────────────────┘
                     (cancel during trial)

    **Data-integrity rule**: no data is ever deleted when a subscription
    ends.  The tenant's data remains fully accessible for read operations.
    Write operations may be restricted by feature gating.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="RESTRICT"),
        nullable=False, unique=True, index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="trial", index=True
    )

    current_period_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trial_ends_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    payment_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="e.g. razorpay, cashfree"
    )
    payment_provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription id={self.id} campus={self.campus_id} "
            f"plan={self.plan_id} status={self.status}>"
        )


class UsageRecord(Base):
    """Cumulative usage for a tenant within a billing period.

    One row per ``(campus_id, metric, period_start)`` triplet.
    Records are upserted — the ``amount`` is incremented on each usage
    event.
    """

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    metric: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g. users, students, storage_gb, ai_requests"
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    period_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "campus_id", "metric", "period_start",
            name="uq_usage_period_metric",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageRecord id={self.id} campus={self.campus_id} "
            f"metric={self.metric} amount={self.amount}>"
        )


class Invoice(Base):
    """An invoice generated for a subscription billing period.

    Invoices are created by the billing engine when a period ends
    or when a payment is processed.  They are **not** deleted when
    a subscription ends — they serve as a permanent record.
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    amount_inr: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Amount in paise (1 INR = 100 paise)"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )

    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_provider_invoice_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    period_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    paid_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} campus={self.campus_id} "
            f"amount={self.amount_inr} status={self.status}>"
        )


class WebhookEvent(Base):
    """Idempotency ledger for provider webhook deliveries.

    Payment providers may retry deliveries (and an attacker may replay a
    captured payload).  Every signature-verified event is recorded here keyed
    by ``(provider_name, event_id)`` so a duplicate delivery is detected and
    skipped — it can never double-process a payment.  Rows are kept for
    ``retention_days`` and purged by a maintenance job.
    """

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g. razorpay, cashfree"
    )
    event_id: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Provider-assigned event identifier"
    )
    event_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="unknown", comment="e.g. payment.captured"
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True, comment="Raw verified event payload"
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True once the event's side effects have been applied",
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="Tenant resolved from the event payload (nullable for platform events)",
    )
    received_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "provider_name", "event_id", name="uq_webhook_event_delivery"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookEvent id={self.id} provider={self.provider_name} "
            f"event={self.event_id} processed={self.processed}>"
        )
