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
from app.domains.attendance.models import AttendanceRecord
from app.domains.attendance.repository import AttendanceRepository
from app.domains.attendance.schemas import (
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    DailyAttendanceCreate,
    DailyAttendanceItem,
)
from app.domains.attendance.service import AttendanceService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


@pytest.fixture
def student_repo(db_session: AsyncSession) -> StudentRepository:
    return StudentRepository(db_session, platform_context())


@pytest.fixture
def year_repo(db_session: AsyncSession) -> AcademicYearRepository:
    return AcademicYearRepository(db_session, platform_context())


@pytest.fixture
def class_repo(db_session: AsyncSession) -> ClassRepository:
    return ClassRepository(db_session, platform_context())


@pytest.fixture
def section_repo(db_session: AsyncSession) -> SectionRepository:
    return SectionRepository(db_session, platform_context())


@pytest.fixture
def enrollment_repo(db_session: AsyncSession) -> EnrollmentRepository:
    return EnrollmentRepository(db_session, platform_context())


@pytest.fixture
def att_repo(db_session: AsyncSession) -> AttendanceRepository:
    return AttendanceRepository(db_session, platform_context())


@pytest.fixture
def service(
    att_repo: AttendanceRepository,
    student_repo: StudentRepository,
    year_repo: AcademicYearRepository,
    class_repo: ClassRepository,
    section_repo: SectionRepository,
) -> AttendanceService:
    return AttendanceService(
        att_repo, student_repo, year_repo, class_repo, section_repo,
        platform_context(),
    )


@pytest.fixture
async def seed_data(
    db_session: AsyncSession,
    student_repo: StudentRepository,
    year_repo: AcademicYearRepository,
    class_repo: ClassRepository,
    section_repo: SectionRepository,
    enrollment_repo: EnrollmentRepository,
):
    year = await year_repo.create(
        AcademicYear(
            name="2026-2027",
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
        Student(
            first_name="John",
            last_name="Doe",
            student_number="STU001",
            status="active",
        )
    )
    s2 = await student_repo.create(
        Student(
            first_name="Jane",
            last_name="Smith",
            student_number="STU002",
            status="active",
        )
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=s1.id,
            academic_year_id=year.id,
            class_id=cls.id,
            section_id=section.id,
            status="active",
        )
    )
    await enrollment_repo.create(
        Enrollment(
            student_id=s2.id,
            academic_year_id=year.id,
            class_id=cls.id,
            section_id=section.id,
            status="active",
        )
    )
    return {"year": year, "class": cls, "section": section, "s1": s1, "s2": s2}


# ---------------------------------------------------------------------------
# RECORD single attendance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_present(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    record = await service.record_attendance(data)
    assert record.id is not None
    assert record.student_id == seed_data["s1"].id
    assert record.status == "present"
    assert record.attendance_date == "2026-03-15"
    assert record.recorded_at is not None
    assert record.updated_at is not None


@pytest.mark.asyncio
async def test_record_absent(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
    )
    record = await service.record_attendance(data)
    assert record.status == "absent"


@pytest.mark.asyncio
async def test_record_late(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="late",
    )
    record = await service.record_attendance(data)
    assert record.status == "late"


@pytest.mark.asyncio
async def test_record_excused(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="excused",
    )
    record = await service.record_attendance(data)
    assert record.status == "excused"


def test_record_invalid_status_schema():
    with pytest.raises(ValueError, match="Invalid attendance status"):
        AttendanceRecordCreate(
            student_id=1,
            academic_year_id=1,
            class_id=1,
            section_id=1,
            attendance_date="2026-03-15",
            status="invalid",
        )


