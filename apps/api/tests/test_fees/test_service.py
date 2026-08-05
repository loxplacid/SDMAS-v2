from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from pydantic import ValidationError as PydanticValidationError
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
    FeeStructureUpdate,
    FeeTypeCreate,
    FeeTypeUpdate,
    PaymentCreate,
)
from app.domains.fees.service import (
    FeeDueService,
    FeeStructureService,
    FeeTypeService,
    PaymentService,
    SummaryService,
)
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_env(db_session: AsyncSession):
    ft_repo = FeeTypeRepository(db_session, platform_context())
    fs_repo = FeeStructureRepository(db_session, platform_context())
    fd_repo = FeeDueRepository(db_session, platform_context())
    pmt_repo = PaymentRepository(db_session, platform_context())
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())

    fee_type_svc = FeeTypeService(ft_repo)
    fee_structure_svc = FeeStructureService(fs_repo, year_repo, class_repo, ft_repo)
    fee_due_svc = FeeDueService(
        fd_repo, student_repo, year_repo, class_repo, enrollment_repo, fs_repo, ft_repo
    )
    payment_svc = PaymentService(pmt_repo, fd_repo, student_repo)
    summary_svc = SummaryService(fd_repo, enrollment_repo)

    year = await year_repo.create(
        AcademicYear(
            name="Test Year", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31), status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    s1 = await student_repo.create(
        Student(first_name="Alice", last_name="Smith", student_number="FEE001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="FEE002", status="active")
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=s1.id, academic_year_id=year.id,
            class_id=cls.id, status="active",
        )
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=s2.id, academic_year_id=year.id,
            class_id=cls.id, status="active",
        )
    )

    ft = await fee_type_svc.create(FeeTypeCreate(name="Tuition"))
    ft2 = await fee_type_svc.create(FeeTypeCreate(name="Library Fee"))

    fs = await fee_structure_svc.create(
        FeeStructureCreate(
            academic_year_id=year.id, class_id=cls.id,
            fee_type_id=ft.id, amount=50000, frequency="annual",
        )
    )
    fs2 = await fee_structure_svc.create(
        FeeStructureCreate(
            academic_year_id=year.id, class_id=cls.id,
            fee_type_id=ft2.id, amount=10000, frequency="annual",
        )
    )

    return {
        "ft_repo": ft_repo,
        "fs_repo": fs_repo,
        "fd_repo": fd_repo,
        "pmt_repo": pmt_repo,
        "student_repo": student_repo,
        "year_repo": year_repo,
        "class_repo": class_repo,
        "enrollment_repo": enrollment_repo,
        "fee_type_svc": fee_type_svc,
        "fee_structure_svc": fee_structure_svc,
        "fee_due_svc": fee_due_svc,
        "payment_svc": payment_svc,
        "summary_svc": summary_svc,
        "year": year,
        "class": cls,
        "s1": s1,
        "s2": s2,
        "ft": ft,
        "ft2": ft2,
        "fs": fs,
        "fs2": fs2,
    }


# ---------------------------------------------------------------------------
# FeeTypeService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fee_type(seeded_env):
    svc = seeded_env["fee_type_svc"]
    ft = await svc.create(FeeTypeCreate(name="Sports Fee"))
    assert ft.id is not None
    assert ft.name == "Sports Fee"
    assert ft.status == "active"


@pytest.mark.asyncio
async def test_create_fee_type_duplicate(seeded_env):
    svc = seeded_env["fee_type_svc"]
    with pytest.raises(ConflictError, match="already exists"):
        await svc.create(FeeTypeCreate(name="Tuition"))


@pytest.mark.asyncio
async def test_get_fee_type(seeded_env):
    svc = seeded_env["fee_type_svc"]
    ft = await svc.get(seeded_env["ft"].id)
    assert ft.name == "Tuition"


@pytest.mark.asyncio
async def test_get_fee_type_not_found(seeded_env):
    svc = seeded_env["fee_type_svc"]
    with pytest.raises(NotFoundError, match="not found"):
        await svc.get(999)


