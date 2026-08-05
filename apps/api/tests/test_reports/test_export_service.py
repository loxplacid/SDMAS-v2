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
from app.domains.attendance.models import AttendanceRecord
from app.domains.attendance.repository import AttendanceRepository
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
    PaymentRepository,
)
from app.domains.reports.export_service import ExportService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_export(db_session: AsyncSession):
    """Seed data for export testing."""
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    section_repo = SectionRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())
    att_repo = AttendanceRepository(db_session, platform_context())
    ft_repo = FeeTypeRepository(db_session, platform_context())
    fs_repo = FeeStructureRepository(db_session, platform_context())
    fd_repo = FeeDueRepository(db_session, platform_context())
    pmt_repo = PaymentRepository(db_session, platform_context())
    export_svc = ExportService(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Export Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Section A", class_id=cls.id, status="active")
    )
    s1 = await student_repo.create(
        Student(first_name="Alice", last_name="Smith", student_number="EX001",
                email="alice@school.com", date_of_birth=datetime.date(2010, 5, 15),
                status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="EX002",
                status="inactive")
    )
    for s in [s1, s2]:
        await enrollment_repo.create(
            Enrollment(
                student_id=s.id, academic_year_id=year.id,
                class_id=cls.id, section_id=section.id, status="active",
            )
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    await att_repo.create(
        AttendanceRecord(
            student_id=s1.id, academic_year_id=year.id,
            class_id=cls.id, section_id=section.id,
            attendance_date="2026-03-15", status="present",
            notes="On time", recorded_at=now, updated_at=now,
        )
    )

    ft = await ft_repo.create(FeeType(name="Tuition"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                     fee_type_id=ft.id, amount=50000, frequency="annual")
    )
    due = await fd_repo.create(
        FeeDue(student_id=s1.id, academic_year_id=year.id,
               fee_structure_id=fs.id, original_amount=50000,
               amount_paid=0, status="unpaid",
               created_at=now, updated_at=now)
    )
    await pmt_repo.create(
        Payment(student_id=s1.id, fee_due_id=due.id, amount=25000,
                payment_date="2026-03-15", payment_method="cash",
                receipt_number="EX_RCP001", created_at=now)
    )

    return {
        "export_svc": export_svc,
        "s1": s1,
        "s2": s2,
        "year": year,
    }


@pytest.mark.asyncio
async def test_export_students_csv(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_students_csv()
    assert response.media_type == "text/csv"
    assert "attachment; filename=students.csv" in response.headers["content-disposition"]

    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "Student Number" in content
    assert "EX001" in content
    assert "EX002" in content
    assert "alice@school.com" in content


@pytest.mark.asyncio
async def test_export_students_csv_filtered_by_status(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_students_csv(status="active")
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "EX001" in content
    assert "EX002" not in content


@pytest.mark.asyncio
async def test_export_students_csv_no_sensitive_fields(seeded_export):
    """Verify no sensitive fields are exposed in student export."""
    svc = seeded_export["export_svc"]
    response = await svc.export_students_csv()
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "password" not in content.lower()
    assert "jwt" not in content.lower()
    assert "secret" not in content.lower()
    assert "token" not in content.lower()


@pytest.mark.asyncio
async def test_export_attendance_csv(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_attendance_csv()
    assert response.media_type == "text/csv"

    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "Student Number" in content
    assert "EX001" in content
    assert "On time" in content


@pytest.mark.asyncio
async def test_export_attendance_csv_empty(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_attendance_csv(
        start_date="2026-01-01", end_date="2026-01-01"
    )
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "Student Number" in content


@pytest.mark.asyncio
async def test_export_payments_csv(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_payments_csv()
    assert response.media_type == "text/csv"

    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "Receipt Number" in content
    assert "EX_RCP001" in content
    assert "25000" in content


@pytest.mark.asyncio
async def test_export_payments_csv_filtered_by_year(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_payments_csv(
        academic_year_id=seeded_export["year"].id
    )
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "EX_RCP001" in content


@pytest.mark.asyncio
async def test_export_payments_csv_filtered_by_date(seeded_export):
    svc = seeded_export["export_svc"]
    response = await svc.export_payments_csv(
        start_date="2026-03-15", end_date="2026-03-15"
    )
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "EX_RCP001" in content


@pytest.mark.asyncio
async def test_export_payments_csv_no_sensitive_fields(seeded_export):
    """Verify no sensitive fields are exposed in payment export."""
    svc = seeded_export["export_svc"]
    response = await svc.export_payments_csv()
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "password" not in content.lower()
    assert "jwt" not in content.lower()
    assert "secret" not in content.lower()
    assert "token" not in content.lower()


@pytest.mark.asyncio
async def test_export_attendance_csv_no_sensitive_fields(seeded_export):
    """Verify no sensitive fields are exposed in attendance export."""
    svc = seeded_export["export_svc"]
    response = await svc.export_attendance_csv()
    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "password" not in content.lower()
    assert "jwt" not in content.lower()
    assert "secret" not in content.lower()
    assert "token" not in content.lower()
