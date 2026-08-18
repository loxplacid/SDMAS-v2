"""Double-entry ledger — ORM models (TASK 16).

A proper double-entry ledger built as a new domain without touching the
existing single-entry ``transaction_logs`` running balance or the fee
workflows that write it.  Four tables implement the core accounting
concepts:

- ``ledger_accounts``      — the chart of accounts: code, name, account
  type (asset / liability / equity / revenue / expense).  The normal
  balance side is *derived* from the type (asset/expense → debit;
  liability/equity/revenue → credit), so a chart row can never claim a
  normal side that contradicts its type.
- ``accounting_periods``   — named date ranges with an open/closed
  status.  Closing a period (lock/finalization) blocks any new posting
  dated inside it.
- ``journal_entries``      — the posting header: period, entry date,
  status (draft / posted / reversed), source reference, idempotency
  key, totals and reversal linkage.
- ``journal_lines``        — the debit/credit legs.  Each line carries a
  direction, a positive amount (minor currency units) and an optional
  generic reference (ref_type/ref_id) so a line can point at a payment,
  student, invoice etc. without hard-coding a foreign key.

**The accounting invariant is enforced at two layers.**

Service layer (``service.py``): posting recomputes and compares the
debit/credit sums inside the same transaction that flips the entry to
``posted`` — an unbalanced entry can never be posted.

Database layer: ``journal_entries`` carries ``total_debits`` /
``total_credits`` and a CHECK constraint requiring them equal for every
non-draft entry, so a direct SQL write that flips a status (or a bug
that skips the service) cannot persist an unbalanced posted entry.  Each
line is constrained to a real direction and a strictly positive amount.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Account types (chart of accounts).
ACCOUNT_ASSET = "asset"
ACCOUNT_LIABILITY = "liability"
ACCOUNT_EQUITY = "equity"
ACCOUNT_REVENUE = "revenue"
ACCOUNT_EXPENSE = "expense"
ACCOUNT_TYPES: frozenset[str] = frozenset(
    {ACCOUNT_ASSET, ACCOUNT_LIABILITY, ACCOUNT_EQUITY, ACCOUNT_REVENUE, ACCOUNT_EXPENSE}
)

#: Normal (natural) balance side per account type.  A chart row's normal
#: side is derived from its type — never stored independently.
NORMAL_SIDE_DEBIT = "debit"
NORMAL_SIDE_CREDIT = "credit"
TYPE_NORMAL_SIDE: dict[str, str] = {
    ACCOUNT_ASSET: NORMAL_SIDE_DEBIT,
    ACCOUNT_EXPENSE: NORMAL_SIDE_DEBIT,
    ACCOUNT_LIABILITY: NORMAL_SIDE_CREDIT,
    ACCOUNT_EQUITY: NORMAL_SIDE_CREDIT,
    ACCOUNT_REVENUE: NORMAL_SIDE_CREDIT,
}

#: Line directions.
LINE_DEBIT = "debit"
LINE_CREDIT = "credit"
LINE_DIRECTIONS: frozenset[str] = frozenset({LINE_DEBIT, LINE_CREDIT})

#: Entry lifecycle.
ENTRY_DRAFT = "draft"
ENTRY_POSTED = "posted"
ENTRY_REVERSED = "reversed"
ENTRY_STATUSES: frozenset[str] = frozenset(
    {ENTRY_DRAFT, ENTRY_POSTED, ENTRY_REVERSED}
)

#: Accounting period lifecycle.
PERIOD_OPEN = "open"
PERIOD_CLOSED = "closed"
PERIOD_STATUSES: frozenset[str] = frozenset({PERIOD_OPEN, PERIOD_CLOSED})

#: Source-type vocabulary for the ``source_type`` reference on entries.
#: Free-form values are rejected by the service so journal provenance
#: stays a closed catalog (audit-friendly).
SOURCE_MANUAL = "manual"
SOURCE_PAYMENT = "payment"
SOURCE_REFUND = "refund"
SOURCE_TRANSACTION_LOG = "transaction_log"
SOURCE_INVOICE = "invoice"
SOURCE_REVERSAL = "reversal"
SOURCE_TYPES: frozenset[str] = frozenset(
    {
        SOURCE_MANUAL,
        SOURCE_PAYMENT,
        SOURCE_REFUND,
        SOURCE_TRANSACTION_LOG,
        SOURCE_INVOICE,
        SOURCE_REVERSAL,
    }
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class LedgerAccount(Base):
    """One row in the chart of accounts (per campus)."""

    __tablename__ = "ledger_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Business key — e.g. ``1100`` (cash), ``1200`` (receivables),
    #: ``4000`` (fee revenue).  Unique per campus.
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("campus_id", "code", name="uq_ledger_account_campus_code"),
        CheckConstraint(
            "account_type IN ('asset','liability','equity','revenue','expense')",
            name="ck_ledger_account_type",
        ),
    )

    @property
    def normal_side(self) -> str:
        """Derived normal balance side (never stored independently)."""
        return TYPE_NORMAL_SIDE[self.account_type]

    def __repr__(self) -> str:
        return (
            f"<LedgerAccount id={self.id} code={self.code} "
            f"name={self.name} type={self.account_type}>"
        )


class AccountingPeriod(Base):
    """A named, locked date range for posting (fiscal period)."""

    __tablename__ = "accounting_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PERIOD_OPEN, index=True
    )
    closed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("campus_id", "name", name="uq_accounting_period_campus_name"),
        CheckConstraint(
            "start_date <= end_date", name="ck_accounting_period_date_range"
        ),
        CheckConstraint(
            "status IN ('open','closed')", name="ck_accounting_period_status"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AccountingPeriod id={self.id} name={self.name} "
            f"status={self.status}>"
        )


class JournalEntry(Base):
    """The posting header.  A balanced set of debit/credit lines."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Human-friendly sequential reference, assigned after insert
    #: (``JE-{campus}-{id:06d}``) in the same transaction.
    entry_number: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    period_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounting_periods.id"), nullable=True, index=True
    )
    entry_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ENTRY_DRAFT, index=True
    )
    #: Re-computed from the lines at post time; the DB CHECK below is the
    #: final backstop for the SUM(debits) == SUM(credits) invariant.
    total_debits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Provenance: closed vocabulary (see ``SOURCE_TYPES``) + optional id.
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    #: Idempotency key — unique per campus; a retried posting resolves to
    #: the original entry instead of double-booking.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Reversal linkage.  ``reversal_of_id`` — the entry this entry
    #: reverses; ``reversed_entry_id`` — the entry that reversed this one.
    reversal_of_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    reversed_entry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "campus_id", "idempotency_key", name="uq_journal_entry_idempotency"
        ),
        CheckConstraint(
            "status IN ('draft','posted','reversed')",
            name="ck_journal_entry_status",
        ),
        # The core invariant, enforced at the DB layer: any non-draft
        # entry MUST be balanced.  Drafts may be mid-edit and unbalanced;
        # the moment an entry is posted (or reversed) it must balance.
        CheckConstraint(
            "status = 'draft' OR total_debits = total_credits",
            name="ck_journal_entry_balanced",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<JournalEntry id={self.id} number={self.entry_number} "
            f"status={self.status} debits={self.total_debits} "
            f"credits={self.total_credits}>"
        )


class JournalLine(Base):
    """A single debit or credit leg of a journal entry."""

    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ledger_accounts.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    #: Amount in minor currency units (paise for INR) — never a float.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Generic line-level reference (e.g. ref_type="payment", ref_id="42").
    ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")

    __table_args__ = (
        Index("ix_journal_lines_account_id", "account_id"),
        Index("ix_journal_lines_ref", "ref_type", "ref_id"),
        CheckConstraint(
            "direction IN ('debit','credit')", name="ck_journal_line_direction"
        ),
        CheckConstraint("amount > 0", name="ck_journal_line_amount_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<JournalLine id={self.id} entry={self.entry_id} "
            f"account={self.account_id} {self.direction} {self.amount}>"
        )
