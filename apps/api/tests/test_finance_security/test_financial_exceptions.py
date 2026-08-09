"""P13 — financial-exception detection tests.

Covers the four deterministic detection rules (reconciliation discrepancy,
payment without receipt, payment without ledger entry, duplicate-looking
payment), campus isolation, linked-case enrichment, and the
``financial_exception`` case source validation.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.domains.cases.service import CaseService
from app.domains.fees.models import FeeDue, Payment
from app.domains.school_finance.models import (
    PaymentReconciliation,
    ReconciliationItem,
    TransactionLog,
)
from app.domains.school_finance.schemas import (
    ReconciliationCreate,
    ReconciliationItemCreate,
    ReceiptGenerate,
)
from app.domains.school_finance.service import (
    FinancialExceptionService,
    ReceiptService,
    ReconciliationService,
)
from app.domains.student.models import Student


async def _seed_student(
    db_session: AsyncSession,
    campus_id: int,
    key: str,
) -> Student:
    student = Student(
        first_name=f"FX{key}",
        last_name="Seed",
        student_number=f"FX-{key}",
        campus_id=campus_id,
        status="active",
    )
    db_session.add(student)
    await db_session.flush()
    return student


# fee_dues has a unique (student_id, fee_structure_id) constraint — give
# every due its own structure id so a student can hold several payments.
_due_seq = [0]


def _next_fee_structure_id() -> int:
    _due_seq[0] += 1
    return _due_seq[0]


async def _seed_payment(
    db_session: AsyncSession,
    *,
    student: Student,
    campus_id: int,
    amount: int,
    key: str,
    with_log: bool = True,
    payment_date: str | None = None,
) -> Payment:
    """Payment (+ optional ledger entry) for an existing student."""
    due = FeeDue(
        student_id=student.id,
        academic_year_id=1,
        fee_structure_id=_next_fee_structure_id(),
        original_amount=amount,
        amount_paid=amount,
        campus_id=campus_id,
        status="paid",
    )
    db_session.add(due)
    await db_session.flush()

    pmt = Payment(
        student_id=student.id,
        fee_due_id=due.id,
        campus_id=campus_id,
        amount=amount,
        payment_method="cash",
        status="completed",
        idempotency_key=key,
        payment_date=payment_date or datetime.date.today().isoformat(),
    )
    db_session.add(pmt)
    await db_session.flush()

    if with_log:
        db_session.add(
            TransactionLog(
                transaction_type="payment",
                student_id=student.id,
                payment_id=pmt.id,
                fee_due_id=due.id,
                amount=amount,
                campus_id=campus_id,
                idempotency_key=f"tx-{key}",
                balance_before=0,
                balance_after=amount,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )
        await db_session.flush()
    return pmt


def _item(findings: list[dict], key: str) -> dict:
    matches = [f for f in findings if f["key"] == key]
    assert matches, f"expected finding {key} in {[f['key'] for f in findings]}"
    return matches[0]


@pytest.mark.asyncio
async def test_detects_reconciliation_discrepancy(db_session: AsyncSession):
    """Expected != actual reconciliation items surface; matched ones do not."""
    student = await _seed_student(db_session, 1, "rec")
    p_discrep = await _seed_payment(db_session, student=student, campus_id=1, amount=5000, key="rec-p1")
    p_match = await _seed_payment(db_session, student=student, campus_id=1, amount=3000, key="rec-p2")

    rec = await ReconciliationService(db_session).create(
        ReconciliationCreate(
            reconciliation_date="2026-08-01",
            total_amount=8000,
            total_count=2,
            campus_id=1,
            items=[
                ReconciliationItemCreate(payment_id=p_discrep.id, expected_amount=5000, actual_amount=4900),
                ReconciliationItemCreate(payment_id=p_match.id, expected_amount=3000, actual_amount=3000),
            ],
        ),
        reconciled_by=1,
        campus_id=1,
    )

    result = await FinancialExceptionService(db_session).list_exceptions(campus_id=1)
    keys = [f["key"] for f in result["items"]]
    assert any(k.startswith("reconciliation-discrepancy:") for k in keys)
    assert not any("matched" in f["key"] for f in result["items"])

    # the discrepancy item is the one with the non-zero difference
    disc = next(f for f in result["items"] if f["category"] == "reconciliation")
    assert disc["reconciliation_item_id"] == rec.items[0].id
    assert disc["evidence"]["difference"] == 100
    assert disc["amount"] == 5000


@pytest.mark.asyncio
async def test_payment_without_receipt_is_actionable_and_resolvable(
    db_session: AsyncSession,
):
    """A payment without a receipt is flagged; generating one clears it."""
    student = await _seed_student(db_session, 1, "rcpt")
    pmt = await _seed_payment(db_session, student=student, campus_id=1, amount=2500, key="rcpt-p1")

    svc = FinancialExceptionService(db_session)
    result = await svc.list_exceptions(campus_id=1)
    finding = _item(result["items"], f"payment-no-receipt:{pmt.id}")
    assert finding["severity"] == "medium"
    assert finding["student_id"] == student.id

    await ReceiptService(db_session).generate(
        ReceiptGenerate(payment_id=pmt.id),
        generated_by=1,
        campus_id=1,
    )
    result2 = await svc.list_exceptions(campus_id=1)
    assert f"payment-no-receipt:{pmt.id}" not in [f["key"] for f in result2["items"]]


@pytest.mark.asyncio
async def test_payment_missing_ledger_entry(db_session: AsyncSession):
    """A payment without a transaction-log entry is a ledger exception."""
    student = await _seed_student(db_session, 1, "ledger")
    pmt = await _seed_payment(db_session, student=student, campus_id=1, amount=1000, key="ledger-p1", with_log=False)

    result = await FinancialExceptionService(db_session).list_exceptions(campus_id=1)
    finding = _item(result["items"], f"payment-no-transaction:{pmt.id}")
    assert finding["severity"] == "high"


@pytest.mark.asyncio
async def test_duplicate_looking_payments(db_session: AsyncSession):
    """Two payments with the same student + amount + date are flagged."""
    student = await _seed_student(db_session, 1, "dup")
    date = "2026-07-20"
    p1 = await _seed_payment(db_session, student=student, campus_id=1, amount=9000, key="dup-p1", payment_date=date)
    p2 = await _seed_payment(db_session, student=student, campus_id=1, amount=9000, key="dup-p2", payment_date=date)
    # a different amount/date must NOT be flagged as a peer
    p3 = await _seed_payment(db_session, student=student, campus_id=1, amount=9000, key="dup-p3", payment_date="2026-07-21")

    result = await FinancialExceptionService(db_session).list_exceptions(campus_id=1)
    f1 = _item(result["items"], f"duplicate-payment:{p1.id}")
    f2 = _item(result["items"], f"duplicate-payment:{p2.id}")
    assert p3.id not in [f["payment_id"] for f in result["items"] if f["category"] == "duplicates"]
    assert p1.id in f2["evidence"]["peer_payment_ids"]
    assert p2.id in f1["evidence"]["peer_payment_ids"]


@pytest.mark.asyncio
async def test_campus_isolation(db_session: AsyncSession):
    """Anomalies in another campus never leak into this campus's list."""
    student2 = await _seed_student(db_session, 2, "iso")
    await _seed_payment(db_session, student=student2, campus_id=2, amount=7000, key="iso-p1", with_log=False)

    result = await FinancialExceptionService(db_session).list_exceptions(campus_id=1)
    assert all(f.get("student_id") is None or f.get("student_id") != student2.id for f in result["items"])


