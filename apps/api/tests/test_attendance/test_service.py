from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.attendance.repository import AttendanceRepository
from app.domains.attendance.schemas import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
)
from app.domains.attendance.service import AttendanceService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_env(db_session: AsyncSession):
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    section_repo = SectionRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())
    att_repo = AttendanceRepository(db_session, platform_context())

    service = AttendanceService(
        att_repo,
        student_repo,
        year_repo,
        class_repo,
        section_repo,
        platform_context(),
    )

    year = await year_repo.create(
        AcademicYear(
            name="SVC Year", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31), status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Section A", class_id=cls.id, status="active")
    )
    s1 = await student_repo.create(
        Student(first_name="Alice", last_name="Smith", student_number="AT001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="AT002", status="active")
    )
    await enrollment_repo.create(
        Enrollment(student_id=s1.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active")
    )
    await enrollment_repo.create(
        Enrollment(student_id=s2.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active")
    )

    return {
        "service": service,
        "year": year,
        "class": cls,
        "section": section,
        "s1": s1,
        "s2": s2,
        "student_repo": student_repo,
    }


@pytest.mark.asyncio
async def test_create_success(seeded_env):
    service = seeded_env["service"]
    record = await service.record_attendance(
        AttendanceRecordCreate(
            student_id=seeded_env["s1"].id,
            academic_year_id=seeded_env["year"].id,
            class_id=seeded_env["class"].id,
            section_id=seeded_env["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
    )
    assert record.id is not None
    assert record.status == "active" or record.status == "present"


@pytest.mark.asyncio
async def test_get_success(seeded_env):
    service = seeded_env["service"]
    created = await service.record_attendance(
        AttendanceRecordCreate(
            student_id=seeded_env["s1"].id,
            academic_year_id=seeded_env["year"].id,
            class_id=seeded_env["class"].id,
            section_id=seeded_env["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
    )
    retrieved = await service.get_attendance(created.id)
    assert retrieved.id == created.id


@pytest.mark.asyncio
async def test_get_not_found(seeded_env):
    service = seeded_env["service"]
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_attendance(99999)


@pytest.mark.asyncio
async def test_update_success(seeded_env):
    service = seeded_env["service"]
    created = await service.record_attendance(
        AttendanceRecordCreate(
            student_id=seeded_env["s1"].id,
            academic_year_id=seeded_env["year"].id,
            class_id=seeded_env["class"].id,
            section_id=seeded_env["section"].id,
            attendance_date="2026-03-15",
            status="absent",
        )
    )
    updated = await service.update_attendance(
        created.id, AttendanceRecordUpdate(status="present")
    )
    assert updated.status == "present"


@pytest.mark.asyncio
async def test_list_empty(seeded_env):
    service = seeded_env["service"]
    records, total = await service.get_student_attendance(seeded_env["s1"].id)
    assert total == 0
    assert len(records) == 0


@pytest.mark.asyncio
async def test_student_summary_edge_cases(seeded_env):
    service = seeded_env["service"]
    summary = await service.get_student_summary(
        seeded_env["s1"].id, "2026-03-15", "2026-03-17"
    )
    assert summary["total"] == 0
    assert summary["percentage"] == 0.0


@pytest.mark.asyncio
async def test_section_summary_no_enrollments(seeded_env, db_session: AsyncSession):
    service = seeded_env["service"]
    section_repo = SectionRepository(db_session, platform_context())
    empty_section = await section_repo.create(
        Section(name="Empty Section", class_id=seeded_env["class"].id, status="active")
    )
    summary = await service.get_section_summary(empty_section.id, "2026-03-15")
    assert summary["total_students"] == 0
    assert summary["total_marked"] == 0
    assert summary["present_percentage"] == 0.0


@pytest.mark.asyncio
async def test_record_attendance_duplicate(seeded_env):
    service = seeded_env["service"]
    data = AttendanceRecordCreate(
        student_id=seeded_env["s1"].id,
        academic_year_id=seeded_env["year"].id,
        class_id=seeded_env["class"].id,
        section_id=seeded_env["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await service.record_attendance(data)
    with pytest.raises(ConflictError, match="already exists"):
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_update_not_found(seeded_env):
    service = seeded_env["service"]
    with pytest.raises(NotFoundError, match="not found"):
        await service.update_attendance(99999, AttendanceRecordUpdate(status="present"))