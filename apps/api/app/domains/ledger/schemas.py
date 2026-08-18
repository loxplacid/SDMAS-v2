"""Double-entry ledger — Pydantic schemas (TASK 16).

All monetary amounts are integers in **minor currency units** (paise for
INR) — the same convention as ``payments`` / ``transaction_logs``, so
the ledger can never introduce float rounding into the books.
"""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.pagination import Page
from app.domains.ledger.models import (
    ACCOUNT_TYPES,
    LINE_DIRECTIONS,
    SOURCE_TYPES,
)


# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    account_type: str
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("account_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in ACCOUNT_TYPES:
            raise ValueError(
                f"account_type must be one of {sorted(ACCOUNT_TYPES)}, got {v!r}"
            )
        return v

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code must not be empty")
        return v


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    code: str
    name: str
    account_type: str
    normal_side: str
    description: Optional[str] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


AccountPage = Page[AccountResponse]


# ---------------------------------------------------------------------------
# Accounting periods
# ---------------------------------------------------------------------------


class PeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: datetime.date
    end_date: datetime.date

    @field_validator("end_date")
    @classmethod
    def _end_not_before_start(cls, v: datetime.date, info) -> datetime.date:
        start = info.data.get("start_date")
        if start is not None and v < start:
            raise ValueError("end_date must not be before start_date")
        return v


class PeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    name: str
    start_date: datetime.date
    end_date: datetime.date
    status: str
    closed_by: Optional[int] = None
    closed_at: Optional[datetime.datetime] = None
    created_by: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


PeriodPage = Page[PeriodResponse]


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------


class JournalLineIn(BaseModel):
    account_id: int
    direction: str
    amount: int = Field(gt=0)
    ref_type: Optional[str] = Field(default=None, max_length=50)
    ref_id: Optional[str] = Field(default=None, max_length=100)
    memo: Optional[str] = Field(default=None, max_length=500)

    @field_validator("direction")
    @classmethod
    def _valid_direction(cls, v: str) -> str:
        if v not in LINE_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {sorted(LINE_DIRECTIONS)}, got {v!r}"
            )
        return v


class JournalEntryCreate(BaseModel):
    period_id: int
    entry_date: datetime.date
    description: str = Field(min_length=1, max_length=2000)
    source_type: Optional[str] = Field(default=None, max_length=50)
    source_id: Optional[str] = Field(default=None, max_length=100)
    idempotency_key: Optional[str] = Field(default=None, max_length=255)
    lines: list[JournalLineIn] = Field(min_length=2)

    @field_validator("source_type")
    @classmethod
    def _valid_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in SOURCE_TYPES:
            raise ValueError(
                f"source_type must be one of {sorted(SOURCE_TYPES)}, got {v!r}"
            )
        return v


class JournalLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_id: int
    account_id: int
    direction: str
    amount: int
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    memo: Optional[str] = None
    created_at: datetime.datetime


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    entry_number: Optional[str] = None
    period_id: Optional[int] = None
    entry_date: datetime.date
    description: str
    status: str
    total_debits: int
    total_credits: int
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    posted_by: Optional[int] = None
    posted_at: Optional[datetime.datetime] = None
    reversal_of_id: Optional[int] = None
    reversed_entry_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    lines: list[JournalLineResponse] = []


JournalEntryPage = Page[JournalEntryResponse]


class ReversalCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    entry_date: Optional[datetime.date] = None
    period_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Reporting / verification
# ---------------------------------------------------------------------------


class TrialBalanceRow(BaseModel):
    account_id: int
    code: str
    name: str
    account_type: str
    normal_side: str
    debits: int
    credits: int
    #: Net = debits − credits; positive = net debit, negative = net credit.
    net: int


class TrialBalanceResponse(BaseModel):
    rows: list[TrialBalanceRow]
    total_debits: int
    total_credits: int
    #: The core invariant: SUM(debits) == SUM(credits) over posted entries.
    balanced: bool


class EntryVerification(BaseModel):
    entry_id: int
    entry_number: Optional[str] = None
    status: str
    stored_debits: int
    stored_credits: int
    computed_debits: int
    computed_credits: int
    balanced: bool
    lines_ok: bool
