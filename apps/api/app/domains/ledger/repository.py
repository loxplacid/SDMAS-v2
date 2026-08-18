"""Double-entry ledger — tenant-scoped repository.

Every query goes through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can
never read or mutate a ledger account, accounting period, journal entry
or journal line belonging to campus B.
"""

from __future__ import annotations

import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.domains.ledger.models import (
    AccountingPeriod,
    JournalEntry,
    JournalLine,
    LedgerAccount,
)


class LedgerRepository(TenantScopedRepository):
    """Tenant-scoped data access for the double-entry ledger."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # Chart of accounts
    # ------------------------------------------------------------------

    async def create_account(self, account: LedgerAccount) -> LedgerAccount:
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_account(self, account_id: int) -> Optional[LedgerAccount]:
        return await self.get_by_id(LedgerAccount, account_id)

    async def get_account_or_404(self, account_id: int) -> LedgerAccount:
        return await self.get_by_id_or_404(
            LedgerAccount, account_id, resource="ledger account"
        )

    async def find_account_by_code(
        self, code: str, campus_id: Optional[int] = None
    ) -> Optional[LedgerAccount]:
        query = self.scoped_query(LedgerAccount).where(LedgerAccount.code == code)
        if campus_id is not None:
            query = query.where(LedgerAccount.campus_id == campus_id)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_accounts(
        self,
        *,
        account_type: Optional[str] = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[LedgerAccount], int]:
        extra: list = []
        if account_type:
            extra.append(LedgerAccount.account_type == account_type)
        if active_only:
            extra.append(LedgerAccount.is_active.is_(True))
        return await self._list_by_tenant(
            LedgerAccount,
            order_by_attr="code",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    # ------------------------------------------------------------------
    # Accounting periods
    # ------------------------------------------------------------------

    async def create_period(self, period: AccountingPeriod) -> AccountingPeriod:
        self.session.add(period)
        await self.session.flush()
        return period

    async def get_period(self, period_id: int) -> Optional[AccountingPeriod]:
        return await self.get_by_id(AccountingPeriod, period_id)

    async def get_period_or_404(self, period_id: int) -> AccountingPeriod:
        return await self.get_by_id_or_404(
            AccountingPeriod, period_id, resource="accounting period"
        )

    async def find_period_by_name(
        self, name: str, campus_id: Optional[int] = None
    ) -> Optional[AccountingPeriod]:
        query = self.scoped_query(AccountingPeriod).where(
            AccountingPeriod.name == name
        )
        if campus_id is not None:
            query = query.where(AccountingPeriod.campus_id == campus_id)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def find_overlapping_period(
        self, start: datetime.date, end: datetime.date, campus_id: Optional[int] = None
    ) -> Optional[AccountingPeriod]:
        """Find any period whose date range overlaps ``[start, end]``."""
        query = self.scoped_query(AccountingPeriod).where(
            AccountingPeriod.start_date <= end,
            AccountingPeriod.end_date >= start,
        )
        if campus_id is not None:
            query = query.where(AccountingPeriod.campus_id == campus_id)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def get_open_period_for_date(
        self, entry_date: datetime.date, campus_id: Optional[int] = None
    ) -> Optional[AccountingPeriod]:
        """The open period covering ``entry_date`` (if any)."""
        query = self.scoped_query(AccountingPeriod).where(
            AccountingPeriod.status == "open",
            AccountingPeriod.start_date <= entry_date,
            AccountingPeriod.end_date >= entry_date,
        )
        if campus_id is not None:
            query = query.where(AccountingPeriod.campus_id == campus_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_periods(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AccountingPeriod], int]:
        extra = [AccountingPeriod.status == status] if status else None
        return await self._list_by_tenant(
            AccountingPeriod,
            order_by_attr="start_date",
            descending=True,
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    # ------------------------------------------------------------------
    # Journal entries / lines
    # ------------------------------------------------------------------

    async def create_entry(self, entry: JournalEntry) -> JournalEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def create_line(self, line: JournalLine) -> JournalLine:
        self.session.add(line)
        await self.session.flush()
        return line

    async def get_entry(self, entry_id: int) -> Optional[JournalEntry]:
        """Fetch one entry with its lines eager-loaded, tenant-scoped."""
        self.require_tenant_scope(JournalEntry)
        query = (
            self.scoped_query(JournalEntry)
            .where(JournalEntry.id == entry_id)
            .options(selectinload(JournalEntry.lines))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_entry_or_404(self, entry_id: int) -> JournalEntry:
        entry = await self.get_entry(entry_id)
        if entry is None:
            raise NotFoundError(f"journal entry with id {entry_id} not found")
        return entry

    async def find_entry_by_idempotency_key(
        self, key: str, campus_id: Optional[int] = None
    ) -> Optional[JournalEntry]:
        """Find a prior journal entry by idempotency key (campus-scoped)."""
        query = self.scoped_query(JournalEntry).where(
            JournalEntry.idempotency_key == key
        )
        if campus_id is not None:
            query = query.where(JournalEntry.campus_id == campus_id)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def get_lines_for_entry(self, entry_id: int) -> list[JournalLine]:
        """All lines of an entry, scoped to the tenant via the entry."""
        await self.get_entry_or_404(entry_id)  # raises 403 cross-tenant / 404
        result = await self.session.execute(
            select(JournalLine).where(JournalLine.entry_id == entry_id)
        )
        return list(result.scalars().all())

    async def sum_lines(self, entry_id: int) -> tuple[int, int]:
        """(total_debits, total_credits) for an entry's lines."""
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(JournalLine.amount).filter(JournalLine.direction == "debit"),
                    0,
                ),
                func.coalesce(
                    func.sum(JournalLine.amount).filter(JournalLine.direction == "credit"),
                    0,
                ),
            ).where(JournalLine.entry_id == entry_id)
        )
        row = result.one()
        return int(row[0] or 0), int(row[1] or 0)

    async def list_entries(
        self,
        *,
        period_id: Optional[int] = None,
        account_id: Optional[int] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        from_date: Optional[datetime.date] = None,
        to_date: Optional[datetime.date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[JournalEntry], int]:
        extra: list = []
        if period_id is not None:
            extra.append(JournalEntry.period_id == period_id)
        if status:
            extra.append(JournalEntry.status == status)
        if source_type:
            extra.append(JournalEntry.source_type == source_type)
        if source_id:
            extra.append(JournalEntry.source_id == source_id)
        if from_date is not None:
            extra.append(JournalEntry.entry_date >= from_date)
        if to_date is not None:
            extra.append(JournalEntry.entry_date <= to_date)
        if account_id is not None:
            # Join through the lines: entries touching the account.
            query = self.scoped_query(JournalEntry).join(
                JournalLine, JournalLine.entry_id == JournalEntry.id
            )
            query = query.where(JournalLine.account_id == account_id)
            total_q = self.scoped_count(JournalEntry).join(
                JournalLine, JournalLine.entry_id == JournalEntry.id
            )
            total_q = total_q.where(JournalLine.account_id == account_id)
            for cond in extra:
                query = query.where(cond)
                total_q = total_q.where(cond)
            total = int((await self.session.execute(total_q)).scalar_one() or 0)
            result = await self.session.execute(
                query.distinct()
                .options(selectinload(JournalEntry.lines))
                .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all()), total

        count_q = self.scoped_count(JournalEntry)
        for cond in extra:
            count_q = count_q.where(cond)
        total = int((await self.session.execute(count_q)).scalar_one() or 0)

        q = self.scoped_query(JournalEntry)
        for cond in extra:
            q = q.where(cond)
        result = await self.session.execute(
            q.options(selectinload(JournalEntry.lines))
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def trial_balance_rows(
        self,
        campus_id: Optional[int] = None,
        period_id: Optional[int] = None,
        as_of: Optional[datetime.date] = None,
    ) -> list[tuple[LedgerAccount, int, int]]:
        """Aggregate posted lines per account: ``(account, debits, credits)``.

        Only lines of **posted / reversed** entries count (drafts are
        never part of the books).  The caller's tenant scope is applied
        through the account (and hence the campus) join.
        """
        line_q = (
            select(
                LedgerAccount,
                func.coalesce(
                    func.sum(JournalLine.amount).filter(JournalLine.direction == "debit"),
                    0,
                ),
                func.coalesce(
                    func.sum(JournalLine.amount).filter(JournalLine.direction == "credit"),
                    0,
                ),
            )
            .join(JournalLine, JournalLine.account_id == LedgerAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalEntry.status.in_(("posted", "reversed")))
        )
        if campus_id is not None:
            line_q = line_q.where(LedgerAccount.campus_id == campus_id)
        if period_id is not None:
            line_q = line_q.where(JournalEntry.period_id == period_id)
        if as_of is not None:
            line_q = line_q.where(JournalEntry.entry_date <= as_of)
        line_q = line_q.group_by(LedgerAccount.id).order_by(LedgerAccount.code)
        result = await self.session.execute(line_q)
        return [
            (account, int(debits or 0), int(credits or 0))
            for account, debits, credits in result.all()
        ]

    async def count_account_entries(self, account_id: int) -> int:
        """Number of posted/reversed lines referencing an account.

        Used to block deactivating an account that is already part of
        the posted books.
        """
        result = await self.session.execute(
            select(func.count(JournalLine.id))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                JournalLine.account_id == account_id,
                JournalEntry.status.in_(("posted", "reversed")),
            )
        )
        return int(result.scalar_one() or 0)