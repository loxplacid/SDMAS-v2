"""create billing tables: plans, subscriptions, usage_records, invoices

Revision ID: 027_create_billing
Revises: 026_create_jobs
Create Date: 2026-07-31 06:30:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "027_create_billing"
down_revision: str | None = "026_create_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Plans ──────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("limits", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("billing_interval", sa.String(10), nullable=False, server_default="monthly"),
        sa.Column("price_inr", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
    op.create_index("ix_plans_code", "plans", ["code"])

    # ── Subscriptions ──────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), sa.ForeignKey("campuses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("payment_provider", sa.String(50), nullable=True),
        sa.Column("payment_provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campus_id", name="uq_subscriptions_campus"),
    )
    op.create_index("ix_subscriptions_campus_id", "subscriptions", ["campus_id"])
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    # ── Usage Records ──────────────────────────────────────────────────
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), sa.ForeignKey("campuses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campus_id", "metric", "period_start", name="uq_usage_period_metric"),
    )
    op.create_index("ix_usage_records_campus_id", "usage_records", ["campus_id"])
    op.create_index("ix_usage_records_subscription_id", "usage_records", ["subscription_id"])
    op.create_index("ix_usage_records_metric", "usage_records", ["metric"])

    # ── Invoices ───────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campus_id", sa.Integer(), sa.ForeignKey("campuses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_provider", sa.String(50), nullable=True),
        sa.Column("payment_provider_invoice_id", sa.String(255), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_campus_id", "invoices", ["campus_id"])
    op.create_index("ix_invoices_subscription_id", "invoices", ["subscription_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    # ── Seed default plans ────────────────────────────────────────────
    from sqlalchemy.sql import text

    now = sa.func.now()
    op.execute(
        text("""
            INSERT INTO plans (name, code, description, features, limits,
                               billing_interval, price_inr, trial_days,
                               is_active, sort_order, created_at, updated_at)
            VALUES
            ('Free Trial', 'trial',
             'Get started with basic features for 14 days',
             '{"basic_reports": true, "email_notifications": true, "sms": false, "ai_grading": false, "advanced_reports": false, "api_access": false}',
             '{"users": 10, "students": 100, "storage_gb": 1, "ai_requests": 0}',
             'monthly', 0, 14, 1, 0, :now, :now),

            ('Starter', 'starter',
             'Essential features for small schools',
             '{"basic_reports": true, "email_notifications": true, "sms": false, "ai_grading": false, "advanced_reports": false, "api_access": false}',
             '{"users": 25, "students": 500, "storage_gb": 5, "ai_requests": 100}',
             'monthly', 29900, 0, 1, 1, :now, :now),

            ('Growth', 'growth',
             'Advanced features for growing schools',
             '{"basic_reports": true, "email_notifications": true, "sms": true, "ai_grading": false, "advanced_reports": true, "api_access": true}',
             '{"users": 100, "students": 2000, "storage_gb": 25, "ai_requests": 1000}',
             'monthly', 99900, 0, 1, 2, :now, :now),

            ('Enterprise', 'enterprise',
             'Full platform access for large institutions',
             '{"basic_reports": true, "email_notifications": true, "sms": true, "ai_grading": true, "advanced_reports": true, "api_access": true}',
             '{"users": 500, "students": 10000, "storage_gb": 100, "ai_requests": 10000}',
             'monthly', 299900, 0, 1, 3, :now, :now)
        """),
    )


def downgrade() -> None:
    op.drop_table("invoices")
    op.drop_table("usage_records")
    op.drop_table("subscriptions")
    op.drop_table("plans")