@pytest.mark.asyncio
async def test_record_student_not_found(service: AttendanceService, seed_data):
    with pytest.raises(NotFoundError, match="not found"):
        data = AttendanceRecordCreate(
            student_id=999,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_record_inactive_student(
    service: AttendanceService,
    seed_data,
    student_repo: StudentRepository,
):
    s = seed_data["s1"]
    s.status = "inactive"
    await student_repo.update(s)

    with pytest.raises(ValidationError, match="inactive student"):
        data = AttendanceRecordCreate(
            student_id=s.id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_record_academic_year_not_found(service: AttendanceService, seed_data):
    with pytest.raises(NotFoundError, match="not found"):
        data = AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=999,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_record_class_not_found(service: AttendanceService, seed_data):
    with pytest.raises(NotFoundError, match="not found"):
        data = AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=999,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_record_section_not_found(service: AttendanceService, seed_data):
    with pytest.raises(NotFoundError, match="not found"):
        data = AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=999,
            attendance_date="2026-03-15",
            status="present",
        )
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_record_student_not_enrolled(
    service: AttendanceService,
    seed_data,
    section_repo: SectionRepository,
):
    other_section = await section_repo.create(
        Section(name="Section B", class_id=seed_data["class"].id, status="active")
    )
    with pytest.raises(ValidationError, match="not enrolled"):
        data = AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=other_section.id,
            attendance_date="2026-03-15",
            status="present",
        )
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_record_with_notes(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
        notes="Sick leave",
    )
    record = await service.record_attendance(data)
    assert record.notes == "Sick leave"


@pytest.mark.asyncio
async def test_record_notes_null_when_not_provided(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    record = await service.record_attendance(data)
    assert record.notes is None


# ---------------------------------------------------------------------------
# DUPLICATE PROTECTION
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_rejected(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await service.record_attendance(data)
    with pytest.raises(ConflictError, match="already exists"):
        await service.record_attendance(data)


@pytest.mark.asyncio
async def test_duplicate_different_date_allowed(service: AttendanceService, seed_data):
    data1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await service.record_attendance(data1)
    data2 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-16",
        status="absent",
    )
    record = await service.record_attendance(data2)
    assert record.status == "absent"
    assert record.attendance_date == "2026-03-16"


@pytest.mark.asyncio
async def test_duplicate_different_student_allowed(service: AttendanceService, seed_data):
    data1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await service.record_attendance(data1)
    data2 = AttendanceRecordCreate(
        student_id=seed_data["s2"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
    )
    record = await service.record_attendance(data2)
    assert record.status == "absent"


# ---------------------------------------------------------------------------
# GET SINGLE RECORD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_attendance_by_id(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    created = await service.record_attendance(data)
    found = await service.get_attendance(created.id)
    assert found.id == created.id
    assert found.status == "present"


@pytest.mark.asyncio
async def test_get_attendance_not_found(service: AttendanceService, seed_data):
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_attendance(999)


# ---------------------------------------------------------------------------
# UPDATE ATTENDANCE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
    )
    created = await service.record_attendance(data)
    updated = await service.update_attendance(
        created.id, AttendanceRecordUpdate(status="present")
    )
    assert updated.status == "present"


@pytest.mark.asyncio
async def test_update_notes(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
        notes="Original note",
    )
    created = await service.record_attendance(data)
    updated = await service.update_attendance(
        created.id,
        AttendanceRecordUpdate(status="present", notes="Corrected - was present"),
    )
    assert updated.status == "present"
    assert updated.notes == "Corrected - was present"


@pytest.mark.asyncio
async def test_update_not_found(service: AttendanceService, seed_data):
    with pytest.raises(NotFoundError, match="not found"):
        await service.update_attendance(999, AttendanceRecordUpdate(status="present"))


def test_update_invalid_status_schema():
    with pytest.raises(ValueError, match="Invalid attendance status"):
        AttendanceRecordUpdate(status="invalid")


@pytest.mark.asyncio
async def test_update_updated_at_changes(service: AttendanceService, seed_data):
    data = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    created = await service.record_attendance(data)
    original_updated = created.updated_at

    import asyncio
    await asyncio.sleep(0.01)

    updated = await service.update_attendance(
        created.id, AttendanceRecordUpdate(status="absent")
    )
    assert updated.updated_at != original_updated


# ---------------------------------------------------------------------------
# GET STUDENT ATTENDANCE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_student_attendance(service: AttendanceService, seed_data):
    d1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    d2 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-16",
        status="absent",
    )
    await service.record_attendance(d1)
    await service.record_attendance(d2)

    records, total = await service.get_student_attendance(seed_data["s1"].id)
    assert total == 2
    assert len(records) == 2


