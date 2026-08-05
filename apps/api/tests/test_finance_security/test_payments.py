from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
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
)
from app.domains.fees.service import (
    FeeDueService,
    FeeStructureService,
    FeeTypeService,
    PaymentService,
)
from app.domains.school_finance.models import TransactionLog
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_finance(db_session: AsyncSession) -> dict:
    """Minimal fee chain: year, class, student, enrollment, fee type,
    fee structure, fee due (amount 50000 paise)."""
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
            name="Fin Sec Year",
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
            first_name="Alice",
            last_name="Smith",
            student_number="FIN001",
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


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_idempotent_replay_returns_same_payment(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]
    key = "ord-12345"

    first = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id,
            fee_due_id=fee_due.id,
            amount=20000,
            idempotency_key=key,
        )
    )
    second = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id,
            fee_due_id=fee_due.id,
            amount=20000,
            idempotency_key=key,
        )
    )

    assert second["payment"].id == first["payment"].id
    assert second["payment"].amount == first["payment"].amount
    # Fee due charged exactly once.
    assert second["fee_due"]["amount_paid"] == 20000


@pytest.mark.asyncio
async def test_payment_idempotency_does_not_double_charge(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]
    repo = seeded_finance["pmt_repo"]

    await svc.record_payment(
        PaymentCreate(
            student_id=s1.id,
            fee_due_id=fee_due.id,
            amount=25000,
            idempotency_key="key-a",
        )
    )
    # A *different* key for the same due is a genuinely new payment.
    await svc.record_payment(
        PaymentCreate(
            student_id=s1.id,
            fee_due_id=fee_due.id,
            amount=25000,
            idempotency_key="key-b",
        )
    )
    await svc.record_payment(
        PaymentCreate(
            student_id=s1.id,
            fee_due_id=fee_due.id,
            amount=25000,
            idempotency_key="key-b",
        )
    )

    payments, _ = await repo.list(fee_due_id=fee_due.id)
    assert len(payments) == 2
    assert sum(p.amount for p in payments) == 50000


@pytest.mark.asyncio
async def test_concurrent_same_idempotency_key_single_payment(seeded_finance):
    """A duplicate racing the winner's commit collapses to one payment.

    The pre-check is made to *miss* (simulating a request that read the
    DB before the winner committed); the INSERT then collides on the
    unique ``idempotency_key`` and the service must recover by returning
    the already-created payment instead of double-booking.
    """
    import asyncio
    from unittest import mock

    from app.domains.fees.repository import PaymentRepository

    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]
    db_session = seeded_finance["db_session"]
    key = "concurrent-key"

    winner = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
            idempotency_key=key,
        )
    )

    original = PaymentRepository.get_by_idempotency_key

    async def side_effect(self, idempotency_key):
        if side_effect.first:
            side_effect.first = False
            return None  # simulate a stale pre-check
        return await original(self, idempotency_key)

    side_effect.first = True

    with mock.patch.object(
        PaymentRepository, "get_by_idempotency_key", side_effect
    ):
        duplicate = await svc.record_payment(
            PaymentCreate(
                student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
                idempotency_key=key,
            )
        )

    assert duplicate["payment"].id == winner["payment"].id
    assert duplicate["fee_due"]["amount_paid"] == 20000

    rows = (
        await db_session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
    ).scalars().all()
    assert len(rows) == 1
    fee_due = await db_session.get(FeeDue, fee_due.id)
    assert fee_due.amount_paid == 20000
    assert fee_due.status == "partially_paid"


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_refund_transitions(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=50000,
            idempotency_key="ref-full-1",
        )
    )
    payment_id = result["payment"].id
    assert result["payment"].campus_id == 999
    assert result["fee_due"]["campus_id"] == 999

    refunded = await svc.record_refund(payment_id, amount=50000, reason="Duplicate charge")
    assert refunded["payment"].status == "refunded"
    assert refunded["payment"].refunded_amount == 50000
    assert refunded["fee_due"]["status"] == "unpaid"
    assert refunded["fee_due"]["amount_paid"] == 0


@pytest.mark.asyncio
async def test_partial_refund_transitions(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=40000,
            idempotency_key="ref-part-1",
        )
    )
    payment_id = result["payment"].id

    refunded = await svc.record_refund(payment_id, amount=10000)
    assert refunded["payment"].status == "partially_refunded"
    assert refunded["payment"].refunded_amount == 10000
    assert refunded["fee_due"]["amount_paid"] == 30000
    assert refunded["fee_due"]["status"] == "partially_paid"


@pytest.mark.asyncio
async def test_refund_cannot_exceed_refundable(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=30000,
            idempotency_key="ref-over-1",
        )
    )
    payment_id = result["payment"].id

    with pytest.raises(ValidationError, match="exceeds the refundable"):
        await svc.record_refund(payment_id, amount=30001)


@pytest.mark.asyncio
async def test_refund_fully_refunded_payment_rejected(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
            idempotency_key="ref-double-1",
        )
    )
    payment_id = result["payment"].id
    await svc.record_refund(payment_id, amount=20000)

    with pytest.raises(ConflictError, match="already fully refunded"):
        await svc.record_refund(payment_id, amount=5000)


@pytest.mark.asyncio
async def test_refund_unknown_payment(seeded_finance):
    svc = seeded_finance["payment_svc"]
    with pytest.raises(NotFoundError, match="not found"):
        await svc.record_refund(999999, amount=1000)


