"""Add double-entry ledger tables.

Revision ID: 061_add_ledger_tables
Revises: 060_add_migration_factory_tables
Create Date: 2026-08-17

TASK 16 (Financial Ledger Foundation) adds a proper double-entry ledger
beside the existing single-entry ``transaction_logs`` running balance.
The existing fee workflows are untouched — this is purely additive.

Four tables:

- ``ledger_accounts``     — chart of accounts (code unique per campus,
  account type constrained to asset/liability/equity/revenue/expense)
- ``accounting_periods``  — named, non-overlapping date ranges with an
  open/closed (locked) status
- ``journal_entries``     — posting headers.  The core accounting
  invariant is enforced at the DB layer: any non-draft entry MUST have
  equal stored totals (``ck_journal_entry_balanced``), and
  ``(campus_id, idempotency_key)`` is unique so retried postings can
  never double-book.
- ``journal_lines``       — the debit/credit legs; each line has a real
  direction and a strictly positive amount (minor currency units).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "061_add_ledger_tables"
down_revision: str | None = "060_add_migration_factory_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "campus_id", "code", name="uq_ledger_account_campus_code"
        ),
        sa.CheckConstraint(
            "account_type IN ('asset','liability','equity','revenue','expense')",
            name="ck_ledger_account_type",
        ),
    )
    op.create_index("ix_ledger_accounts_campus_id", "ledger_accounts", ["campus_id"])
    op.create_index("ix_ledger_accounts_account_type", "ledger_accounts", ["account_type"])

    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "campus_id", "name", name="uq_accounting_period_campus_name"
        ),
        sa.CheckConstraint(
            "start_date <= end_date", name="ck_accounting_period_date_range"
        ),
        sa.CheckConstraint(
            "status IN ('open','closed')", name="ck_accounting_period_status"
        ),
    )
    op.create_index("ix_accounting_periods_campus_id", "accounting_periods", ["campus_id"])
    op.create_index("ix_accounting_periods_status", "accounting_periods", ["status"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entry_number", sa.String(60), nullable=True),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("accounting_periods.id"),
            nullable=True,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_debits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("posted_by", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reversal_of_id",
            sa.Integer(),
            sa.ForeignKey("journal_entries.id"),
            nullable=True,
        ),
        sa.Column(
            "reversed_entry_id",
            sa.Integer(),
            sa.ForeignKey("journal_entries.id"),
            nullable=True,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "campus_id", "idempotency_key", name="uq_journal_entry_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('draft','posted','reversed')", name="ck_journal_entry_status"
        ),
        # The core invariant at the DB layer: every non-draft entry MUST
        # be balanced.
        sa.CheckConstraint(
            "status = 'draft' OR total_debits = total_credits",
            name="ck_journal_entry_balanced",
        ),
    )
    op.create_index("ix_journal_entries_campus_id", "journal_entries", ["campus_id"])
    op.create_index("ix_journal_entries_entry_number", "journal_entries", ["entry_number"])
    op.create_index("ix_journal_entries_period_id", "journal_entries", ["period_id"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])
    op.create_index("ix_journal_entries_source_type", "journal_entries", ["source_type"])
    op.create_index("ix_journal_entries_source_id", "journal_entries", ["source_id"])
    op.create_index("ix_journal_entries_reversal_of_id", "journal_entries", ["reversal_of_id"])
    op.create_index("ix_journal_entries_reversed_entry_id", "journal_entries", ["reversed_entry_id"])

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("ledger_accounts.id"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("ref_type", sa.String(50), nullable=True),
        sa.Column("ref_id", sa.String(100), nullable=True),
        sa.Column("memo", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "direction IN ('debit','credit')", name="ck_journal_line_direction"
        ),
        sa.CheckConstraint("amount > 0", name="ck_journal_line_amount_positive"),
    )
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])
    op.create_index("ix_journal_lines_ref", "journal_lines", ["ref_type", "ref_id"])


def downgrade() -> None:
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("accounting_periods")
    op.drop_table("ledger_accounts")
