"""School-finance integrity tests.

* A reconciliation can never be created for, or reference payments from,
  another campus (relationship-table cross-tenant write protection).
* The finance dashboard is campus-scoped and its queries are correct —
  a tenant sees only its own totals and recent transactions.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.domains.academic.models import (  # noqa: F401 — register tables for Base.metadata
    AcademicYear,
    Class,
    Enrollment,
)
from app.domains.fees.models import (  # noqa: F401 — register tables for Base.metadata
    FeeDue,
    FeeStructure,
    FeeType,
    Payment,
)
from app.domains.school_finance.models import TransactionLog
from app.domains.school_finance.schemas import (
    ReconciliationCreate,
    ReconciliationItemCreate,
)
from app.domains.school_finance.service import (
    ReconciliationService,
    SchoolFinanceDashboardService,
)
from app.domains.student.models import Student


async def _seed_payment(
    db_session: AsyncSession,
    campus_id: int,
    amount: int,
    key: str,
    student_tag: str | None = None,
) -> int:
    """Compact payment + ledger seed (FKs are not enforced in the in-memory
    test DB, so the academic chain is stubbed with id=1).

    ``student_tag`` distinguishes rows that reuse the same ``key`` (e.g.
    same-campus idempotent replay) because ``students.student_number`` is
    globally unique while the payment idempotency key is campus-scoped.
    """
    student = Student(
        first_name=f"SF{key}", last_name="Seed",
        student_number=f"SF-{student_tag or key}", campus_id=campus_id,
        status="active",
    )
    db_session.add(student)
    await db_session.flush()

    due = FeeDue(
        student_id=student.id, academic_year_id=1, fee_structure_id=1,
        original_amount=amount, amount_paid=amount, campus_id=campus_id,
        status="paid",
    )
    db_session.add(due)
    await db_session.flush()

    pmt = Payment(
        student_id=student.id, fee_due_id=due.id, campus_id=campus_id,
        amount=amount, payment_method="cash", status="completed",
        idempotency_key=key,
        payment_date=datetime.date.today().isoformat(),
    )
    db_session.add(pmt)
    await db_session.flush()

    db_session.add(TransactionLog(
        transaction_type="payment", student_id=student.id,
        payment_id=pmt.id, fee_due_id=due.id, amount=amount,
        campus_id=campus_id, idempotency_key=f"tx-{key}",
        balance_before=0, balance_after=amount,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))
    await db_session.flush()
    return pmt.id


# ---------------------------------------------------------------------------
# Reconciliation — no cross-tenant junctions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconciliation_rejects_cross_campus_payment(db_session: AsyncSession):
    """A reconciliation must never reference a payment from another campus."""
    await _seed_payment(db_session, 1, 5000, "rec-own-1")
    p_other = await _seed_payment(db_session, 2, 9000, "rec-other-1")

    svc = ReconciliationService(db_session)
    data = ReconciliationCreate(
        reconciliation_date="2026-08-01",
        total_amount=9000, total_count=1,
        campus_id=1,
        items=[ReconciliationItemCreate(
            payment_id=p_other, expected_amount=9000, actual_amount=9000,
        )],
    )
    with pytest.raises(ValidationError, match="does not belong"):
        await svc.create(data, reconciled_by=1, campus_id=1)


@pytest.mark.asyncio
async def test_reconciliation_pins_authoritative_campus(db_session: AsyncSession):
    """The campus scope supplied by the router wins over any client-supplied
    campus_id in the payload, and items are validated against it."""
    p_own = await _seed_payment(db_session, 1, 5000, "rec-pin-1")

    svc = ReconciliationService(db_session)
    data = ReconciliationCreate(
        reconciliation_date="2026-08-01",
        total_amount=5000, total_count=1,
        campus_id=2,  # client-supplied value — must be ignored
        items=[ReconciliationItemCreate(
            payment_id=p_own, expected_amount=5000, actual_amount=5000,
        )],
    )
    rec = await svc.create(data, reconciled_by=1, campus_id=1)
    assert rec.campus_id == 1, "client campus_id must not win"
    assert rec.status == "draft"

    items = rec.items
    assert len(items) == 1
    assert items[0].status == "matched"


# ---------------------------------------------------------------------------
# Dashboard — campus scoping + correct query construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_is_campus_scoped(db_session: AsyncSession):
    """The dashboard aggregates only the caller's campus and never crashes
    when a campus filter is supplied (regression: the campus predicate used
    to be applied *after* executing the query)."""
    await _seed_payment(db_session, 1, 20000, "dash-a-1")
    await _seed_payment(db_session, 2, 30000, "dash-b-1")

    svc = SchoolFinanceDashboardService(db_session)

    dash_a = await svc.get_dashboard(campus_id=1)
    assert dash_a["total_collected"] == 20000
    assert dash_a["payment_count"] == 1
    assert dash_a["today_collection"] == 20000
    assert len(dash_a["recent_transactions"]) == 1
    assert all(t["campus_id"] == 1 for t in dash_a["recent_transactions"])

    dash_b = await svc.get_dashboard(campus_id=2)
    assert dash_b["total_collected"] == 30000
    assert dash_b["payment_count"] == 1

    # No filter → the platform view sums both campuses.
    dash_all = await svc.get_dashboard(campus_id=None)
    assert dash_all["total_collected"] == 50000
    assert dash_all["payment_count"] == 2


# ---------------------------------------------------------------------------
# Idempotency keys — scoped per campus (migration 047)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_idempotency_keys_are_campus_scoped(db_session: AsyncSession):
    """Two independent campuses may legitimately use the same client-supplied
    idempotency key (regression for migration 047: the unique constraint used
    to be global, so the second campus hit a spurious IntegrityError/409).

    A same-campus duplicate is still rejected — the composite
    (campus_id, idempotency_key) constraint enforces one payment per key.
    """
    await _seed_payment(db_session, 1, 5000, "camp-a-key")
    await _seed_payment(db_session, 2, 5000, "camp-b-key")

    rows_a = (
        await db_session.execute(
            select(Payment).where(Payment.idempotency_key == "camp-a-key")
        )
    ).scalars().all()
    rows_b = (
        await db_session.execute(
            select(Payment).where(Payment.idempotency_key == "camp-b-key")
        )
    ).scalars().all()
    assert len(rows_a) == 1 and rows_a[0].campus_id == 1
    assert len(rows_b) == 1 and rows_b[0].campus_id == 2

    # Same campus + same key → the composite (campus_id, idempotency_key)
    # constraint fires: replay is a DB-level IntegrityError, not a silent
    # duplicate. student_tag varies because students.student_number is
    # globally unique even though the payment idempotency key is campus-scoped.
    # A savepoint confines the expected failure so the outer test
    # transaction (with the earlier rows) survives.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await _seed_payment(db_session, 1, 5000, "camp-a-key", student_tag="camp-a-key-replay")

    rows_a2 = (
        await db_session.execute(
            select(Payment).where(Payment.idempotency_key == "camp-a-key")
        )
    ).scalars().all()
    assert len(rows_a2) == 1  # one payment per (campus, key)


@pytest.mark.asyncio
async def test_transaction_log_idempotency_scoped_by_campus(db_session: AsyncSession):
    """``TransactionLogService.find_by_idempotency_key`` must not resolve a
    key that belongs to another campus (regression for the unscoped lookup
    fixed alongside migration 047).
    """
    from app.domains.school_finance.service import TransactionLogService

    await _seed_payment(db_session, 1, 5000, "tx-scope-a")
    await _seed_payment(db_session, 2, 7000, "tx-scope-b")

    svc = TransactionLogService(db_session)

    # Campus 1 must find its own ledger row...
    found = await svc.find_by_idempotency_key("tx-tx-scope-a", campus_id=1)
    assert found is not None
    assert found.campus_id == 1

    # ...and must NOT see campus 2's row under the same key.
    cross = await svc.find_by_idempotency_key("tx-tx-scope-b", campus_id=1)
    assert cross is None

    # Same-campus replay resolves to the original row.
    same = await svc.find_by_idempotency_key("tx-tx-scope-a", campus_id=1)
    assert same is not None and same.id == found.id


# ---------------------------------------------------------------------------
# Transaction log — free-text search (P13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transaction_list_q_search(db_session: AsyncSession):
    """The ledger's `q` filter matches reference numbers / descriptions /
    idempotency keys and resolves numeric queries against the student id."""
    from app.domains.school_finance.service import TransactionLogService

    p1 = await _seed_payment(db_session, 1, 5000, "q-src-1")
    p2 = await _seed_payment(db_session, 1, 8000, "q-src-2")
    svc = TransactionLogService(db_session)

    # reference-number search (the ledger's own reference_number column)
    stmt1 = select(TransactionLog).where(TransactionLog.payment_id == p1)
    row1 = (await db_session.execute(stmt1)).scalar_one()
    row1.reference_number = "RCP-TEST-1001"
    stmt2 = select(TransactionLog).where(TransactionLog.payment_id == p2)
    row2 = (await db_session.execute(stmt2)).scalar_one()
    row2.reference_number = "RCP-TEST-2002"
    await db_session.flush()

    rows, total = await svc.list(q="RCP-TEST-1001")
    assert total == 1
    assert rows[0].payment_id == p1

    rows, total = await svc.list(q="2002")
    assert total == 1
    assert rows[0].payment_id == p2

    # numeric query → student-id resolution
    rows, total = await svc.list(q=str(row1.student_id))
    assert total >= 1

    # no match
    rows, total = await svc.list(q="no-such-ledger-entry")
    assert total == 0

    # combines with existing filters (amount range + campus scope)
    rows, total = await svc.list(q="RCP-TEST", min_amount=6000, campus_id=1)
    assert total == 1
    assert rows[0].payment_id == p2


@pytest.mark.asyncio
async def test_reconciliation_list_q_search_and_status_filter(db_session: AsyncSession):
    """The reconciliation `q` filter (P13) matches notes and resolves numeric
    queries against the reconciliation id, composing with the status facet."""
    p1 = await _seed_payment(db_session, 1, 5000, "rec-q-1")
    p2 = await _seed_payment(db_session, 1, 8000, "rec-q-2")
    svc = ReconciliationService(db_session)

    rec1 = await svc.create(
        ReconciliationCreate(
            reconciliation_date="2026-08-01", total_amount=5000, total_count=1,
            notes="Term 1 close — cash drawer",
            items=[ReconciliationItemCreate(
                payment_id=p1, expected_amount=5000, actual_amount=5000,
            )],
        ),
        reconciled_by=1, campus_id=1,
    )
    rec2 = await svc.create(
        ReconciliationCreate(
            reconciliation_date="2026-08-02", total_amount=8000, total_count=1,
            notes="Term 1 close — bank statement",
            items=[ReconciliationItemCreate(
                payment_id=p2, expected_amount=8000, actual_amount=8000,
            )],
        ),
        reconciled_by=1, campus_id=1,
    )

    # notes search
    rows, total = await svc.list(q="cash drawer")
    assert total == 1
    assert rows[0].id == rec1.id

    # numeric query → reconciliation-id resolution
    rows, total = await svc.list(q=str(rec2.id))
    assert total == 1
    assert rows[0].id == rec2.id

    # composes with the status facet
    rows, total = await svc.list(status_filter="draft", q="Term 1 close")
    assert total == 2
    assert {r.id for r in rows} == {rec1.id, rec2.id}

    # no match
    rows, total = await svc.list(q="no-such-note")
    assert total == 0
