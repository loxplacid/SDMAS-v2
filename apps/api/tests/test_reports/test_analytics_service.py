from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.analytics.service import AnalyticsService
from app.domains.attendance.models import AttendanceRecord
from app.domains.attendance.repository import AttendanceRepository
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
    PaymentRepository,
)
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository


@pytest.fixture
async def seeded_analytics(db_session: AsyncSession):
    """Seed comprehensive data for analytics testing."""
    sr = StudentRepository(db_session)
    yr = AcademicYearRepository(db_session)
    cr = ClassRepository(db_session)
    secr = SectionRepository(db_session)
    er = EnrollmentRepository(db_session)
    ar = AttendanceRepository(db_session)
    ftr = FeeTypeRepository(db_session)
    fsr = FeeStructureRepository(db_session)
    fdr = FeeDueRepository(db_session)
    pmtr = PaymentRepository(db_session)
    svc = AnalyticsService(db_session)

    year = await yr.create(
        AcademicYear(name="Analytics Year", start_date=datetime.date(2026, 1, 1),
                     end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await cr.create(Class(name="Grade 10", academic_year_id=year.id, status="active"))
    sec = await secr.create(Section(name="Section A", class_id=cls.id, status="active"))

    s1 = await sr.create(Student(first_name="Alice", last_name="Smith", student_number="AN001", status="active"))
    s2 = await sr.create(Student(first_name="Bob", last_name="Jones", student_number="AN002", status="active"))
    s3 = await sr.create(Student(first_name="Inactive", last_name="User", student_number="AN003", status="inactive"))

    now = datetime.datetime.now(datetime.timezone.utc)
    for s in [s1, s2]:
        await er.create(Enrollment(student_id=s.id, academic_year_id=year.id, class_id=cls.id,
                                    section_id=sec.id, status="active", enrolled_at=now,
                                    created_at=now, updated_at=now))

    # Attendance: s1 present 4/5, s2 present 2/5 (40% - low attendance)
    for sid, statuses in [(s1.id, ["present", "present", "present", "present", "absent"]),
                           (s2.id, ["present", "present", "absent", "absent", "absent"])]:
        for i, st in enumerate(statuses):
            await ar.create(AttendanceRecord(
                student_id=sid, academic_year_id=year.id, class_id=cls.id,
                section_id=sec.id, attendance_date=f"2026-03-{15+i:02d}",
                status=st, recorded_at=now, updated_at=now))

    # Fee structures and dues
    ft = await ftr.create(FeeType(name="Tuition"))
    fs = await fsr.create(FeeStructure(academic_year_id=year.id, class_id=cls.id,
                                        fee_type_id=ft.id, amount=50000, frequency="annual"))
    due1 = await fdr.create(FeeDue(student_id=s1.id, academic_year_id=year.id,
                                    fee_structure_id=fs.id, original_amount=50000,
                                    amount_paid=50000, status="paid", created_at=now, updated_at=now))
    due2 = await fdr.create(FeeDue(student_id=s2.id, academic_year_id=year.id,
                                    fee_structure_id=fs.id, original_amount=50000,
                                    amount_paid=10000, status="partially_paid",
                                    created_at=now, updated_at=now))

    await pmtr.create(Payment(student_id=s1.id, fee_due_id=due1.id, amount=50000,
                               payment_date="2026-03-20", payment_method="cash",
                               receipt_number="AN_RCP01", created_at=now))

    return {"svc": svc, "year": year, "cls": cls, "sec": sec, "s1": s1, "s2": s2, "s3": s3}


@pytest.mark.asyncio
async def test_overview_metrics(seeded_analytics):
    svc = seeded_analytics["svc"]
    ov = await svc.get_overview()
    assert ov["total_students"] == 3
    assert ov["active_students"] == 2
    assert ov["inactive_students"] == 1
    assert ov["current_academic_year"] == "Analytics Year"
    assert ov["total_classes"] >= 1
    assert ov["total_sections"] >= 1
    # total_collected = sum(FeeDue.amount_paid) = 50000 + 10000 = 60000
    assert ov["total_collected"] == 60000
    assert ov["total_outstanding"] == 40000


@pytest.mark.asyncio
async def test_attendance_overview(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    ao = await svc.get_attendance_overview(academic_year_id=year.id)
    assert ao["total_records"] == 10
    assert ao["present"] == 6
    assert ao["absent"] == 4
    assert ao["late"] == 0
    assert ao["excused"] == 0
    assert ao["attendance_percentage"] == 60.0


@pytest.mark.asyncio
async def test_attendance_overview_filtered(seeded_analytics):
    svc = seeded_analytics["svc"]
    cls = seeded_analytics["cls"]
    ao = await svc.get_attendance_overview(class_id=cls.id)
    assert ao["total_records"] == 10
    assert ao["present"] == 6


@pytest.mark.asyncio
async def test_attendance_trends(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    tr = await svc.get_attendance_trends(academic_year_id=year.id, granularity="daily")
    assert len(tr["trend"]) == 5
    assert tr["granularity"] == "daily"
    assert tr["trend"][0]["present"] == 2
    assert tr["trend"][0]["total"] == 2


@pytest.mark.asyncio
async def test_attendance_trends_monthly(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    tr = await svc.get_attendance_trends(academic_year_id=year.id, granularity="monthly")
    assert len(tr["trend"]) == 1
    assert tr["granularity"] == "monthly"


@pytest.mark.asyncio
async def test_attendance_class_comparison(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    cc = await svc.get_attendance_class_comparison(academic_year_id=year.id)
    assert len(cc) >= 1
    assert cc[0]["class_name"] == "Grade 10"
    assert cc[0]["attendance_percentage"] == 60.0


@pytest.mark.asyncio
async def test_low_attendance_students(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    low = await svc.get_low_attendance_students(threshold=90, academic_year_id=year.id)
    assert len(low) == 2  # Both s1 (80%) and s2 (40%) below 90%
    assert low[0]["attendance_percentage"] == 40.0  # s2 sorted first (lowest)
    assert low[1]["attendance_percentage"] == 80.0  # s1 also below 90%


@pytest.mark.asyncio
async def test_low_attendance_threshold_75(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    low = await svc.get_low_attendance_students(threshold=75, academic_year_id=year.id)
    assert len(low) == 1  # only s2 below 75%
    assert low[0]["attendance_percentage"] == 40.0


@pytest.mark.asyncio
async def test_low_attendance_threshold_30(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    low = await svc.get_low_attendance_students(threshold=30, academic_year_id=year.id)
    assert len(low) == 0  # No one below 30%


@pytest.mark.asyncio
async def test_finance_overview(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    fo = await svc.get_finance_overview(academic_year_id=year.id)
    assert fo["total_fees_amount"] == 100000
    assert fo["total_collected"] == 60000  # 50000 from due1 + 10000 from due2
    assert fo["total_outstanding"] == 40000
    assert fo["collection_percentage"] == 60.0
    assert fo["fully_paid_students"] == 1
    assert fo["partially_paid_students"] == 1
    assert fo["unpaid_students"] == 0  # No unpaid dues


@pytest.mark.asyncio
async def test_finance_overview_integer_monetary(seeded_analytics):
    """Verify all monetary values are integers (minor units)."""
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    fo = await svc.get_finance_overview(academic_year_id=year.id)
    assert isinstance(fo["total_fees_amount"], int)
    assert isinstance(fo["total_collected"], int)
    assert isinstance(fo["total_outstanding"], int)


@pytest.mark.asyncio
async def test_fee_type_collection(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    ftc = await svc.get_fee_type_collection(academic_year_id=year.id)
    assert len(ftc) >= 1
    assert ftc[0]["fee_type_name"] == "Tuition"
    assert ftc[0]["total_expected"] == 100000
    assert ftc[0]["total_collected"] == 60000  # 50000 due1 + 10000 due2
    assert ftc[0]["collection_percentage"] == 60.0


@pytest.mark.asyncio
async def test_collection_trends(seeded_analytics):
    svc = seeded_analytics["svc"]
    ct = await svc.get_collection_trends(granularity="daily")
    assert len(ct["trend"]) >= 1
    assert ct["trend"][0]["amount"] == 50000
    assert ct["trend"][0]["count"] == 1


@pytest.mark.asyncio
async def test_payment_method_distribution(seeded_analytics):
    svc = seeded_analytics["svc"]
    pm = await svc.get_payment_method_distribution()
    assert len(pm) >= 1
    assert pm[0]["payment_method"] == "cash"
    assert pm[0]["transaction_count"] == 1
    assert pm[0]["total_amount"] == 50000


@pytest.mark.asyncio
async def test_fee_status_distribution(seeded_analytics):
    svc = seeded_analytics["svc"]
    year = seeded_analytics["year"]
    sd = await svc.get_fee_status_distribution(academic_year_id=year.id)
    status_map = {s["status"]: s for s in sd}
    assert status_map["paid"]["count"] == 1
    assert status_map["partially_paid"]["count"] == 1


@pytest.mark.asyncio
async def test_student_overview(seeded_analytics):
    svc = seeded_analytics["svc"]
    so = await svc.get_student_overview()
    assert so["total_students"] == 3
    assert so["active_students"] == 2
    assert so["inactive_students"] == 1


@pytest.mark.asyncio
async def test_students_by_class(seeded_analytics):
    svc = seeded_analytics["svc"]
    bc = await svc.get_students_by_class()
    assert len(bc) >= 1
    assert bc[0]["student_count"] == 2


@pytest.mark.asyncio
async def test_students_by_section(seeded_analytics):
    svc = seeded_analytics["svc"]
    bs = await svc.get_students_by_section()
    assert len(bs) >= 1
    assert bs[0]["student_count"] == 2


@pytest.mark.asyncio
async def test_academic_overview(seeded_analytics):
    svc = seeded_analytics["svc"]
    ao = await svc.get_academic_overview()
    assert ao["active_academic_year"] == "Analytics Year"
    assert ao["total_classes"] >= 1
    assert ao["total_sections"] >= 1


@pytest.mark.asyncio
async def test_empty_datasets(db_session: AsyncSession):
    """Test analytics with empty database returns zeros not errors."""
    svc = AnalyticsService(db_session)
    ov = await svc.get_overview()
    assert ov["total_students"] == 0
    assert ov["overall_attendance_percentage"] == 0.0
    assert ov["total_collected"] == 0

    att = await svc.get_attendance_overview()
    assert att["total_records"] == 0
    assert att["attendance_percentage"] == 0.0

    tr = await svc.get_attendance_trends()
    assert tr["trend"] == []
    assert tr["granularity"] == "daily"

    cc = await svc.get_attendance_class_comparison()
    assert cc == []

    low = await svc.get_low_attendance_students()
    assert low == []

    fo = await svc.get_finance_overview()
    assert fo["total_fees_amount"] == 0
    assert fo["total_collected"] == 0
    assert fo["collection_percentage"] == 0.0

    pm = await svc.get_payment_method_distribution()
    assert pm == []

    sd = await svc.get_fee_status_distribution()
    assert sd == []

    so = await svc.get_student_overview()
    assert so["total_students"] == 0
    assert so["active_students"] == 0

    bc = await svc.get_students_by_class()
    assert bc == []

    ao = await svc.get_academic_overview()
    assert ao["active_academic_year"] is None


@pytest.mark.asyncio
async def test_term_attendance_not_found(db_session: AsyncSession):
    svc = AnalyticsService(db_session)
    result = await svc.get_term_attendance(99999)
    assert result is None


@pytest.mark.asyncio
async def test_all_term_attendance_empty(db_session: AsyncSession):
    svc = AnalyticsService(db_session)
    result = await svc.get_all_term_attendance()
    assert result == []


@pytest.mark.asyncio
async def test_enrollment_trends(db_session: AsyncSession):
    svc = AnalyticsService(db_session)
    et = await svc.get_enrollment_trends()
    assert et == []


@pytest.mark.asyncio
async def test_teacher_workload_empty(db_session: AsyncSession):
    svc = AnalyticsService(db_session)
    tw = await svc.get_teacher_workload()
    assert tw == []


@pytest.mark.asyncio
async def test_subject_distribution_empty(db_session: AsyncSession):
    svc = AnalyticsService(db_session)
    sd = await svc.get_subject_distribution()
    assert sd == []