@pytest.mark.asyncio
async def test_linked_case_enrichment(db_session: AsyncSession):
    """A promoted exception shows its operational case instead of a duplicate."""
    student = await _seed_student(db_session, 1, "link")
    pmt = await _seed_payment(db_session, student=student, campus_id=1, amount=4500, key="link-p1", with_log=False)

    case = await CaseService(db_session).create_case(
        campus_id=1,
        actor_user_id=1,
        actor_name="Admin",
        title="Missing ledger entry",
        case_type="finance",
        priority="high",
        source_type="financial_exception",
        source_id=pmt.id,
        student_id=student.id,
    )

    result = await FinancialExceptionService(db_session).list_exceptions(campus_id=1)
    finding = _item(result["items"], f"payment-no-transaction:{pmt.id}")
    assert finding["linked_case"] is not None
    assert finding["linked_case"]["case_number"] == case.case_number
    assert finding["linked_case"]["status"] == case.status


@pytest.mark.asyncio
async def test_case_source_validation_for_financial_exception(db_session: AsyncSession):
    """The case service validates the referenced financial entity."""
    student = await _seed_student(db_session, 1, "val")
    pmt = await _seed_payment(db_session, student=student, campus_id=1, amount=2000, key="val-p1")

    svc = CaseService(db_session)
    # valid payment reference is accepted
    case = await svc.create_case(
        campus_id=1,
        actor_user_id=1,
        actor_name="Admin",
        title="Review payment",
        case_type="finance",
        priority="medium",
        source_type="financial_exception",
        source_id=pmt.id,
        student_id=student.id,
    )
    assert case.source_type == "financial_exception"

    # a foreign payment id is rejected
    with pytest.raises(ValidationError):
        await svc.create_case(
            campus_id=1,
            actor_user_id=1,
            actor_name="Admin",
            title="Bad reference",
            case_type="finance",
            source_type="financial_exception",
            source_id=999_999,
        )
