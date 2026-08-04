from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import AcademicYear, Class, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    EnrollmentRepository,
)
from app.domains.fees.models import FeeStructure, FeeType, Payment
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
from app.domains.school_finance.models import Receipt
from app.domains.school_finance.schemas import ReceiptGenerate
from app.domains.school_finance.service import ReceiptService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository


@pytest.fixture
async def receipt_env(db_session: AsyncSession) -> dict:
    """A payment with an escaping-hostile student name, ready for receipts."""
    ft_repo = FeeTypeRepository(db_session)
    fs_repo = FeeStructureRepository(db_session)
    fd_repo = FeeDueRepository(db_session)
    pmt_repo = PaymentRepository(db_session)
    student_repo = StudentRepository(db_session)
    year_repo = AcademicYearRepository(db_session)
    class_repo = ClassRepository(db_session)
    enrollment_repo = EnrollmentRepository(db_session)

    year = await year_repo.create(
        AcademicYear(
            name="Receipt Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 5", academic_year_id=year.id, status="active")
    )
    student = await student_repo.create(
        Student(
            first_name="<script>alert(1)</script>",
            last_name="Smith",
            student_number="RCP001",
            status="active",
        )
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=student.id,
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
            amount=25000,
            frequency="annual",
        )
    )
    due = await FeeDueService(
        fd_repo, student_repo, year_repo, class_repo, enrollment_repo, fs_repo, ft_repo
    ).create_dues(student.id, year.id)

    payment = await PaymentService(pmt_repo, fd_repo, student_repo).record_payment(
        PaymentCreate(
            student_id=student.id,
            fee_due_id=due[0].id,
            amount=25000,
            receipt_number="PYMT-RCP-001",
            idempotency_key="receipt-pmt-1",
        )
    )

    return {
        "db_session": db_session,
        "student": student,
        "payment": payment["payment"],
        "receipt_svc": ReceiptService(db_session),
    }


@pytest.mark.asyncio
async def test_receipt_numbers_are_unique_and_sequential(receipt_env):
    svc = receipt_env["receipt_svc"]
    payment = receipt_env["payment"]

    r1 = await svc.generate(ReceiptGenerate(payment_id=payment.id), generated_by=1)
    r2 = await svc.generate(
        ReceiptGenerate(payment_id=payment.id, notes="second"), generated_by=1
    )

    # Same payment → the second call returns the existing receipt.
    assert r1.id == r2.id
    assert r1.receipt_number == r2.receipt_number


@pytest.mark.asyncio
async def test_receipt_numbers_unique_across_payments(db_session: AsyncSession):
    """Two distinct payments produce two distinct receipt numbers."""
    ft_repo = FeeTypeRepository(db_session)
    fs_repo = FeeStructureRepository(db_session)
    fd_repo = FeeDueRepository(db_session)
    pmt_repo = PaymentRepository(db_session)
    student_repo = StudentRepository(db_session)
    year_repo = AcademicYearRepository(db_session)
    class_repo = ClassRepository(db_session)
    enrollment_repo = EnrollmentRepository(db_session)

    year = await year_repo.create(
        AcademicYear(
            name="Receipt Year 2",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 6", academic_year_id=year.id, status="active")
    )
    student = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="RCP002", status="active")
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=student.id, academic_year_id=year.id,
            class_id=cls.id, status="active",
        )
    )
    ft = await FeeTypeService(ft_repo).create(FeeTypeCreate(name="Tuition"))
    fs = await FeeStructureService(fs_repo, year_repo, class_repo, ft_repo).create(
        FeeStructureCreate(
            academic_year_id=year.id, class_id=cls.id,
            fee_type_id=ft.id, amount=30000,
        )
    )
    due = await FeeDueService(
        fd_repo, student_repo, year_repo, class_repo, enrollment_repo, fs_repo, ft_repo
    ).create_dues(student.id, year.id)

    svc = PaymentService(pmt_repo, fd_repo, student_repo)
    p1 = await svc.record_payment(
        PaymentCreate(
            student_id=student.id, fee_due_id=due[0].id, amount=10000,
            payment_method="cash", idempotency_key="rcp-multi-1",
        )
    )
    p2 = await svc.record_payment(
        PaymentCreate(
            student_id=student.id, fee_due_id=due[0].id, amount=10000,
            payment_method="cash", idempotency_key="rcp-multi-2",
        )
    )

    receipt_svc = ReceiptService(db_session)
    r1 = await receipt_svc.generate(ReceiptGenerate(payment_id=p1["payment"].id), generated_by=1)
    r2 = await receipt_svc.generate(ReceiptGenerate(payment_id=p2["payment"].id), generated_by=1)

    assert r1.receipt_number != r2.receipt_number
    assert r1.receipt_number.startswith("RCP-")
    assert r2.receipt_number.startswith("RCP-")

    rows = (await db_session.execute(select(Receipt))).scalars().all()
    numbers = [r.receipt_number for r in rows]
    assert len(numbers) == len(set(numbers))


@pytest.mark.asyncio
async def test_receipt_html_escapes_and_uses_rupee(receipt_env):
    svc = receipt_env["receipt_svc"]
    payment = receipt_env["payment"]

    receipt = await svc.generate(ReceiptGenerate(payment_id=payment.id), generated_by=1)
    html = await svc.generate_receipt_html(receipt.id)

    # HTML-escaped student name — the raw payload tag is neutralised.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)" not in html
    assert "</script> Smith" not in html

    # Indian Rupee symbol, never a bare dollar sign.
    assert "&#8377;" in html
    assert "$" not in html

    # Amount rendered in rupees from integer paise (25000 paise = 250.00).
    assert "250.00" in html


@pytest.mark.asyncio
async def test_receipt_rejects_cross_campus_payment(db_session: AsyncSession):
    """A receipt must never be generated for a payment owned by another
    campus — that would create a cross-tenant junction and disclose the
    payment amount.  Legacy NULL-campus payments stay acceptable."""
    from app.core.exceptions import ValidationError as CoreValidationError
    from app.domains.fees.models import Payment

    # Payment tagged with campus 2; caller scoped to campus 1.
    pmt_b = Payment(
        student_id=1, fee_due_id=1, campus_id=2, amount=25000,
        payment_method="cash", status="completed",
        idempotency_key="rcp-cross-1",
    )
    db_session.add(pmt_b)
    await db_session.flush()

    svc = ReceiptService(db_session)
    with pytest.raises(CoreValidationError, match="does not belong"):
        await svc.generate(
            ReceiptGenerate(payment_id=pmt_b.id), generated_by=1, campus_id=1
        )

    # Same campus is fine, and the receipt is tagged with that campus.
    own = await svc.generate(
        ReceiptGenerate(payment_id=pmt_b.id), generated_by=1, campus_id=2
    )
    assert own.campus_id == 2
    assert own.receipt_number.startswith("RCP-")

    # Legacy NULL-campus payment remains receiptable by a scoped caller.
    pmt_legacy = Payment(
        student_id=1, fee_due_id=1, campus_id=None, amount=5000,
        payment_method="cash", status="completed",
        idempotency_key="rcp-legacy-1",
    )
    db_session.add(pmt_legacy)
    await db_session.flush()
    legacy = await svc.generate(
        ReceiptGenerate(payment_id=pmt_legacy.id), generated_by=1, campus_id=1
    )
    assert legacy.campus_id == 1
