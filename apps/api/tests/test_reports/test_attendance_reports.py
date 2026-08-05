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
from app.domains.reports.attendance_reports import AttendanceReportService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_attendance(db_session: AsyncSession):
    """Seed attendance data for report testing."""
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    section_repo = SectionRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())
    att_repo = AttendanceRepository(db_session, platform_context())
    report_svc = AttendanceReportService(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Report Year",
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
        Student(first_name="Alice", last_name="Smith", student_number="RP001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="RP002", status="active")
    )
    s3 = await student_repo.create(
        Student(first_name="Carol", last_name="White", student_number="RP003", status="active")
    )
    s4 = await student_repo.create(
        Student(first_name="David", last_name="Black", student_number="RP004", status="active")
    )
    for s in [s1, s2, s3, s4]:
        await enrollment_repo.create(
            Enrollment(
                student_id=s.id, academic_year_id=year.id,
                class_id=cls.id, section_id=section.id, status="active",
            )
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    statuses = ["present", "absent", "late", "excused"]
    for sid, status in zip([s1.id, s2.id, s3.id, s4.id], statuses):
        await att_repo.create(
            AttendanceRecord(
                student_id=sid, academic_year_id=year.id,
                class_id=cls.id, section_id=section.id,
                attendance_date="2026-03-15", status=status,
                recorded_at=now, updated_at=now,
            )
        )
    await att_repo.create(
        AttendanceRecord(
            student_id=s1.id, academic_year_id=year.id,
            class_id=cls.id, section_id=section.id,
            attendance_date="2026-03-16", status="present",
            recorded_at=now, updated_at=now,
        )
    )
    await att_repo.create(
        AttendanceRecord(
            student_id=s2.id, academic_year_id=year.id,
            class_id=cls.id, section_id=section.id,
            attendance_date="2026-03-16", status="absent",
            recorded_at=now, updated_at=now,
        )
    )

    return {
        "report_svc": report_svc,
        "year": year,
        "class": cls,
        "section": section,
        "s1": s1,
        "s2": s2,
        "s3": s3,
        "s4": s4,
    }


@pytest.mark.asyncio
async def test_class_attendance_summary(seeded_attendance):
    svc = seeded_attendance["report_svc"]
    cls = seeded_attendance["class"]
    year = seeded_attendance["year"]

    report = await svc.get_class_attendance_summary(cls.id, year.id)
    assert report["class_id"] == cls.id
    assert report["class_name"] == "Grade 10"
    assert report["total_students"] == 4
    assert report["total_records"] == 6
    assert report["present"] == 2
    assert report["absent"] == 2
    assert report["late"] == 1
    assert report["excused"] == 1
    assert report["present_percentage"] == pytest.approx(33.33, rel=0.01)


@pytest.mark.asyncio
async def test_class_attendance_summary_with_date_range(seeded_attendance):
    svc = seeded_attendance["report_svc"]
    cls = seeded_attendance["class"]
    year = seeded_attendance["year"]

    report = await svc.get_class_attendance_summary(
        cls.id, year.id, start_date="2026-03-15", end_date="2026-03-15"
    )
    assert report["total_records"] == 4
    assert report["present"] == 1
    assert report["absent"] == 1
    assert report["late"] == 1
    assert report["excused"] == 1


@pytest.mark.asyncio
async def test_class_attendance_summary_empty_results(db_session: AsyncSession):
    svc = AttendanceReportService(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Empty Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Empty Class", academic_year_id=year.id, status="active")
    )

    report = await svc.get_class_attendance_summary(cls.id, year.id)
    assert report["total_records"] == 0
    assert report["present_percentage"] == 0.0


@pytest.mark.asyncio
async def test_section_attendance_summary(seeded_attendance):
    svc = seeded_attendance["report_svc"]
    section = seeded_attendance["section"]

    report = await svc.get_section_attendance_summary(section.id)
    assert report["section_id"] == section.id
    assert report["section_name"] == "Section A"
    assert report["class_name"] == "Grade 10"
    assert report["total_records"] == 6
    assert report["present"] == 2


@pytest.mark.asyncio
async def test_section_attendance_summary_with_date_range(seeded_attendance):
    svc = seeded_attendance["report_svc"]
    section = seeded_attendance["section"]

    report = await svc.get_section_attendance_summary(
        section.id, start_date="2026-03-16", end_date="2026-03-16"
    )
    assert report["total_records"] == 2
    assert report["present"] == 1


@pytest.mark.asyncio
async def test_section_attendance_summary_empty(db_session: AsyncSession):
    svc = AttendanceReportService(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    section_repo = SectionRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Empty Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Empty Class", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Empty Section", class_id=cls.id, status="active")
    )

    report = await svc.get_section_attendance_summary(section.id)
    assert report["total_records"] == 0


@pytest.mark.asyncio
async def test_attendance_overview(seeded_attendance):
    svc = seeded_attendance["report_svc"]
    year = seeded_attendance["year"]

    report = await svc.get_attendance_overview(year.id)
    assert report["academic_year_id"] == year.id
    assert report["total_classes"] >= 1
    assert report["total_sections"] >= 1
    assert report["total_students"] == 4
    assert report["total_records"] == 6
    assert report["present"] == 2
    assert report["overall_present_percentage"] == pytest.approx(33.33, rel=0.01)


@pytest.mark.asyncio
async def test_attendance_overview_empty(db_session: AsyncSession):
    svc = AttendanceReportService(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Empty Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )

    report = await svc.get_attendance_overview(year.id)
    assert report["total_records"] == 0
    assert report["overall_present_percentage"] == 0.0