@pytest.mark.asyncio
async def test_get_student_attendance_filter_by_status(service: AttendanceService, seed_data):
    d1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    d2 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-16",
        status="absent",
    )
    await service.record_attendance(d1)
    await service.record_attendance(d2)

    records, total = await service.get_student_attendance(
        seed_data["s1"].id, status="present"
    )
    assert total == 1
    assert records[0].status == "present"


@pytest.mark.asyncio
async def test_get_student_attendance_empty(service: AttendanceService, seed_data):
    records, total = await service.get_student_attendance(seed_data["s1"].id)
    assert total == 0
    assert len(records) == 0


@pytest.mark.asyncio
async def test_get_student_attendance_invalid_status_filter(service: AttendanceService, seed_data):
    with pytest.raises(ValidationError, match="Invalid attendance status filter"):
        await service.get_student_attendance(seed_data["s1"].id, status="invalid")


# ---------------------------------------------------------------------------
# GET SECTION ATTENDANCE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_section_attendance(service: AttendanceService, seed_data):
    d1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    d2 = AttendanceRecordCreate(
        student_id=seed_data["s2"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
    )
    await service.record_attendance(d1)
    await service.record_attendance(d2)

    records = await service.get_section_attendance(
        seed_data["section"].id, "2026-03-15"
    )
    assert len(records) == 2


@pytest.mark.asyncio
async def test_get_section_attendance_empty(service: AttendanceService, seed_data):
    records = await service.get_section_attendance(
        seed_data["section"].id, "2026-03-15"
    )
    assert len(records) == 0


# ---------------------------------------------------------------------------
# RECORD DAILY ATTENDANCE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_daily_attendance(service: AttendanceService, seed_data):
    data = DailyAttendanceCreate(
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        records=[
            DailyAttendanceItem(student_id=seed_data["s1"].id, status="present"),
            DailyAttendanceItem(student_id=seed_data["s2"].id, status="absent"),
        ],
    )
    records = await service.record_daily_attendance(data)
    assert len(records) == 2
    assert records[0].status == "present"
    assert records[1].status == "absent"
    assert records[0].attendance_date == "2026-03-15"
    assert records[1].attendance_date == "2026-03-15"


def test_record_daily_attendance_empty_records_schema():
    with pytest.raises(ValueError, match="non-empty"):
        DailyAttendanceCreate(
            section_id=1,
            attendance_date="2026-03-15",
            records=[],
        )


# ---------------------------------------------------------------------------
# STUDENT SUMMARY
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_summary(service: AttendanceService, seed_data):
    dates_statuses = [
        ("2026-03-15", "present"),
        ("2026-03-16", "present"),
        ("2026-03-17", "absent"),
        ("2026-03-18", "late"),
        ("2026-03-19", "excused"),
    ]
    for date, status in dates_statuses:
        await service.record_attendance(
            AttendanceRecordCreate(
                student_id=seed_data["s1"].id,
                academic_year_id=seed_data["year"].id,
                class_id=seed_data["class"].id,
                section_id=seed_data["section"].id,
                attendance_date=date,
                status=status,
            )
        )

    summary = await service.get_student_summary(
        seed_data["s1"].id, "2026-03-15", "2026-03-19"
    )
    assert summary["total"] == 5
    assert summary["present"] == 2
    assert summary["absent"] == 1
    assert summary["late"] == 1
    assert summary["excused"] == 1


@pytest.mark.asyncio
async def test_student_summary_percentage(service: AttendanceService, seed_data):
    await service.record_attendance(
        AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-15",
            status="present",
        )
    )
    await service.record_attendance(
        AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-16",
            status="present",
        )
    )
    await service.record_attendance(
        AttendanceRecordCreate(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date="2026-03-17",
            status="absent",
        )
    )

    summary = await service.get_student_summary(
        seed_data["s1"].id, "2026-03-15", "2026-03-17"
    )
    assert summary["total"] == 3
    assert summary["present"] == 2
    assert summary["percentage"] == 66.67


@pytest.mark.asyncio
async def test_student_summary_zero_when_no_records(service: AttendanceService, seed_data):
    summary = await service.get_student_summary(
        seed_data["s1"].id, "2026-03-15", "2026-03-17"
    )
    assert summary["total"] == 0
    assert summary["present"] == 0
    assert summary["percentage"] == 0.0


