from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.domains.academic.models import AcademicYear, Class, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    EnrollmentRepository,
)
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
    PaymentRepository,
)
from app.domains.fees.schemas import (
    FeeStructureCreate,
    FeeTypeCreate,
    PaymentCreate,
    RefundCreate,
)
from app.domains.fees.service import (
    FeeDueService,
    FeeStructureService,
    FeeTypeService,
    PaymentService,
)
from app.domains.school_finance.models import TransactionLog
from app.domains.school_finance.schemas import VALID_TRANSACTION_TYPES
from app.domains.school_finance.service import TransactionLogService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_finance(db_session: AsyncSession) -> dict:
    """Minimal fee chain (mirrors test_payments.py): year, class, student,
    enrollment, fee type, fee structure, fee due (50000 paise)."""
    ft_repo = FeeTypeRepository(db_session, platform_context())
    fs_repo = FeeStructureRepository(db_session, platform_context())
    fd_repo = FeeDueRepository(db_session, platform_context())
    pmt_repo = PaymentRepository(db_session, platform_context())
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Ledger Inv Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    s1 = await student_repo.create(
        Student(
            first_name="Bob",
            last_name="Rivets",
            student_number="FINLEDGER001",
            status="active",
        )
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=s1.id,
            academic_year_id=year.id,
            class_id=cls.id,
            status="active",
        )
    )

    ft = await FeeTypeService(ft_repo).create(FeeTypeCreate(name="Tuition"))
    fs = await FeeStructureService(fs_repo, year_repo, class_repo, ft_repo).create(
        FeeStructureCreate(
            academic_year_id=year.id,
            class_id=cls.id,
            fee_type_id=ft.id,
            amount=50000,
            frequency="annual",
        )
    )
    due = await FeeDueService(
        fd_repo, student_repo, year_repo, class_repo, enrollment_repo, fs_repo, ft_repo
    ).create_dues(s1.id, year.id)
    fee_due = due[0]
    fee_due.campus_id = 999
    await db_session.commit()
    await db_session.refresh(fee_due)

    payment_svc = PaymentService(pmt_repo, fd_repo, student_repo)

    return {
        "db_session": db_session,
        "payment_svc": payment_svc,
        "fd_repo": fd_repo,
        "pmt_repo": pmt_repo,
        "student": s1,
        "fee_due": fee_due,
    }


async def _logs_sorted(db_session: AsyncSession, payment_id: int | None = None):
    q = select(TransactionLog).order_by(
        TransactionLog.created_at, TransactionLog.id
    )
    if payment_id is not None:
        q = q.where(TransactionLog.payment_id == payment_id)
    result = await db_session.execute(q)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Refund idempotency — a retried/double-submitted refund request must not
# apply twice (the payment path already enforces this; the refund path
# historically did not).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_replay_with_same_key_applies_once(seeded_finance):
    db_session = seeded_finance["db_session"]
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=50000,
            idempotency_key="ref-idem-1",
        )
    )
    payment_id = result["payment"].id

    # The refund carries a client idempotency key (the standard retry signal).
    first = await svc.record_refund(
        payment_id, amount=20000, reason="duplicate charge", idempotency_key="refund-req-1"
    )
    assert first["payment"].refunded_amount == 20000

    # Replay of the SAME logical request must not refund a second time.
    replay = await svc.record_refund(
        payment_id, amount=20000, reason="duplicate charge", idempotency_key="refund-req-1"
    )
    assert replay["payment"].id == first["payment"].id
    assert replay["payment"].refunded_amount == 20000  # not 40000
    assert replay["fee_due"]["amount_paid"] == 30000

    refunds = [
        l for l in await _logs_sorted(db_session, payment_id)
        if l.transaction_type == "refund"
    ]
    assert len(refunds) == 1  # a single ledger effect


@pytest.mark.asyncio
async def test_refund_key_reused_for_different_payment_conflicts(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    p1 = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
            idempotency_key="ref-key-a",
        )
    )
    p2 = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
            idempotency_key="ref-key-b",
        )
    )
    await svc.record_refund(p1["payment"].id, 5000, idempotency_key="shared-key")

    with pytest.raises(ConflictError, match="different payment"):
        await svc.record_refund(p2["payment"].id, 5000, idempotency_key="shared-key")


@pytest.mark.asyncio
async def test_refund_without_key_remains_an_intentional_new_refund(seeded_finance):
    """Contract pin: without an idempotency key each refund is a distinct
    intentional action, still bounded by the refundable balance and the DB
    CHECK constraint (refunded_amount <= amount)."""
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=10000,
            idempotency_key="ref-nokey-1",
        )
    )
    payment_id = result["payment"].id
    await svc.record_refund(payment_id, 4000)
    await svc.record_refund(payment_id, 4000)  # distinct action → 8000 total
    with pytest.raises(ValidationError, match="exceeds the refundable"):
        await svc.record_refund(payment_id, 3000)  # only 2000 left

    payment = await svc.get_payment(payment_id)
    assert payment.refunded_amount == 8000
    assert payment.status == "partially_refunded"


