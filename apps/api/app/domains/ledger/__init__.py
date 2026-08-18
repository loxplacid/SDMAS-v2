"""Double-entry ledger (TASK 16).

A proper double-entry ledger beside the existing single-entry
``transaction_logs`` running balance: chart of accounts, accounting
periods (with lock/finalization), balanced journal entries, source
references, reversals, trial balance and independent verification.

The core invariant — ``SUM(debits) == SUM(credits)`` for every posted
entry — is enforced in the posting transaction and backstopped by a
database CHECK constraint on ``journal_entries``.  No financial balance
is ever mutated directly; journal entries ARE the posting mechanism.
"""

from app.domains.ledger.models import (
    ACCOUNT_ASSET,
    ACCOUNT_EQUITY,
    ACCOUNT_EXPENSE,
    ACCOUNT_LIABILITY,
    ACCOUNT_REVENUE,
    ACCOUNT_TYPES,
    ENTRY_DRAFT,
    ENTRY_POSTED,
    ENTRY_REVERSED,
    ENTRY_STATUSES,
    LINE_CREDIT,
    LINE_DEBIT,
    LINE_DIRECTIONS,
    NORMAL_SIDE_CREDIT,
    NORMAL_SIDE_DEBIT,
    PERIOD_CLOSED,
    PERIOD_OPEN,
    PERIOD_STATUSES,
    SOURCE_INVOICE,
    SOURCE_MANUAL,
    SOURCE_PAYMENT,
    SOURCE_REFUND,
    SOURCE_REVERSAL,
    SOURCE_TRANSACTION_LOG,
    SOURCE_TYPES,
    AccountingPeriod,
    JournalEntry,
    JournalLine,
    LedgerAccount,
)
from app.domains.ledger.repository import LedgerRepository
from app.domains.ledger.service import DEFAULT_CHART, LedgerService

__all__ = [
    "ACCOUNT_ASSET",
    "ACCOUNT_EQUITY",
    "ACCOUNT_EXPENSE",
    "ACCOUNT_LIABILITY",
    "ACCOUNT_REVENUE",
    "ACCOUNT_TYPES",
    "ENTRY_DRAFT",
    "ENTRY_POSTED",
    "ENTRY_REVERSED",
    "ENTRY_STATUSES",
    "LINE_CREDIT",
    "LINE_DEBIT",
    "LINE_DIRECTIONS",
    "NORMAL_SIDE_CREDIT",
    "NORMAL_SIDE_DEBIT",
    "PERIOD_CLOSED",
    "PERIOD_OPEN",
    "PERIOD_STATUSES",
    "SOURCE_INVOICE",
    "SOURCE_MANUAL",
    "SOURCE_PAYMENT",
    "SOURCE_REFUND",
    "SOURCE_REVERSAL",
    "SOURCE_TRANSACTION_LOG",
    "SOURCE_TYPES",
    "AccountingPeriod",
    "JournalEntry",
    "JournalLine",
    "LedgerAccount",
    "LedgerRepository",
    "LedgerService",
    "DEFAULT_CHART",
]