@pytest.mark.asyncio
async def test_refund_zero_rejected_by_schema(seeded_finance):
    from app.domains.fees.schemas import RefundCreate

    with pytest.raises(PydanticValidationError):
        RefundCreate(amount=0)


@pytest.mark.asyncio
async def test_concurrent_refund_must_re_read_payment_under_lock(seeded_finance):
    """Two refunds racing on the same payment must serialize on the row
    lock and re-read the fresh ``refunded_amount`` — a stale pre-check
    must never let the same money be refunded twice (which would journal
    a second refund against a balance that no longer exists).

    The trap below makes the test FAIL if the refund path ever regresses
    to an unlocked ``get_by_id`` read: the refundable balance has to be
    computed from the locked, post-commit snapshot.
    """
    from unittest import mock

    from app.domains.fees.repository import PaymentRepository

    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]
    db_session = seeded_finance["db_session"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
            idempotency_key="ref-lock-1",
        )
    )
    payment_id = result["payment"].id
    await svc.record_refund(payment_id, amount=10000)

    async def _trap(self, pid):
        raise AssertionError(
            "refund must re-read the payment via get_by_id_for_update "
            "(unlocked get_by_id is a stale snapshot)"
        )

    with mock.patch.object(PaymentRepository, "get_by_id", new=_trap):
        second = await svc.record_refund(payment_id, amount=10000)

    assert second["payment"].status == "refunded"
    assert second["payment"].refunded_amount == 20000
    assert second["fee_due"]["amount_paid"] == 0
    assert second["fee_due"]["status"] == "unpaid"

    rows = (
        await db_session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
    ).scalars().all()
    assert rows[0].refunded_amount == 20000
    assert rows[0].status == "refunded"

    # Both refunds are journaled with distinct idempotency keys and the
    # ledger balance is consistent with the payment state.
    logs = (
        await db_session.execute(
            select(TransactionLog)
            .where(TransactionLog.payment_id == payment_id)
            .order_by(TransactionLog.created_at)
        )
    ).scalars().all()
    refunds = [l for l in logs if l.transaction_type == "refund"]
    assert len(refunds) == 2
    assert sum(l.amount for l in refunds) == 20000
    assert logs[-1].balance_after == 0


@pytest.mark.asyncio
async def test_refund_after_partial_refund_uses_fresh_balance(seeded_finance):
    """A refund after an earlier partial refund is validated against the
    *current* refunded_amount, never a stale one."""
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=20000,
            idempotency_key="ref-fresh-1",
        )
    )
    payment_id = result["payment"].id
    await svc.record_refund(payment_id, amount=15000)

    # Only 5000 remains refundable — a 6000 refund must be rejected.
    with pytest.raises(ValidationError, match="exceeds the refundable"):
        await svc.record_refund(payment_id, amount=6000)

    ok = await svc.record_refund(payment_id, amount=5000)
    assert ok["payment"].status == "refunded"
    assert ok["payment"].refunded_amount == 20000
    assert ok["fee_due"]["amount_paid"] == 0


# ---------------------------------------------------------------------------
# Money integrity (integer minor units — never floats)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_money_fields_are_integers(seeded_finance):
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=12345,
            idempotency_key="int-money-1",
        )
    )
    payment = result["payment"]
    assert type(payment.amount) is int
    assert type(payment.refunded_amount) is int
    assert type(result["fee_due"]["amount_paid"]) is int

    refunded = await svc.record_refund(payment.id, amount=345)
    assert type(refunded["payment"].refunded_amount) is int
    assert type(refunded["fee_due"]["amount_paid"]) is int


@pytest.mark.asyncio
async def test_payment_zero_amount_rejected_by_schema(seeded_finance):
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]
    with pytest.raises(PydanticValidationError, match="positive"):
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=0,
        )


@pytest.mark.asyncio
async def test_idempotency_key_blank_rejected_by_schema(seeded_finance):
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]
    with pytest.raises(PydanticValidationError):
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=1000,
            idempotency_key="   ",
        )


# ---------------------------------------------------------------------------
# Ledger / audit wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_and_refund_write_ledger(seeded_finance):
    db_session = seeded_finance["db_session"]
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=50000,
            idempotency_key="ledger-1",
        )
    )
    logs = (
        await db_session.execute(
            select(TransactionLog).where(TransactionLog.payment_id == result["payment"].id)
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].transaction_type == "payment"
    assert logs[0].amount == 50000
    assert logs[0].balance_after == 50000

    await svc.record_refund(result["payment"].id, amount=10000)
    refund_logs = (
        await db_session.execute(
            select(TransactionLog).where(TransactionLog.payment_id == result["payment"].id)
        )
    ).scalars().all()
    assert any(l.transaction_type == "refund" and l.amount == 10000 for l in refund_logs)


@pytest.mark.asyncio
async def test_payment_writes_audit_entry(seeded_finance):
    db_session = seeded_finance["db_session"]
    svc = seeded_finance["payment_svc"]
    s1 = seeded_finance["student"]
    fee_due = seeded_finance["fee_due"]

    from app.domains.audit.actors import AuditActor
    from app.domains.audit.models import AuditLog

    result = await svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id, amount=5000,
            idempotency_key="audit-1",
        ),
        actor=AuditActor.user(1, "admin"),
    )
    entry = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "payment")
        )
    ).scalars().first()
    assert entry is not None
    assert entry.resource_id == str(result["payment"].id)
