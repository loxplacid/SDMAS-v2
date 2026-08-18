"""Double-entry ledger — application service (TASK 16).

The ledger is a new domain beside the existing single-entry
``transaction_logs`` running balance.  Nothing here mutates the existing
fee workflows: payments continue to record through
``TransactionLogService`` exactly as before.  This service provides the
double-entry capability, the accounting-period lock, and a documented
bridge (``post_fee_payment``) that the fee domain can adopt gradually.

**Core invariant** — for every posted (or reversed) entry::

    SUM(debits) == SUM(credits)

Enforced here *in the same transaction* that flips the status, and
backstopped at the database layer by ``ck_journal_entry_balanced`` on
``journal_entries`` (non-draft entries must have equal stored totals).

**Balance mutation rule** — no financial balance is ever mutated
directly.  The only way into the books is a posted journal entry
(service) or a direct SQL write, which the DB constraints and the
verification endpoints make detectable.  ``verify_entry`` re-computes
each entry's sums from its lines; ``trial_balance`` re-aggregates the
whole campus and reports whether the books balance.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.domains.ledger.models import (
    ENTRY_DRAFT,
    ENTRY_POSTED,
    ENTRY_REVERSED,
    LINE_CREDIT,
    LINE_DEBIT,
    PERIOD_CLOSED,
    PERIOD_OPEN,
    SOURCE_MANUAL,
    SOURCE_PAYMENT,
    SOURCE_REVERSAL,
    TYPE_NORMAL_SIDE,
    AccountingPeriod,
    JournalEntry,
    JournalLine,
    LedgerAccount,
)
from app.domains.ledger.repository import LedgerRepository
from app.domains.ledger.schemas import (
    AccountCreate,
    AccountUpdate,
    JournalEntryCreate,
    PeriodCreate,
    TrialBalanceResponse,
    TrialBalanceRow,
)
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


def _actor_id(actor: AuditActor | None) -> Optional[int]:
    if actor is None or actor.actor_type != ActorType.USER:
        return None
    raw = actor.actor_id
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _actor_name(actor: AuditActor | None) -> Optional[str]:
    return actor.actor_name if actor is not None else None


#: The default chart seeded per campus (idempotent) — a minimal,
#: self-consistent chart covering the fee-payment bridge.
DEFAULT_CHART: list[tuple[str, str, str, str]] = [
    # (code, name, type, description)
    ("1000", "Cash & Bank", "asset", "Cash on hand and bank balances"),
    ("1200", "Fee Receivables", "asset", "Outstanding fee dues receivable from students"),
    ("2100", "Refunds Payable", "liability", "Refunds owed to students/parents"),
    ("3100", "Retained Earnings", "equity", "Accumulated retained earnings"),
    ("4000", "Fee Revenue", "revenue", "Tuition and fee revenue earned"),
    ("5100", "Operating Expense", "expense", "General operating expenses"),
]


class LedgerService:
    """Double-entry ledger operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = LedgerRepository(session, tenant)
        self.audit = AuditService(session, tenant)

    # ==================================================================
    # Chart of accounts
    # ==================================================================

    async def create_account(
        self, data: AccountCreate, actor: AuditActor | None = None
    ) -> LedgerAccount:
        campus_id = self.repo._effective_campus_id()
        existing = await self.repo.find_account_by_code(data.code, campus_id=campus_id)
        if existing is not None:
            raise ConflictError(
                f"An account with code {data.code!r} already exists for this campus."
            )
        account = LedgerAccount(
            campus_id=campus_id,
            code=data.code,
            name=data.name,
            account_type=data.account_type,
            description=data.description,
            is_active=data.is_active,
            created_by=_actor_id(actor),
        )
        account = await self.repo.create_account(account)
        await self.audit.record(
            action="CREATE",
            resource_type="ledger_account",
            resource_id=str(account.id),
            actor=actor,
            details={"code": account.code, "name": account.name,
                     "account_type": account.account_type},
        )
        return account

    async def update_account(
        self, account_id: int, data: AccountUpdate, actor: AuditActor | None = None
    ) -> LedgerAccount:
        account = await self.repo.get_account_or_404(account_id)
        changed: dict[str, Any] = {}
        if data.name is not None and data.name != account.name:
            account.name = data.name
            changed["name"] = data.name
        if data.description is not None and data.description != account.description:
            account.description = data.description
            changed["description"] = data.description
        if data.is_active is not None and data.is_active != account.is_active:
            if data.is_active is False:
                used = await self.repo.count_account_entries(account.id)
                if used > 0:
                    raise ConflictError(
                        "Account is referenced by posted journal lines and cannot "
                        "be deactivated."
                    )
            account.is_active = data.is_active
            changed["is_active"] = data.is_active
        await self.session.flush()
        if changed:
            await self.audit.record(
                action="UPDATE",
                resource_type="ledger_account",
                resource_id=str(account.id),
                actor=actor,
                details=changed,
            )
        return account

    async def get_account(self, account_id: int) -> LedgerAccount:
        return await self.repo.get_account_or_404(account_id)

    async def list_accounts(
        self,
        *,
        account_type: Optional[str] = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[LedgerAccount], int]:
        return await self.repo.list_accounts(
            account_type=account_type, active_only=active_only,
            skip=skip, limit=limit,
        )

    async def seed_default_chart(
        self, actor: AuditActor | None = None
    ) -> list[LedgerAccount]:
        """Idempotently create the default chart for this campus.

        Accounts that already exist (by code) are left untouched, so the
        operation is safe to run repeatedly.
        """
        campus_id = self.repo._effective_campus_id()
        created: list[LedgerAccount] = []
        for code, name, account_type, description in DEFAULT_CHART:
            existing = await self.repo.find_account_by_code(code, campus_id=campus_id)
            if existing is not None:
                continue
            account = LedgerAccount(
                campus_id=campus_id,
                code=code,
                name=name,
                account_type=account_type,
                description=description,
                is_active=True,
                created_by=_actor_id(actor),
            )
            created.append(await self.repo.create_account(account))
        if created:
            await self.audit.record(
                action="SEED",
                resource_type="ledger_chart",
                resource_id=str(campus_id or 0),
                actor=actor,
                details={"accounts_created": [a.code for a in created]},
            )
        return created

    # ==================================================================
    # Accounting periods
    # ==================================================================

    async def create_period(
        self, data: PeriodCreate, actor: AuditActor | None = None
    ) -> AccountingPeriod:
        campus_id = self.repo._effective_campus_id()
        existing = await self.repo.find_period_by_name(data.name, campus_id=campus_id)
        if existing is not None:
            raise ConflictError(
                f"An accounting period named {data.name!r} already exists for "
                "this campus."
            )
        overlap = await self.repo.find_overlapping_period(
            data.start_date, data.end_date, campus_id=campus_id
        )
        if overlap is not None:
            raise ConflictError(
                "Period overlaps existing period "
                f"{overlap.name!r} ({overlap.start_date}..{overlap.end_date}); "
                "accounting periods for a campus must not overlap."
            )
        period = AccountingPeriod(
            campus_id=campus_id,
            name=data.name,
            start_date=data.start_date,
            end_date=data.end_date,
            status=PERIOD_OPEN,
            created_by=_actor_id(actor),
        )
        period = await self.repo.create_period(period)
        await self.audit.record(
            action="CREATE",
            resource_type="accounting_period",
            resource_id=str(period.id),
            actor=actor,
            details={"name": period.name, "start_date": str(period.start_date),
                     "end_date": str(period.end_date)},
        )
        return period

    async def close_period(
        self, period_id: int, actor: AuditActor | None = None
    ) -> AccountingPeriod:
        """Lock/finalize a period: no further postings dated inside it.

        Closing is final within this service (no reopen) — reopening a
        locked period would silently invalidate the audit trail of every
        entry posted after the lock, so it is deliberately not offered.
        """
        period = await self.repo.get_period_or_404(period_id)
        if period.status == PERIOD_CLOSED:
            raise ConflictError(f"Accounting period {period.name!r} is already closed.")
        period.status = PERIOD_CLOSED
        period.closed_by = _actor_id(actor)
        period.closed_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.flush()
        await self.audit.record(
            action="CLOSE_PERIOD",
            resource_type="accounting_period",
            resource_id=str(period.id),
            actor=actor,
            details={"name": period.name, "start_date": str(period.start_date),
                     "end_date": str(period.end_date)},
        )
        return period

    async def get_period(self, period_id: int) -> AccountingPeriod:
        return await self.repo.get_period_or_404(period_id)

    async def list_periods(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AccountingPeriod], int]:
        return await self.repo.list_periods(
            status=status, skip=skip, limit=limit
        )

    # ==================================================================
    # Journal entries
    # ==================================================================

    async def create_entry(
        self, data: JournalEntryCreate, actor: AuditActor | None = None
    ) -> JournalEntry:
        """Create a DRAFT journal entry (unbalanced drafts are allowed)."""
        await self._validate_entry_data(data, require_balance=False)
        entry = JournalEntry(
            campus_id=self.repo._effective_campus_id(),
            period_id=data.period_id,
            entry_date=data.entry_date,
            description=data.description,
            status=ENTRY_DRAFT,
            source_type=data.source_type or SOURCE_MANUAL,
            source_id=data.source_id,
            idempotency_key=data.idempotency_key,
            created_by=_actor_id(actor),
        )
        entry = await self.repo.create_entry(entry)
        created_lines: list[JournalLine] = []
        for line in data.lines:
            created_lines.append(
                await self.repo.create_line(
                    JournalLine(
                        entry_id=entry.id,
                        account_id=line.account_id,
                        direction=line.direction,
                        amount=line.amount,
                        ref_type=line.ref_type,
                        ref_id=line.ref_id,
                        memo=line.memo,
                    )
                )
            )
        entry.lines = created_lines  # in-memory collection for serialization
        # Totals are computed from the lines and stored on the header so
        # the DB-level balance CHECK has something authoritative to test.
        entry.total_debits, entry.total_credits = await self.repo.sum_lines(entry.id)
        self._assign_entry_number(entry)
        await self.session.flush()
        await self.audit.record(
            action="CREATE",
            resource_type="journal_entry",
            resource_id=str(entry.id),
            actor=actor,
            details={
                "entry_date": str(entry.entry_date),
                "period_id": entry.period_id,
                "debits": entry.total_debits,
                "credits": entry.total_credits,
            },
        )
        return entry

    async def create_and_post(
        self, data: JournalEntryCreate, actor: AuditActor | None = None
    ) -> JournalEntry:
        """Create a balanced entry and post it in one operation.

        Idempotent: a repeated call with the same ``idempotency_key``
        resolves to the original posted entry instead of double-booking.
        """
        if data.idempotency_key:
            existing = await self.repo.find_entry_by_idempotency_key(
                data.idempotency_key,
                campus_id=self.repo._effective_campus_id(),
            )
            if existing is not None:
                return existing
        entry = await self.create_entry(data, actor=actor)
        return await self.post_entry(entry.id, actor=actor)

    async def post_entry(
        self, entry_id: int, actor: AuditActor | None = None
    ) -> JournalEntry:
        """Post a draft entry.

        Validates, in the same transaction that flips the status:

        * the entry is a draft (posting is one-shot),
        * the lines contain at least one debit and one credit,
        * SUM(debits) == SUM(credits) — the core invariant,
        * the accounting period exists, is open (not locked), and covers
          the entry date,
        * every referenced account is active.

        No financial balance is ever touched directly — the journal entry
        IS the posting.
        """
        entry = await self.repo.get_entry_or_404(entry_id)
        if entry.status != ENTRY_DRAFT:
            raise ConflictError(
                f"Entry {entry.entry_number or entry.id} is already "
                f"{entry.status}; only draft entries can be posted."
            )
        debits, credits = await self.repo.sum_lines(entry.id)
        if debits <= 0 or credits <= 0:
            raise ValidationError(
                "A journal entry must contain at least one debit and one credit line."
            )
        if debits != credits:
            raise ValidationError(
                f"Unbalanced journal entry: debits {debits} != credits {credits}. "
                "SUM(debits) must equal SUM(credits) before posting."
            )
        await self._assert_period_open(entry)
        await self._assert_accounts_active(entry.id)

        entry.status = ENTRY_POSTED
        entry.total_debits = debits
        entry.total_credits = credits
        entry.posted_by = _actor_id(actor)
        entry.posted_at = datetime.datetime.now(datetime.timezone.utc)
        await self.session.flush()
        await self.audit.record(
            action="POST",
            resource_type="journal_entry",
            resource_id=str(entry.id),
            actor=actor,
            details={
                "entry_number": entry.entry_number,
                "debits": entry.total_debits,
                "credits": entry.total_credits,
                "period_id": entry.period_id,
            },
        )
        return entry

    async def reverse_entry(
        self,
        entry_id: int,
        reason: str,
        actor: AuditActor | None = None,
        entry_date: Optional[datetime.date] = None,
        period_id: Optional[int] = None,
    ) -> JournalEntry:
        """Reverse a posted entry by posting an exact mirror (debits ↔
        credits) and marking the original ``reversed``.

        A posted entry can be reversed at most once; drafts cannot be
        reversed (they are simply discarded or edited).  The mirror is
        posted in the same transaction, so the books stay balanced at
        every instant.
        """
        original = await self.repo.get_entry_or_404(entry_id)
        if original.status == ENTRY_DRAFT:
            raise ConflictError("Draft entries cannot be reversed; edit or discard them.")
        if original.reversed_entry_id is not None:
            raise ConflictError(
                f"Entry {original.entry_number or original.id} has already been "
                "reversed."
            )
        # Accounting default: a reversal carries the original entry's date
        # (it reverses that posting), not "today" — today may fall outside
        # the original period, which would needlessly force a caller to
        # pass a date that the books don't care about.
        date = entry_date or original.entry_date
        if period_id is not None:
            period = await self.repo.get_period_or_404(period_id)
            await self._assert_period_open_for(period, date)
        elif original.period_id is not None:
            period = await self.repo.get_period_or_404(original.period_id)
            if period.status == PERIOD_CLOSED:
                raise ValidationError(
                    "The original entry's accounting period is closed. Pass an "
                    "open period_id (and matching entry_date) for the reversal."
                )
            if not (period.start_date <= date <= period.end_date):
                raise ValidationError(
                    "The reversal date falls outside the original entry's period; "
                    "pass an open period_id covering the reversal date."
                )
        else:
            raise ValidationError("Reversal requires an accounting period.")

        lines = await self.repo.get_lines_for_entry(original.id)
        if not lines:
            raise ValidationError("Original entry has no lines; cannot reverse.")

        mirror = JournalEntry(
            campus_id=original.campus_id,
            period_id=period.id,
            entry_date=date,
            description=f"Reversal of {original.entry_number or original.id} — {reason}",
            status=ENTRY_POSTED,
            source_type=SOURCE_REVERSAL,
            source_id=str(original.id),
            reversal_of_id=original.id,
            posted_by=_actor_id(actor),
            posted_at=datetime.datetime.now(datetime.timezone.utc),
            created_by=_actor_id(actor),
        )
        mirror = await self.repo.create_entry(mirror)
        mirror_debits = 0
        mirror_credits = 0
        mirror_lines: list[JournalLine] = []
        for line in lines:
            if line.direction == LINE_DEBIT:
                direction = LINE_CREDIT
                mirror_credits += line.amount
            else:
                direction = LINE_DEBIT
                mirror_debits += line.amount
            mirror_lines.append(
                await self.repo.create_line(
                    JournalLine(
                        entry_id=mirror.id,
                        account_id=line.account_id,
                        direction=direction,
                        amount=line.amount,
                        ref_type=line.ref_type,
                        ref_id=line.ref_id,
                        memo=f"Reversal of line {line.id}: {reason}",
                    )
                )
            )
        mirror.lines = mirror_lines  # in-memory collection for serialization
        mirror.total_debits = mirror_debits
        mirror.total_credits = mirror_credits
        self._assign_entry_number(mirror)

        original.reversed_entry_id = mirror.id
        original.status = ENTRY_REVERSED
        await self.session.flush()

        await self.audit.record(
            action="REVERSE",
            resource_type="journal_entry",
            resource_id=str(original.id),
            actor=actor,
            details={
                "reversal_entry_id": mirror.id,
                "reversal_number": mirror.entry_number,
                "reason": reason,
                "amount": mirror.total_debits,
            },
        )
        return mirror

    # ------------------------------------------------------------------
    # Reads / reporting
    # ------------------------------------------------------------------

    async def get_entry(self, entry_id: int) -> JournalEntry:
        return await self.repo.get_entry_or_404(entry_id)

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
        return await self.repo.list_entries(
            period_id=period_id,
            account_id=account_id,
            status=status,
            source_type=source_type,
            source_id=source_id,
            from_date=from_date,
            to_date=to_date,
            skip=skip,
            limit=limit,
        )

    async def verify_entry(self, entry_id: int) -> dict[str, Any]:
        """Re-compute an entry's sums from its lines and compare against
        the stored totals — a tamper check independent of the writer."""
        entry = await self.repo.get_entry_or_404(entry_id)
        lines = await self.repo.get_lines_for_entry(entry.id)
        debits = sum(l.amount for l in lines if l.direction == LINE_DEBIT)
        credits = sum(l.amount for l in lines if l.direction == LINE_CREDIT)
        ok_directions = all(l.direction in (LINE_DEBIT, LINE_CREDIT) for l in lines)
        # The live truth of the invariant, independent of stored totals:
        # compare with ``stored_debits``/``stored_credits`` to detect
        # any out-of-band mutation of the header.
        balanced = debits == credits
        return {
            "entry_id": entry.id,
            "entry_number": entry.entry_number,
            "status": entry.status,
            "stored_debits": entry.total_debits,
            "stored_credits": entry.total_credits,
            "computed_debits": debits,
            "computed_credits": credits,
            "balanced": balanced,
            "lines_ok": ok_directions and len(lines) >= 2,
        }

    async def trial_balance(
        self,
        *,
        period_id: Optional[int] = None,
        as_of: Optional[datetime.date] = None,
    ) -> TrialBalanceResponse:
        """Aggregate posted (and reversed) lines per account.

        Reports the per-account debit/credit totals and the global
        balance check — ``balanced`` is the live truth of whether
        SUM(debits) == SUM(credits) across every posted entry.
        """
        rows_raw = await self.repo.trial_balance_rows(
            campus_id=self.repo._effective_campus_id(),
            period_id=period_id,
            as_of=as_of,
        )
        rows: list[TrialBalanceRow] = []
        for account, debits, credits in rows_raw:
            rows.append(
                TrialBalanceRow(
                    account_id=account.id,
                    code=account.code,
                    name=account.name,
                    account_type=account.account_type,
                    normal_side=TYPE_NORMAL_SIDE[account.account_type],
                    debits=debits,
                    credits=credits,
                    net=debits - credits,
                )
            )
        total_debits = sum(r.debits for r in rows)
        total_credits = sum(r.credits for r in rows)
        return TrialBalanceResponse(
            rows=rows,
            total_debits=total_debits,
            total_credits=total_credits,
            balanced=total_debits == total_credits,
        )

    # ==================================================================
    # Integration bridge (gradual, non-breaking)
    # ==================================================================

    async def post_fee_payment(
        self,
        *,
        campus_id: int,
        payment_id: int,
        amount: int,
        period_id: int,
        entry_date: Optional[datetime.date] = None,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        actor: AuditActor | None = None,
    ) -> JournalEntry:
        """Journal a recorded fee payment as a double-entry posting.

        Standard treatment for a payment that settles a fee receivable::

            Dr  Cash & Bank            amount
                Cr  Fee Receivables            amount

        Uses the default chart seeded by :meth:`seed_default_chart`
        (codes ``1000`` / ``1200``).  This is the *integration bridge*:
        the fee domain keeps recording payments exactly as today; when a
        campus opts into the ledger, this method is called alongside
        (or instead of) the running-balance log within the same
        transaction.  Requires an existing open accounting period.
        """
        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")
        period = await self.repo.get_period_or_404(period_id)
        await self._assert_period_open_for(period, entry_date or datetime.date.today())
        cash = await self.repo.find_account_by_code("1000", campus_id=campus_id)
        receivable = await self.repo.find_account_by_code("1200", campus_id=campus_id)
        if cash is None or receivable is None:
            raise ValidationError(
                "Ledger chart not seeded for this campus — call "
                "seed_default_chart first (accounts 1000 and 1200 are required)."
            )
        data = JournalEntryCreate(
            period_id=period.id,
            entry_date=entry_date or datetime.date.today(),
            description=description or f"Fee payment {payment_id}",
            source_type=SOURCE_PAYMENT,
            source_id=str(payment_id),
            idempotency_key=idempotency_key,
            lines=[
                {
                    "account_id": cash.id,
                    "direction": LINE_DEBIT,
                    "amount": amount,
                    "ref_type": "payment",
                    "ref_id": str(payment_id),
                },
                {
                    "account_id": receivable.id,
                    "direction": LINE_CREDIT,
                    "amount": amount,
                    "ref_type": "payment",
                    "ref_id": str(payment_id),
                },
            ],
        )
        return await self.create_and_post(data, actor=actor)

    # ==================================================================
    # Internal helpers
    # ==================================================================

    async def _validate_entry_data(
        self, data: JournalEntryCreate, *, require_balance: bool
    ) -> None:
        period = await self.repo.get_period_or_404(data.period_id)
        if not (period.start_date <= data.entry_date <= period.end_date):
            raise ValidationError(
                f"entry_date {data.entry_date} is outside accounting period "
                f"{period.name!r} ({period.start_date}..{period.end_date})."
            )
        if data.idempotency_key and not data.idempotency_key.strip():
            raise ValidationError("idempotency_key must not be blank.")
        debits = sum(l.amount for l in data.lines if l.direction == LINE_DEBIT)
        credits = sum(l.amount for l in data.lines if l.direction == LINE_CREDIT)
        if debits <= 0 or credits <= 0:
            raise ValidationError(
                "A journal entry must contain at least one debit and one credit line."
            )
        if require_balance and debits != credits:
            raise ValidationError(
                f"Unbalanced journal entry: debits {debits} != credits {credits}."
            )
        for line in data.lines:
            account = await self.repo.get_account_or_404(line.account_id)
            if not account.is_active:
                raise ValidationError(
                    f"Account {account.code!r} ({account.name}) is inactive."
                )

    async def _assert_period_open(self, entry: JournalEntry) -> None:
        if entry.period_id is None:
            raise ValidationError(
                "Posting requires an accounting period — entries without a "
                "period cannot be posted."
            )
        period = await self.repo.get_period_or_404(entry.period_id)
        await self._assert_period_open_for(period, entry.entry_date)

    async def _assert_period_open_for(
        self, period: AccountingPeriod, entry_date: datetime.date
    ) -> None:
        if period.status != PERIOD_OPEN:
            raise ValidationError(
                f"Accounting period {period.name!r} is closed — no postings are "
                "allowed into a locked period."
            )
        if not (period.start_date <= entry_date <= period.end_date):
            raise ValidationError(
                f"entry_date {entry_date} is outside accounting period "
                f"{period.name!r} ({period.start_date}..{period.end_date})."
            )

    async def _assert_accounts_active(self, entry_id: int) -> None:
        lines = await self.repo.get_lines_for_entry(entry_id)
        for line in lines:
            account = await self.repo.get_account(line.account_id)
            if account is None or not account.is_active:
                raise ValidationError(
                    f"Account {line.account_id} is missing or inactive; cannot post."
                )

    def _assign_entry_number(self, entry: JournalEntry) -> None:
        entry.entry_number = f"JE-{entry.campus_id or 'X'}-{entry.id:06d}"