# ---------------------------------------------------------------------------
# SECTION SUMMARY
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_section_summary(service: AttendanceService, seed_data):
    d1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    d2 = AttendanceRecordCreate(
        student_id=seed_data["s2"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="absent",
    )
    await service.record_attendance(d1)
    await service.record_attendance(d2)

    summary = await service.get_section_summary(seed_data["section"].id, "2026-03-15")
    assert summary["total_students"] == 2
    assert summary["present"] == 1
    assert summary["absent"] == 1
    assert summary["total_marked"] == 2


@pytest.mark.asyncio
async def test_section_summary_no_records(service: AttendanceService, seed_data):
    summary = await service.get_section_summary(seed_data["section"].id, "2026-03-15")
    assert summary["total_students"] == 2
    assert summary["present"] == 0
    assert summary["absent"] == 0
    assert summary["total_marked"] == 0
    assert summary["present_percentage"] == 0.0


@pytest.mark.asyncio
async def test_section_summary_hundred_percent(service: AttendanceService, seed_data):
    d1 = AttendanceRecordCreate(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    d2 = AttendanceRecordCreate(
        student_id=seed_data["s2"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await service.record_attendance(d1)
    await service.record_attendance(d2)

    summary = await service.get_section_summary(seed_data["section"].id, "2026-03-15")
    assert summary["present"] == 2
    assert summary["present_percentage"] == 100


# ---------------------------------------------------------------------------
# REPOSITORY DIRECT TESTS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_get_by_id_not_found(att_repo: AttendanceRepository):
    with pytest.raises(NotFoundError, match="not found"):
        await att_repo.get_by_id(999)


@pytest.mark.asyncio
async def test_repo_find_duplicate(
    att_repo: AttendanceRepository,
    seed_data,
):
    record = AttendanceRecord(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await att_repo.create(record)

    found = await att_repo.find_duplicate(
        seed_data["s1"].id, "2026-03-15", seed_data["section"].id
    )
    assert found is not None
    assert found.id == record.id

    not_found = await att_repo.find_duplicate(
        seed_data["s1"].id, "2026-03-16", seed_data["section"].id
    )
    assert not_found is None


@pytest.mark.asyncio
async def test_repo_list_pagination(att_repo: AttendanceRepository, seed_data):
    for i in range(5):
        r = AttendanceRecord(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date=f"2026-03-{15+i:02d}",
            status="present",
        )
        await att_repo.create(r)

    records, total = await att_repo.list(skip=0, limit=2)
    assert total == 5
    assert len(records) == 2


@pytest.mark.asyncio
async def test_repo_find_by_student_and_filters(
    att_repo: AttendanceRepository, seed_data
):
    for i in range(3):
        r = AttendanceRecord(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date=f"2026-03-{15+i:02d}",
            status="present" if i % 2 == 0 else "absent",
        )
        await att_repo.create(r)

    records, total = await att_repo.find_by_student_and_filters(
        seed_data["s1"].id, status="present"
    )
    assert total == 2
    assert len(records) == 2


@pytest.mark.asyncio
async def test_repo_find_by_section_and_date_range(
    att_repo: AttendanceRepository, seed_data
):
    for i in range(3):
        r = AttendanceRecord(
            student_id=seed_data["s1"].id,
            academic_year_id=seed_data["year"].id,
            class_id=seed_data["class"].id,
            section_id=seed_data["section"].id,
            attendance_date=f"2026-03-{15+i:02d}",
            status="present",
        )
        await att_repo.create(r)

    records = await att_repo.find_by_section_and_date_range(
        seed_data["section"].id, "2026-03-15", "2026-03-17"
    )
    assert len(records) == 3


@pytest.mark.asyncio
async def test_repo_delete(
    att_repo: AttendanceRepository, seed_data
):
    record = AttendanceRecord(
        student_id=seed_data["s1"].id,
        academic_year_id=seed_data["year"].id,
        class_id=seed_data["class"].id,
        section_id=seed_data["section"].id,
        attendance_date="2026-03-15",
        status="present",
    )
    await att_repo.create(record)
    record_id = record.id

    db_session = att_repo.session
    await db_session.delete(record)
    await db_session.flush()

    with pytest.raises(NotFoundError, match="not found"):
        await att_repo.get_by_id(record_id)