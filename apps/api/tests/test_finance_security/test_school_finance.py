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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.domains.academic.models import AcademicYear, Class, Enrollment  # noqa: F401 — register tables for Base.metadata
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment  # noqa: F401 — register tables for Base.metadata
from app.domains.student.models import Student
from app.domains.school_finance.models import TransactionLog
from app.domains.school_finance.schemas import (
    ReconciliationCreate,
    ReconciliationItemCreate,
)
from app.domains.school_finance.service import (
    ReconciliationService,
    SchoolFinanceDashboardService,
)


async def _seed_payment(
    db_session: AsyncSession,
    campus_id: int,
    amount: int,
    key: str,
) -> int:
    """Compact payment + ledger seed (FKs are not enforced in the in-memory
    test DB, so the academic chain is stubbed with id=1)."""
    student = Student(
        first_name=f"SF{key}", last_name="Seed",
        student_number=f"SF-{key}", campus_id=campus_id, status="active",
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