@pytest.mark.asyncio
async def test_update_fee_type(seeded_env):
    svc = seeded_env["fee_type_svc"]
    ft = await svc.update(
        seeded_env["ft"].id,
        FeeTypeUpdate(name="Updated Tuition", description="Updated desc"),
    )
    assert ft.name == "Updated Tuition"
    assert ft.description == "Updated desc"


@pytest.mark.asyncio
async def test_update_fee_type_invalid_status(seeded_env):
    svc = seeded_env["fee_type_svc"]
    with pytest.raises(PydanticValidationError, match="Invalid fee type status"):
        await svc.update(
            seeded_env["ft"].id,
            FeeTypeUpdate(status="invalid"),
        )


@pytest.mark.asyncio
async def test_deactivate_fee_type(seeded_env):
    svc = seeded_env["fee_type_svc"]
    ft = await svc.deactivate(seeded_env["ft"].id)
    assert ft.status == "inactive"


@pytest.mark.asyncio
async def test_list_fee_types(seeded_env):
    svc = seeded_env["fee_type_svc"]
    items, total = await svc.list()
    assert total >= 2


# ---------------------------------------------------------------------------
# FeeStructureService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fee_structure(seeded_env):
    svc = seeded_env["fee_structure_svc"]
    ft_svc = seeded_env["fee_type_svc"]
    new_ft = await ft_svc.create(FeeTypeCreate(name="New FT for Struct"))
    year = seeded_env["year"]
    cls = seeded_env["class"]
    fs = await svc.create(
        FeeStructureCreate(
            academic_year_id=year.id, class_id=cls.id,
            fee_type_id=new_ft.id, amount=25000, frequency="term",
        )
    )
    assert fs.id is not None
    assert fs.amount == 25000


@pytest.mark.asyncio
async def test_create_fee_structure_duplicate(seeded_env):
    svc = seeded_env["fee_structure_svc"]
    fs = seeded_env["fs"]
    with pytest.raises(ConflictError, match="already exists"):
        await svc.create(
            FeeStructureCreate(
                academic_year_id=fs.academic_year_id, class_id=fs.class_id,
                fee_type_id=fs.fee_type_id, amount=50000,
            )
        )


@pytest.mark.asyncio
async def test_get_fee_structure(seeded_env):
    svc = seeded_env["fee_structure_svc"]
    fs = await svc.get(seeded_env["fs"].id)
    assert fs.amount == 50000


@pytest.mark.asyncio
async def test_update_fee_structure(seeded_env):
    svc = seeded_env["fee_structure_svc"]
    fs = await svc.update(
        seeded_env["fs"].id,
        FeeStructureUpdate(amount=60000),
    )
    assert fs.amount == 60000


@pytest.mark.asyncio
async def test_update_fee_structure_invalid_status(seeded_env):
    svc = seeded_env["fee_structure_svc"]
    with pytest.raises(PydanticValidationError, match="Invalid fee structure status"):
        await svc.update(seeded_env["fs"].id, FeeStructureUpdate(status="invalid"))


@pytest.mark.asyncio
async def test_list_fee_structures(seeded_env):
    svc = seeded_env["fee_structure_svc"]
    items, total = await svc.list()
    assert total >= 2


