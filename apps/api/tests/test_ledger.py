"""Double-entry ledger tests (TASK 16).

Covers the accounting invariants exhaustively:

- the chart of accounts: creation, duplicate codes, type validation,
  derived normal side, deactivation guard, idempotent default chart
- accounting periods: creation, overlap/duplicate rejection, and the
  lock (posting into a closed period is impossible)
- the core invariant ``SUM(debits) == SUM(credits)``: enforced at
  posting, backstopped at the DB layer, and independently verifiable
- posting lifecycle: draft → posted is one-shot; unbalanced or
  single-direction entries can never post
- idempotency: a repeated ``idempotency_key`` resolves to the original
  entry instead of double-booking
- reversals: exact mirror, single-reversal guard, draft rejection
- trial balance: books balance, reversals net to zero
- tenant isolation: campus A can never see or post against campus B
- the API surface (auth_client): full flow + period lock via HTTP
- the fee-payment integration bridge
"""

from __future__ import annotations

import datetime
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import AuditActor
from app.domains.ledger.models import (
    ENTRY_DRAFT,
    ENTRY_POSTED,
    ENTRY_REVERSED,
    LINE_CREDIT,
    LINE_DEBIT,
    PERIOD_CLOSED,
    PERIOD_OPEN,
    JournalEntry,
    LedgerAccount,
)
from app.domains.ledger.repository import LedgerRepository
from app.domains.ledger.schemas import (
    AccountCreate,
    AccountUpdate,
    JournalEntryCreate,
    PeriodCreate,
)
from app.domains.ledger.service import LedgerService
from app.multi_tenant.models import TenantContext

# Deterministic HMAC for the (guarded) audit-chain hook on audit writes.
os.environ.setdefault("AUDIT_CHAIN_SECRET", "test-secret")


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor.user(user_id, f"user{user_id}")


def _today() -> datetime.date:
    return datetime.date(2026, 4, 15)


def _period() -> PeriodCreate:
    return PeriodCreate(
        name="FY 2025-26",
        start_date=datetime.date(2025, 4, 1),
        end_date=datetime.date(2026, 3, 31),
    )


async def _seed_chart(db: AsyncSession, tenant: TenantContext) -> list[LedgerAccount]:
    svc = LedgerService(db, tenant)
    accounts = await svc.seed_default_chart(actor=_actor())
    return accounts


async def _open_period(db: AsyncSession, tenant: TenantContext) -> int:
    svc = LedgerService(db, tenant)
    period = await svc.create_period(_period(), actor=_actor())
    return period.id


async def _balanced_entry(
    db: AsyncSession,
    tenant: TenantContext,
    accounts: list[LedgerAccount],
    period_id: int,
    *,
    amount: int = 50000,
    description: str = "Test posting",
    idempotency_key: str | None = None,
    source_type: str = "manual",
) -> JournalEntryCreate:
    by_code = {a.code: a for a in accounts}
    return JournalEntryCreate(
        period_id=period_id,
        entry_date=datetime.date(2026, 3, 15),
        description=description,
        source_type=source_type,
        idempotency_key=idempotency_key,
        lines=[
            {
                "account_id": by_code["1000"].id,
                "direction": LINE_DEBIT,
                "amount": amount,
            },
            {
                "account_id": by_code["4000"].id,
                "direction": LINE_CREDIT,
                "amount": amount,
            },
        ],
    )


# ======================================================================
# Chart of accounts
# ======================================================================


