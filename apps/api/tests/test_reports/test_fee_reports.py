from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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
from app.domains.reports.fee_reports import FeeReportService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_fees(db_session: AsyncSession):
    """Seed fee data for report testing."""
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())
    ft_repo = FeeTypeRepository(db_session, platform_context())
    fs_repo = FeeStructureRepository(db_session, platform_context())
    fd_repo = FeeDueRepository(db_session, platform_context())
    pmt_repo = PaymentRepository(db_session, platform_context())
    report_svc = FeeReportService(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Fee Report Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    cls2 = await class_repo.create(
        Class(name="Grade 11", academic_year_id=year.id, status="active")
    )
    s1 = await student_repo.create(
        Student(first_name="Alice", last_name="Smith", student_number="FR001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="FR002", status="active")
    )
    for s in [s1, s2]:
        await enrollment_repo.create(
            Enrollment(
                student_id=s.id, academic_year_id=year.id,
                class_id=cls.id, status="active",
            )
        )

    ft1 = await ft_repo.create(FeeType(name="Tuition"))
    ft2 = await ft_repo.create(FeeType(name="Library Fee"))

    fs1 = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                     fee_type_id=ft1.id, amount=50000, frequency="annual")
    )
    fs2 = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                     fee_type_id=ft2.id, amount=10000, frequency="annual")
    )

    now = datetime.datetime.now(timezone.utc)
    due1 = await fd_repo.create(
        FeeDue(student_id=s1.id, academic_year_id=year.id,
               fee_structure_id=fs1.id, original_amount=50000,
               amount_paid=25000, status="partially_paid",
               created_at=now, updated_at=now)
    )
    due2 = await fd_repo.create(
        FeeDue(student_id=s1.id, academic_year_id=year.id,
               fee_structure_id=fs2.id, original_amount=10000,
               amount_paid=0, status="unpaid",
               created_at=now, updated_at=now)
    )
    due3 = await fd_repo.create(
        FeeDue(student_id=s2.id, academic_year_id=year.id,
               fee_structure_id=fs1.id, original_amount=50000,
               amount_paid=50000, status="paid",
               created_at=now, updated_at=now)
    )

    await pmt_repo.create(
        Payment(student_id=s1.id, fee_due_id=due1.id, amount=25000,
                payment_date="2026-03-15", payment_method="cash",
                receipt_number="FR_RCP001", created_at=now)
    )
    await pmt_repo.create(
        Payment(student_id=s2.id, fee_due_id=due3.id, amount=50000,
                payment_date="2026-03-20", payment_method="bank_transfer",
                receipt_number="FR_RCP002", created_at=now)
    )

    return {
        "report_svc": report_svc,
        "year": year,
        "cls": cls,
        "cls2": cls2,
        "s1": s1,
        "s2": s2,
        "due1": due1,
        "due2": due2,
        "due3": due3,
    }


@pytest.mark.asyncio
async def test_collection_report(seeded_fees):
    svc = seeded_fees["report_svc"]
    year = seeded_fees["year"]

    report = await svc.get_collection_report(year.id)
    assert len(report) >= 1

    for r in report:
        if r["class_id"] == seeded_fees["cls"].id:
            assert r["total_students"] == 2
            assert r["total_fees_assigned"] > 0
            assert r["total_collected"] > 0
            break


@pytest.mark.asyncio
async def test_collection_report_with_date_range(seeded_fees):
    svc = seeded_fees["report_svc"]
    year = seeded_fees["year"]

    report = await svc.get_collection_report(
        year.id, start_date="2026-03-20", end_date="2026-03-20"
    )
    assert len(report) >= 1


@pytest.mark.asyncio
async def test_collection_report_empty(db_session: AsyncSession):
    svc = FeeReportService(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Empty Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )

    report = await svc.get_collection_report(year.id)
    assert report == []


@pytest.mark.asyncio
async def test_outstanding_report(seeded_fees):
    svc = seeded_fees["report_svc"]
    year = seeded_fees["year"]

    report = await svc.get_outstanding_report(year.id)
    assert len(report) > 0

    for r in report:
        if r["student_id"] == seeded_fees["s1"].id:
            assert r["outstanding"] > 0
            assert r["total_fees"] == 60000  # 50000 + 10000
            assert r["total_paid"] == 25000
            assert r["outstanding"] == 35000
            break


@pytest.mark.asyncio
async def test_outstanding_report_filtered_by_class(seeded_fees):
    svc = seeded_fees["report_svc"]
    year = seeded_fees["year"]
    cls = seeded_fees["cls"]

    report = await svc.get_outstanding_report(year.id, class_id=cls.id)
    assert len(report) > 0


@pytest.mark.asyncio
async def test_outstanding_report_sorts_by_outstanding_desc(seeded_fees):
    svc = seeded_fees["report_svc"]
    year = seeded_fees["year"]

    report = await svc.get_outstanding_report(year.id)
    if len(report) > 1:
        for i in range(len(report) - 1):
            assert report[i]["outstanding"] >= report[i + 1]["outstanding"]


@pytest.mark.asyncio
async def test_outstanding_report_fully_paid_excluded(seeded_fees):
    svc = seeded_fees["report_svc"]
    year = seeded_fees["year"]

    report = await svc.get_outstanding_report(year.id)
    for r in report:
        if r["student_id"] == seeded_fees["s2"].id:
            pytest.fail("Fully paid student should not appear in outstanding report")


@pytest.mark.asyncio
async def test_outstanding_report_empty(db_session: AsyncSession):
    svc = FeeReportService(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Empty Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )

    report = await svc.get_outstanding_report(year.id)
    assert report == []


@pytest.mark.asyncio
async def test_detailed_receipt(seeded_fees):
    svc = seeded_fees["report_svc"]
    from app.domains.fees.repository import PaymentRepository
    payments = await PaymentRepository(
        seeded_fees["report_svc"].session, platform_context()
    ).list(skip=0, limit=1)
    items, _ = payments
    if not items:
        pytest.skip("No payments available")
    payment = items[0]

    receipt = await svc.get_detailed_receipt(payment.id)
    assert receipt["payment_id"] == payment.id
    assert receipt["receipt_number"] is not None
    assert receipt["student_name"] is not None
    assert receipt["academic_year_name"] == "Fee Report Year"
    assert receipt["amount"] > 0


@pytest.mark.asyncio
async def test_detailed_receipt_not_found(seeded_fees):
    svc = seeded_fees["report_svc"]
    with pytest.raises(NotFoundError):
        await svc.get_detailed_receipt(99999)