# ---------------------------------------------------------------------------
# FeeDueService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_fee_dues(seeded_env):
    svc = seeded_env["fee_due_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await svc.create_dues(s1.id, year.id)
    assert len(dues) >= 2
    for d in dues:
        assert d.status == "unpaid"
        assert d.amount_paid == 0


@pytest.mark.asyncio
async def test_create_fee_dues_duplicate(seeded_env):
    svc = seeded_env["fee_due_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    await svc.create_dues(s1.id, year.id)
    with pytest.raises(ConflictError, match="already exists"):
        await svc.create_dues(s1.id, year.id)


@pytest.mark.asyncio
async def test_create_fee_dues_inactive_student(seeded_env):
    svc = seeded_env["fee_due_svc"]
    repo = seeded_env["student_repo"]
    s1 = seeded_env["s1"]
    s1.status = "inactive"
    await repo.update(s1)
    with pytest.raises(ValidationError, match="inactive student"):
        await svc.create_dues(s1.id, seeded_env["year"].id)


@pytest.mark.asyncio
async def test_create_fee_dues_not_enrolled(seeded_env):
    svc = seeded_env["fee_due_svc"]
    s3 = await seeded_env["student_repo"].create(
        Student(first_name="Not", last_name="Enrolled", student_number="FEE003", status="active")
    )
    with pytest.raises(ValidationError, match="not enrolled"):
        await svc.create_dues(s3.id, seeded_env["year"].id)


@pytest.mark.asyncio
async def test_get_fee_due(seeded_env):
    svc = seeded_env["fee_due_svc"]
    dues = await svc.create_dues(seeded_env["s1"].id, seeded_env["year"].id)
    due = await svc.get(dues[0].id)
    assert due.id == dues[0].id


@pytest.mark.asyncio
async def test_list_fee_dues(seeded_env):
    svc = seeded_env["fee_due_svc"]
    await svc.create_dues(seeded_env["s1"].id, seeded_env["year"].id)
    items, total = await svc.list()
    assert total >= 2


@pytest.mark.asyncio
async def test_get_student_dues(seeded_env):
    svc = seeded_env["fee_due_svc"]
    await svc.create_dues(seeded_env["s1"].id, seeded_env["year"].id)
    dues = await svc.get_student_dues(seeded_env["s1"].id)
    assert len(dues) >= 2


@pytest.mark.asyncio
async def test_get_student_fees(seeded_env):
    svc = seeded_env["fee_due_svc"]
    fees = await svc.get_student_fees(seeded_env["s1"].id, seeded_env["year"].id)
    assert len(fees) >= 2
    for f in fees:
        assert "fee_type_name" in f


# ---------------------------------------------------------------------------
# PaymentService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_payment_full(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    fee_due = dues[0]

    result = await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id,
            amount=fee_due.original_amount, receipt_number="RCP001",
        )
    )
    assert result["payment"].amount == fee_due.original_amount
    assert result["fee_due"]["status"] == "paid"
    assert result["fee_due"]["amount_paid"] == fee_due.original_amount


@pytest.mark.asyncio
async def test_record_payment_partial(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    fee_due = dues[0]

    result = await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id,
            amount=20000, receipt_number="RCP002",
        )
    )
    assert result["fee_due"]["status"] == "partially_paid"
    assert result["fee_due"]["amount_paid"] == 20000

    result2 = await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id,
            amount=30000, receipt_number="RCP003",
        )
    )
    assert result2["fee_due"]["status"] == "paid"
    assert result2["fee_due"]["amount_paid"] == 50000


@pytest.mark.asyncio
async def test_record_payment_overpayment(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    fee_due = dues[0]

    with pytest.raises(ValidationError, match="exceed outstanding"):
        await pmt_svc.record_payment(
            PaymentCreate(
                student_id=s1.id, fee_due_id=fee_due.id,
                amount=fee_due.original_amount + 1, receipt_number="RCP_OVER",
            )
        )


@pytest.mark.asyncio
async def test_record_payment_duplicate_receipt(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    fee_due = dues[0]

    await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id,
            amount=10000, receipt_number="RCP_DUP",
        )
    )
    with pytest.raises(ConflictError, match="already exists"):
        await pmt_svc.record_payment(
            PaymentCreate(
                student_id=s1.id, fee_due_id=fee_due.id,
                amount=5000, receipt_number="RCP_DUP",
            )
        )


@pytest.mark.asyncio
async def test_record_payment_invalid_fee_due(seeded_env):
    pmt_svc = seeded_env["payment_svc"]
    with pytest.raises(NotFoundError, match="not found"):
        await pmt_svc.record_payment(
            PaymentCreate(
                student_id=seeded_env["s1"].id, fee_due_id=999,
                amount=1000, receipt_number="RCP_INV",
            )
        )