class TestChartOfAccounts:
    async def test_create_account_and_derived_normal_side(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        account = await svc.create_account(
            AccountCreate(code="9001", name="Test Asset", account_type="asset"),
            actor=_actor(),
        )
        assert account.id > 0
        assert account.campus_id == 1
        assert account.normal_side == "debit"
        assert account.is_active is True

        revenue = await svc.create_account(
            AccountCreate(code="9002", name="Test Revenue", account_type="revenue"),
            actor=_actor(),
        )
        assert revenue.normal_side == "credit"

    async def test_duplicate_code_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        await svc.create_account(
            AccountCreate(code="9001", name="A", account_type="asset"), actor=_actor()
        )
        with pytest.raises(ConflictError):
            await svc.create_account(
                AccountCreate(code="9001", name="B", account_type="asset"),
                actor=_actor(),
            )

    async def test_same_code_allowed_in_different_campus(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LedgerService(db_session, tenant_a)
        svc_b = LedgerService(db_session, tenant_b)
        await svc_a.create_account(
            AccountCreate(code="9001", name="A", account_type="asset"), actor=_actor()
        )
        # Campus B may legitimately reuse the same chart code.
        account = await svc_b.create_account(
            AccountCreate(code="9001", name="B", account_type="asset"), actor=_actor()
        )
        assert account.campus_id == 2

    async def test_invalid_account_type_rejected_by_schema(self) -> None:
        with pytest.raises(ValueError):
            AccountCreate(code="X", name="X", account_type="magic")

    async def test_deactivate_used_account_blocked(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        accounts = await _seed_chart(db_session, tenant_a)
        period_id = await _open_period(db_session, tenant_a)
        entry = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        assert entry.status == ENTRY_POSTED

        with pytest.raises(ConflictError):
            await svc.update_account(
                accounts[0].id, AccountUpdate(is_active=False), actor=_actor()
            )

    async def test_seed_default_chart_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        first = await svc.seed_default_chart(actor=_actor())
        second = await svc.seed_default_chart(actor=_actor())
        assert len(first) >= 6
        assert second == []  # nothing new on the second run
        codes = {a.code for a in first}
        assert {"1000", "1200", "2100", "3100", "4000", "5100"} <= codes


# ======================================================================
# Accounting periods
# ======================================================================


class TestAccountingPeriods:
    async def test_create_period(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = LedgerService(db_session, tenant_a)
        period = await svc.create_period(_period(), actor=_actor())
        assert period.status == PERIOD_OPEN
        assert period.campus_id == 1

    async def test_duplicate_name_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        await svc.create_period(_period(), actor=_actor())
        with pytest.raises(ConflictError):
            await svc.create_period(_period(), actor=_actor())

    async def test_overlapping_period_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        await svc.create_period(_period(), actor=_actor())
        overlap = PeriodCreate(
            name="FY 2025-26 Q3",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 6, 30),
        )
        with pytest.raises(ConflictError):
            await svc.create_period(overlap, actor=_actor())

    async def test_close_period_and_reclose_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        period = await svc.create_period(_period(), actor=_actor())
        closed = await svc.close_period(period.id, actor=_actor())
        assert closed.status == PERIOD_CLOSED
        assert closed.closed_at is not None
        with pytest.raises(ConflictError):
            await svc.close_period(period.id, actor=_actor())


# ======================================================================
# Journal entries — the core invariant
# ======================================================================


class TestPosting:
    async def _setup(self, db_session: AsyncSession, tenant_a: TenantContext):
        accounts = await _seed_chart(db_session, tenant_a)
        period_id = await _open_period(db_session, tenant_a)
        svc = LedgerService(db_session, tenant_a)
        return svc, accounts, period_id

    async def test_post_balanced_entry(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_entry(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        assert entry.status == ENTRY_DRAFT
        assert entry.entry_number.startswith("JE-")

        posted = await svc.post_entry(entry.id, actor=_actor())
        assert posted.status == ENTRY_POSTED
        assert posted.posted_at is not None
        assert posted.total_debits == posted.total_credits == 50000
        lines = await svc.repo.get_lines_for_entry(posted.id)
        assert len(lines) == 2

    async def test_post_unbalanced_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        data = await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000)
        data.lines[1].amount = 40000  # Dr 50000 / Cr 40000 — unbalanced
        entry = await svc.create_entry(data, actor=_actor())
        with pytest.raises(ValidationError):
            await svc.post_entry(entry.id, actor=_actor())

    async def test_single_direction_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        by_code = {a.code: a for a in accounts}
        data = JournalEntryCreate(
            period_id=period_id,
            entry_date=datetime.date(2026, 3, 15),
            description="Both legs debit",
            source_type="manual",
            lines=[
                {"account_id": by_code["1000"].id, "direction": LINE_DEBIT, "amount": 100},
                {"account_id": by_code["4000"].id, "direction": LINE_DEBIT, "amount": 100},
            ],
        )
        with pytest.raises(ValidationError):
            await svc.create_entry(data, actor=_actor())

    async def test_post_into_closed_period_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_entry(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        await svc.close_period(period_id, actor=_actor())
        # The lock: once the period is closed, posting is impossible.
        with pytest.raises(ValidationError):
            await svc.post_entry(entry.id, actor=_actor())

    async def test_entry_date_outside_period_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        data = await _balanced_entry(db_session, tenant_a, accounts, period_id)
        data.entry_date = datetime.date(2027, 1, 1)  # after the period ends
        with pytest.raises(ValidationError):
            await svc.create_entry(data, actor=_actor())

    async def test_post_already_posted_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        with pytest.raises(ConflictError):
            await svc.post_entry(entry.id, actor=_actor())

    async def test_post_inactive_account_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        # Create a dedicated account and immediately deactivate it.
        account = await svc.create_account(
            AccountCreate(code="9100", name="Dormant", account_type="asset"),
            actor=_actor(),
        )
        await svc.update_account(
            account.id, AccountUpdate(is_active=False), actor=_actor()
        )
        by_code = {a.code: a for a in accounts}
        data = JournalEntryCreate(
            period_id=period_id,
            entry_date=datetime.date(2026, 3, 15),
            description="Uses dormant account",
            source_type="manual",
            lines=[
                {"account_id": account.id, "direction": LINE_DEBIT, "amount": 100},
                {"account_id": by_code["4000"].id, "direction": LINE_CREDIT, "amount": 100},
            ],
        )
        with pytest.raises(ValidationError):
            await svc.create_entry(data, actor=_actor())

    async def test_idempotent_create_and_post(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        data = await _balanced_entry(
            db_session, tenant_a, accounts, period_id, idempotency_key="pmt-dup-1"
        )
        first = await svc.create_and_post(data, actor=_actor())
        second = await svc.create_and_post(data, actor=_actor())
        assert first.id == second.id
        # No duplicate book — exactly one entry with that key.
        assert await svc.repo.find_entry_by_idempotency_key("pmt-dup-1") is first

    async def test_negative_and_zero_amounts_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        by_code = {a.code: a for a in accounts}
        for bad_amount in (0, -100):
            with pytest.raises(ValueError):
                JournalEntryCreate(
                    period_id=period_id,
                    entry_date=datetime.date(2026, 3, 15),
                    description="bad amount",
                    source_type="manual",
                    lines=[
                        {
                            "account_id": by_code["1000"].id,
                            "direction": LINE_DEBIT,
                            "amount": bad_amount,
                        },
                        {
                            "account_id": by_code["4000"].id,
                            "direction": LINE_CREDIT,
                            "amount": 100,
                        },
                    ],
                )

    async def test_db_constraint_blocks_unbalanced_posting(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        """Tamper test: a direct SQL write flipping an unbalanced draft to
        posted must fail at the DB layer (ck_journal_entry_balanced)."""
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        data = await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000)
        data.lines[1].amount = 40000  # unbalanced draft
        entry = await svc.create_entry(data, actor=_actor())
        assert entry.total_debits != entry.total_credits

        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await db_session.execute(
                    text(
                        "UPDATE journal_entries SET status = :status "
                        "WHERE id = :entry_id"
                    ),
                    {"status": ENTRY_POSTED, "entry_id": entry.id},
                )


# ======================================================================
# Reversals
# ======================================================================


class TestReversals:
    async def _setup(self, db_session: AsyncSession, tenant_a: TenantContext):
        accounts = await _seed_chart(db_session, tenant_a)
        period_id = await _open_period(db_session, tenant_a)
        svc = LedgerService(db_session, tenant_a)
        return svc, accounts, period_id

    async def test_reverse_posted_entry(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        original = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        mirror = await svc.reverse_entry(
            original.id, reason="Erroneous posting", actor=_actor()
        )
        assert mirror.status == ENTRY_POSTED
        assert mirror.reversal_of_id == original.id
        assert mirror.total_debits == mirror.total_credits == 50000

        # Original is now reversed and linked back.
        reloaded = await svc.get_entry(original.id)
        assert reloaded.status == ENTRY_REVERSED
        assert reloaded.reversed_entry_id == mirror.id

        # The mirror has the opposite directions of the original.
        orig_lines = {l.account_id: l.direction for l in await svc.repo.get_lines_for_entry(original.id)}
        mir_lines = {l.account_id: l.direction for l in await svc.repo.get_lines_for_entry(mirror.id)}
        assert set(orig_lines) == set(mir_lines)
        for account_id in orig_lines:
            assert orig_lines[account_id] != mir_lines[account_id]

    async def test_double_reversal_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        original = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        await svc.reverse_entry(original.id, reason="First", actor=_actor())
        with pytest.raises(ConflictError):
            await svc.reverse_entry(original.id, reason="Second", actor=_actor())

    async def test_reverse_draft_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_entry(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        with pytest.raises(ConflictError):
            await svc.reverse_entry(entry.id, reason="nope", actor=_actor())

    async def test_reversal_into_closed_period_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        original = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id),
            actor=_actor(),
        )
        await svc.close_period(period_id, actor=_actor())
        with pytest.raises(ValidationError):
            await svc.reverse_entry(original.id, reason="late", actor=_actor())


# ======================================================================
# Trial balance / verification
# ======================================================================


class TestReporting:
    async def _setup(self, db_session: AsyncSession, tenant_a: TenantContext):
        accounts = await _seed_chart(db_session, tenant_a)
        period_id = await _open_period(db_session, tenant_a)
        svc = LedgerService(db_session, tenant_a)
        return svc, accounts, period_id

    async def test_trial_balance_balances_after_postings(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=25000),
            actor=_actor(),
        )
        tb = await svc.trial_balance()
        assert tb.balanced is True
        assert tb.total_debits == tb.total_credits == 75000
        by_code = {r.code: r for r in tb.rows}
        assert by_code["1000"].debits == 75000
        assert by_code["4000"].credits == 75000

    async def test_trial_balance_period_filter(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        # A second open period with its own posting.
        period2 = await svc.create_period(
            PeriodCreate(
                name="FY 2026-27",
                start_date=datetime.date(2026, 4, 1),
                end_date=datetime.date(2027, 3, 31),
            ),
            actor=_actor(),
        )
        data2 = await _balanced_entry(db_session, tenant_a, accounts, period2.id, amount=1000)
        data2.entry_date = datetime.date(2026, 5, 1)
        await svc.create_and_post(data2, actor=_actor())

        tb_p1 = await svc.trial_balance(period_id=period_id)
        assert tb_p1.total_debits == 50000
        tb_p2 = await svc.trial_balance(period_id=period2.id)
        assert tb_p2.total_debits == 1000

    async def test_reversal_nets_trial_balance_to_zero(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        original = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        await svc.reverse_entry(original.id, reason="void", actor=_actor())
        tb = await svc.trial_balance()
        assert tb.balanced is True
        assert tb.total_debits == tb.total_credits == 50000
        by_code = {r.code: r for r in tb.rows}
        # The reversal mirrors the original — net effect is zero.
        assert by_code["1000"].net == 0
        assert by_code["4000"].net == 0

    async def test_verify_entry_reports_truth(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        result = await svc.verify_entry(entry.id)
        assert result["balanced"] is True
        assert result["stored_debits"] == result["computed_debits"] == 50000
        assert result["lines_ok"] is True

    async def test_header_tamper_blocked_by_db_constraint(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        """Direct header mutation of a posted entry's totals violates
        ``ck_journal_entry_balanced`` and is rejected by the DB."""
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await db_session.execute(
                    text("UPDATE journal_entries SET total_debits = 1 WHERE id = :id"),
                    {"id": entry.id},
                )

    async def test_verify_entry_detects_line_tamper(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        """Line-level tampering passes the DB CHECKs (amount still
        positive) but is caught by independent verification."""
        svc, accounts, period_id = await self._setup(db_session, tenant_a)
        entry = await svc.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id, amount=50000),
            actor=_actor(),
        )
        line = (await svc.repo.get_lines_for_entry(entry.id))[0]
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE journal_lines SET amount = 40000 WHERE id = :id"),
                {"id": line.id},
            )
        # Drop the identity-map cache so verification re-reads the DB.
        db_session.expire_all()
        result = await svc.verify_entry(entry.id)
        assert result["balanced"] is False  # computed imbalance now visible
        assert result["computed_debits"] != result["stored_debits"]  # tamper visible


# ======================================================================
# Tenant isolation
# ======================================================================


class TestTenantIsolation:
    async def test_cross_tenant_account_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LedgerService(db_session, tenant_a)
        account = await svc_a.create_account(
            AccountCreate(code="9001", name="A's account", account_type="asset"),
            actor=_actor(),
        )
        svc_b = LedgerService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.get_account(account.id)  # 404 — does not exist to B

    async def test_cross_tenant_period_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LedgerService(db_session, tenant_a)
        period = await svc_a.create_period(_period(), actor=_actor())
        svc_b = LedgerService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.get_period(period.id)

    async def test_cross_tenant_posting_impossible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LedgerService(db_session, tenant_a)
        accounts = await svc_a.seed_default_chart(actor=_actor())
        period_id = await svc_a.create_period(_period(), actor=_actor())
        entry = await svc_a.create_entry(
            await _balanced_entry(db_session, tenant_a, accounts, period_id.id),
            actor=_actor(),
        )

        # Tenant B cannot post A's entry, cannot see A's period, and
        # cannot even find A's accounts.
        svc_b = LedgerService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.post_entry(entry.id, actor=_actor())
        with pytest.raises(NotFoundError):
            await svc_b.get_period(period_id.id)
        with pytest.raises(NotFoundError):
            await svc_b.get_account(accounts[0].id)

    async def test_cross_tenant_trial_balance_empty(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LedgerService(db_session, tenant_a)
        accounts = await svc_a.seed_default_chart(actor=_actor())
        period_id = await svc_a.create_period(_period(), actor=_actor())
        await svc_a.create_and_post(
            await _balanced_entry(db_session, tenant_a, accounts, period_id.id),
            actor=_actor(),
        )
        svc_b = LedgerService(db_session, tenant_b)
        tb = await svc_b.trial_balance()
        assert tb.balanced is True
        assert tb.rows == []
        assert tb.total_debits == tb.total_credits == 0

    async def test_cross_tenant_bridge_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = LedgerService(db_session, tenant_a)
        await svc_a.seed_default_chart(actor=_actor())
        period = await svc_a.create_period(_period(), actor=_actor())
        # Tenant B tries to journal a payment against A's period.
        svc_b = LedgerService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.post_fee_payment(
                campus_id=1,
                payment_id=7,
                amount=50000,
                period_id=period.id,
                actor=_actor(98),
            )


# ======================================================================
# Fee-payment integration bridge
# ======================================================================


class TestFeePaymentBridge:
    async def test_bridge_requires_seeded_chart(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        period_id = await _open_period(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.post_fee_payment(
                campus_id=1, payment_id=1, amount=50000, period_id=period_id
            )

    async def test_bridge_journals_cash_vs_receivable(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        await svc.seed_default_chart(actor=_actor())
        period_id = await _open_period(db_session, tenant_a)
        entry = await svc.post_fee_payment(
            campus_id=1,
            payment_id=42,
            amount=50000,
            period_id=period_id,
            entry_date=datetime.date(2026, 3, 15),
            idempotency_key="bridge-pmt-42",
            actor=_actor(),
        )
        assert entry.status == ENTRY_POSTED
        assert entry.source_type == "payment"
        assert entry.source_id == "42"
        lines = {l.account_id: (l.direction, l.amount) for l in await svc.repo.get_lines_for_entry(entry.id)}
        accounts, _ = await svc.repo.list_accounts()
        by_code = {a.code: a.id for a in accounts}
        assert lines[by_code["1000"]] == (LINE_DEBIT, 50000)
        assert lines[by_code["1200"]] == (LINE_CREDIT, 50000)

    async def test_bridge_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = LedgerService(db_session, tenant_a)
        await svc.seed_default_chart(actor=_actor())
        period_id = await _open_period(db_session, tenant_a)
        kwargs = {
            "campus_id": 1,
            "payment_id": 42,
            "amount": 50000,
            "period_id": period_id,
            "entry_date": datetime.date(2026, 3, 15),
            "idempotency_key": "bridge-pmt-42",
            "actor": _actor(),
        }
        first = await svc.post_fee_payment(**kwargs)
        second = await svc.post_fee_payment(**kwargs)
        assert first.id == second.id


# ======================================================================
# API surface (end-to-end through FastAPI)
# ======================================================================


class TestLedgerAPI:
    async def test_full_flow_via_api(self, auth_client) -> None:
        # Seed the default chart (admin has ledger.manage).
        resp = await auth_client.post("/api/ledger/accounts/seed")
        assert resp.status_code == 200, resp.text
        accounts = {a["code"]: a for a in resp.json()}
        assert {"1000", "4000"} <= set(accounts)

        resp = await auth_client.post(
            "/api/ledger/periods",
            json={
                "name": "FY 2025-26",
                "start_date": "2025-04-01",
                "end_date": "2026-03-31",
            },
        )
        assert resp.status_code == 201, resp.text
        period_id = resp.json()["id"]

        resp = await auth_client.post(
            "/api/ledger/entries/post",
            json={
                "period_id": period_id,
                "entry_date": "2026-03-15",
                "description": "Tuition collection",
                "source_type": "manual",
                "idempotency_key": "api-1",
                "lines": [
                    {"account_id": accounts["1000"]["id"], "direction": "debit", "amount": 50000},
                    {"account_id": accounts["4000"]["id"], "direction": "credit", "amount": 50000},
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        entry = resp.json()
        assert entry["status"] == "posted"
        assert entry["total_debits"] == entry["total_credits"] == 50000

        resp = await auth_client.get("/api/ledger/trial-balance")
        assert resp.status_code == 200, resp.text
        tb = resp.json()
        assert tb["balanced"] is True
        assert tb["total_debits"] == tb["total_credits"] == 50000

        resp = await auth_client.post(f"/api/ledger/entries/{entry['id']}/verify")
        assert resp.status_code == 405  # GET only — route exists for GET

        resp = await auth_client.get(f"/api/ledger/entries/{entry['id']}/verify")
        assert resp.status_code == 200, resp.text
        assert resp.json()["balanced"] is True

        # Reversal via API.
        resp = await auth_client.post(
            f"/api/ledger/entries/{entry['id']}/reverse",
            json={"reason": "duplicate"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "posted"

        # Lock the period; a second posting is now rejected.
        resp = await auth_client.post(f"/api/ledger/periods/{period_id}/close")
        assert resp.status_code == 200, resp.text
        resp = await auth_client.post(
            "/api/ledger/entries/post",
            json={
                "period_id": period_id,
                "entry_date": "2026-03-20",
                "description": "Late posting",
                "source_type": "manual",
                "lines": [
                    {"account_id": accounts["1000"]["id"], "direction": "debit", "amount": 100},
                    {"account_id": accounts["4000"]["id"], "direction": "credit", "amount": 100},
                ],
            },
        )
        assert resp.status_code == 422, resp.text  # locked period → validation error

    async def test_api_rejects_unbalanced_posting(self, auth_client) -> None:
        resp = await auth_client.post("/api/ledger/accounts/seed")
        accounts = {a["code"]: a for a in resp.json()}
        resp = await auth_client.post(
            "/api/ledger/periods",
            json={"name": "FY 2025-26", "start_date": "2025-04-01", "end_date": "2026-03-31"},
        )
        period_id = resp.json()["id"]
        resp = await auth_client.post(
            "/api/ledger/entries/post",
            json={
                "period_id": period_id,
                "entry_date": "2026-03-15",
                "description": "Unbalanced attempt",
                "source_type": "manual",
                "lines": [
                    {"account_id": accounts["1000"]["id"], "direction": "debit", "amount": 50000},
                    {"account_id": accounts["4000"]["id"], "direction": "credit", "amount": 40000},
                ],
            },
        )
        assert resp.status_code == 422, resp.text
        assert "Unbalanced" in resp.text

    async def test_api_unauthenticated_denied(self, client) -> None:
        resp = await client.get("/api/ledger/trial-balance")
        assert resp.status_code in (401, 403)