@pytest.mark.asyncio
async def test_refund_blank_key_rejected_by_schema(seeded_finance):
    with pytest.raises(PydanticValidationError):
        RefundCreate(amount=1000, idempotency_key="   ")


# ---------------------------------------------------------------------------
# Ledger mathematical invariants — the running balance chain must agree with
# the authoritative recomputed balance, and every valid transaction type
# must participate in both (no silent exclusion).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_chain_matches_recomputed_balance(seeded_finance):
    db_session = seeded_finance["db_session"]
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    p = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=30000,
            idempotency_key="chain-1",
        )
    )
    await svc.record_refund(p["payment"].id, 10000)
    await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=5000,
            idempotency_key="chain-2",
        )
    )

    tx_svc = TransactionLogService(db_session)
    assert await tx_svc.get_student_balance(s1.id) == 25000

    logs = await _logs_sorted(db_session)
    assert len(logs) == 3
    running = 0
    for log in logs:
        assert log.balance_before == running
        sign = -1 if log.transaction_type == "refund" else 1
        running = log.balance_before + sign * log.amount
        assert log.balance_after == running
    assert running == 25000


@pytest.mark.asyncio
async def test_every_valid_transaction_type_keeps_chain_and_sum_consistent(seeded_finance):
    """Every type accepted by the ledger schema must be counted by BOTH the
    running chain and the recomputed balance.  A type that the chain counts
    but the recompute ignores silently drifts the two apart."""
    db_session = seeded_finance["db_session"]
    s1 = seeded_finance["student"]

    tx_svc = TransactionLogService(db_session)
    for t in sorted(VALID_TRANSACTION_TYPES):
        await tx_svc.record(transaction_type=t, student_id=s1.id, amount=1000)

    logs = await _logs_sorted(db_session)
    chain_after = logs[-1].balance_after
    recomputed = await tx_svc.get_student_balance(s1.id)
    assert chain_after == recomputed


@pytest.mark.asyncio
async def test_ledger_record_rejects_invalid_type_and_amount(seeded_finance):
    """Service-layer validation: a direct caller cannot write garbage into
    the immutable ledger (the router schema is not the only entry point)."""
    db_session = seeded_finance["db_session"]
    s1 = seeded_finance["student"]
    tx_svc = TransactionLogService(db_session)

    with pytest.raises(ValidationError, match="Invalid transaction type"):
        await tx_svc.record(transaction_type="bogus", student_id=s1.id, amount=1000)
    with pytest.raises(ValidationError, match="positive"):
        await tx_svc.record(transaction_type="payment", student_id=s1.id, amount=0)
    with pytest.raises(ValidationError, match="positive"):
        await tx_svc.record(transaction_type="refund", student_id=s1.id, amount=-50)

    # Nothing was written.
    assert await _logs_sorted(db_session) == []


@pytest.mark.asyncio
async def test_ledger_record_serializes_per_student_with_row_lock(seeded_finance):
    """The student-row ``SELECT ... FOR UPDATE`` is the per-student
    serialization point for the running balance.  SQLite ignores the lock,
    so the concurrency race itself cannot be reproduced deterministically
    here — but this test pins that the lock IS issued, so a future refactor
    that drops it fails CI instead of silently drifting the chain on
    PostgreSQL."""
    from unittest import mock

    from app.domains.school_finance.service import TransactionLogService

    db_session = seeded_finance["db_session"]
    s1 = seeded_finance["student"]
    real_execute = db_session.execute
    student_lock_seen = []

    async def spy(statement, *args, **kwargs):
        text = str(statement)
        if "FOR UPDATE" in text and "students" in text:
            student_lock_seen.append(statement)
        return await real_execute(statement, *args, **kwargs)

    tx_svc = TransactionLogService(db_session)
    with mock.patch.object(db_session, "execute", new=spy):
        await tx_svc.record(
            transaction_type="payment", student_id=s1.id, amount=1000
        )

    assert student_lock_seen, "record() must take the student-row FOR UPDATE lock"


@pytest.mark.asyncio
async def test_ledger_replay_returns_existing_row(seeded_finance):
    """record() is itself idempotent on the ledger key (retried financial
    operations never double-journal)."""
    db_session = seeded_finance["db_session"]
    s1 = seeded_finance["student"]
    tx_svc = TransactionLogService(db_session)

    first = await tx_svc.record(
        transaction_type="payment", student_id=s1.id, amount=1000,
        idempotency_key="ledger-dup-1",
    )
    second = await tx_svc.record(
        transaction_type="payment", student_id=s1.id, amount=1000,
        idempotency_key="ledger-dup-1",
    )
    assert second.id == first.id
    assert len(await _logs_sorted(db_session)) == 1
    assert await tx_svc.get_student_balance(s1.id) == 1000