@pytest.mark.asyncio
async def test_record_payment_wrong_student(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    s2 = seeded_env["s2"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    fee_due = dues[0]

    with pytest.raises(ValidationError, match="does not belong"):
        await pmt_svc.record_payment(
            PaymentCreate(
                student_id=s2.id, fee_due_id=fee_due.id,
                amount=1000, receipt_number="RCP_WRONG",
            )
        )


@pytest.mark.asyncio
async def test_record_payment_already_paid(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    fee_due = dues[0]

    await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=fee_due.id,
            amount=fee_due.original_amount, receipt_number="RCP_FULL",
        )
    )
    with pytest.raises(ConflictError, match="already fully paid"):
        await pmt_svc.record_payment(
            PaymentCreate(
                student_id=s1.id, fee_due_id=fee_due.id,
                amount=5000, receipt_number="RCP_EXTRA",
            )
        )


@pytest.mark.asyncio
async def test_get_payment(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    result = await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=dues[0].id,
            amount=25000, receipt_number="RCP_GET",
        )
    )
    payment = await pmt_svc.get_payment(result["payment"].id)
    assert payment.id == result["payment"].id


@pytest.mark.asyncio
async def test_get_student_payments(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=dues[0].id,
            amount=10000, receipt_number="RCP_SP1",
        )
    )
    payments = await pmt_svc.get_student_payments(s1.id)
    assert len(payments) >= 1


@pytest.mark.asyncio
async def test_get_fee_due_payments(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=dues[0].id,
            amount=10000, receipt_number="RCP_FDP",
        )
    )
    payments = await pmt_svc.get_fee_due_payments(dues[0].id)
    assert len(payments) >= 1


@pytest.mark.asyncio
async def test_get_payment_by_receipt_number(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)
    await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=dues[0].id,
            amount=10000, receipt_number="RCP_BYR",
        )
    )
    payment = await pmt_svc.get_payment_by_receipt_number("RCP_BYR")
    assert payment.receipt_number == "RCP_BYR"


@pytest.mark.asyncio
async def test_get_payment_by_receipt_number_not_found(seeded_env):
    pmt_svc = seeded_env["payment_svc"]
    with pytest.raises(NotFoundError, match="not found"):
        await pmt_svc.get_payment_by_receipt_number("NONEXISTENT")


# ---------------------------------------------------------------------------
# SummaryService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_summary(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    pmt_svc = seeded_env["payment_svc"]
    summary_svc = seeded_env["summary_svc"]
    s1 = seeded_env["s1"]
    year = seeded_env["year"]
    dues = await due_svc.create_dues(s1.id, year.id)

    summary = await summary_svc.get_student_summary(s1.id, year.id)
    assert summary["total_fees_assigned"] > 0
    assert summary["total_paid"] == 0
    assert summary["unpaid_count"] > 0

    await pmt_svc.record_payment(
        PaymentCreate(
            student_id=s1.id, fee_due_id=dues[0].id,
            amount=dues[0].original_amount, receipt_number="RCP_SUM1",
        )
    )
    summary2 = await summary_svc.get_student_summary(s1.id, year.id)
    assert summary2["total_paid"] > 0
    assert summary2["paid_count"] >= 1


@pytest.mark.asyncio
async def test_class_summary(seeded_env):
    due_svc = seeded_env["fee_due_svc"]
    summary_svc = seeded_env["summary_svc"]
    s1 = seeded_env["s1"]
    s2 = seeded_env["s2"]
    year = seeded_env["year"]
    cls = seeded_env["class"]
    await due_svc.create_dues(s1.id, year.id)
    await due_svc.create_dues(s2.id, year.id)

    summary = await summary_svc.get_class_summary(cls.id, year.id)
    assert summary["total_students"] == 2
    assert summary["total_fees_assigned"] > 0
    assert summary["students_with_outstanding"] == 2


@pytest.mark.asyncio
async def test_student_summary_no_dues(seeded_env):
    summary_svc = seeded_env["summary_svc"]
    s3 = await seeded_env["student_repo"].create(
        Student(first_name="No", last_name="Dues", student_number="FEE004", status="active")
    )
    summary = await summary_svc.get_student_summary(s3.id, seeded_env["year"].id)
    assert summary["total_fees_assigned"] == 0
    assert summary["total_paid"] == 0
    assert summary["total_outstanding"] == 0