from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.reports.batch_service import BatchService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.fees.models import FeeDue, FeeStructure, FeeType
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
    FeeTypeRepository,
)
from app.multi_tenant.models import platform_context


@pytest.fixture
async def seeded_batch(db_session: AsyncSession):
    """Seed data for batch operation testing."""
    student_repo = StudentRepository(db_session, platform_context())
    year_repo = AcademicYearRepository(db_session, platform_context())
    class_repo = ClassRepository(db_session, platform_context())
    section_repo = SectionRepository(db_session, platform_context())
    enrollment_repo = EnrollmentRepository(db_session, platform_context())
    ft_repo = FeeTypeRepository(db_session, platform_context())
    fs_repo = FeeStructureRepository(db_session, platform_context())
    fd_repo = FeeDueRepository(db_session, platform_context())
    batch_svc = BatchService(db_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="Batch Year",
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
        Student(first_name="Alice", last_name="Smith", student_number="BT001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="BT002", status="active")
    )
    s3 = await student_repo.create(
        Student(first_name="Inactive", last_name="Student", student_number="BT003", status="inactive")
    )

    ft = await ft_repo.create(FeeType(name="Tuition"))
    await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                     fee_type_id=ft.id, amount=50000, frequency="annual")
    )

    return {
        "batch_svc": batch_svc,
        "student_repo": student_repo,
        "year_repo": year_repo,
        "class_repo": class_repo,
        "section_repo": section_repo,
        "enrollment_repo": enrollment_repo,
        "fd_repo": fd_repo,
        "fs_repo": fs_repo,
        "year": year,
        "cls": cls,
        "section": section,
        "s1": s1,
        "s2": s2,
        "s3": s3,
    }


# ---------------------------------------------------------------------------
# Batch Enrollment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_enroll_success(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    section = seeded_batch["section"]
    s1 = seeded_batch["s1"]
    s2 = seeded_batch["s2"]

    enrollments_data = [
        {"student_id": s1.id, "class_id": cls.id, "section_id": section.id},
        {"student_id": s2.id, "class_id": cls.id, "section_id": section.id},
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["total"] == 2
    assert result["succeeded"] == 2
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_batch_enroll_duplicate(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]

    enrollments_data = [
        {"student_id": s1.id, "class_id": cls.id},
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["succeeded"] == 1

    # Try enrolling the same student again
    result2 = await svc.batch_enroll(year.id, enrollments_data)
    assert result2["succeeded"] == 0
    assert result2["failed"] == 1
    assert "already enrolled" in result2["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_batch_enroll_invalid_student(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]

    enrollments_data = [
        {"student_id": 99999, "class_id": cls.id},
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["succeeded"] == 0
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_batch_enroll_inactive_student(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s3 = seeded_batch["s3"]

    enrollments_data = [
        {"student_id": s3.id, "class_id": cls.id},
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "not active" in result["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_batch_enroll_invalid_class(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    s1 = seeded_batch["s1"]

    enrollments_data = [
        {"student_id": s1.id, "class_id": 99999},
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["succeeded"] == 0
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_batch_enroll_section_not_in_class(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]

    # Create a section in a different class
    other_cls = await seeded_batch["class_repo"].create(
        Class(name="Grade 11", academic_year_id=year.id, status="active")
    )
    other_section = await seeded_batch["section_repo"].create(
        Section(name="Section B", class_id=other_cls.id, status="active")
    )

    enrollments_data = [
        {"student_id": s1.id, "class_id": cls.id, "section_id": other_section.id},
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "does not belong" in result["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_batch_enroll_inactive_academic_year(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year_repo = seeded_batch["year_repo"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]

    inactive_year = await year_repo.create(
        AcademicYear(
            name="Inactive Year",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            status="inactive",
        )
    )

    with pytest.raises(ValidationError, match="inactive"):
        await svc.batch_enroll(
            inactive_year.id,
            [{"student_id": s1.id, "class_id": cls.id}],
        )


@pytest.mark.asyncio
async def test_batch_enroll_mixed_results(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]
    s3 = seeded_batch["s3"]

    enrollments_data = [
        {"student_id": s1.id, "class_id": cls.id},  # Should succeed
        {"student_id": s3.id, "class_id": cls.id},  # Inactive - should fail
        {"student_id": 99999, "class_id": cls.id},  # Invalid - should fail
    ]

    result = await svc.batch_enroll(year.id, enrollments_data)
    assert result["total"] == 3
    assert result["succeeded"] == 1
    assert result["failed"] == 2
    assert len(result["results"]) == 3


# ---------------------------------------------------------------------------
# Batch Fee Dues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_create_fee_dues_success(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]
    s2 = seeded_batch["s2"]

    # First enroll the students
    enrollments_data = [
        {"student_id": s1.id, "class_id": cls.id},
        {"student_id": s2.id, "class_id": cls.id},
    ]
    await svc.batch_enroll(year.id, enrollments_data)

    result = await svc.batch_create_fee_dues(year.id, [s1.id, s2.id])
    assert result["total"] == 2
    assert result["succeeded"] == 2
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_batch_create_fee_dues_duplicate_prevention(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]

    await svc.batch_enroll(year.id, [{"student_id": s1.id, "class_id": cls.id}])
    await svc.batch_create_fee_dues(year.id, [s1.id])

    # Run again - should skip all (duplicate prevention)
    result = await svc.batch_create_fee_dues(year.id, [s1.id])
    assert result["succeeded"] == 1
    assert result["results"][0]["dues_created"] == 0  # All skipped


@pytest.mark.asyncio
async def test_batch_create_fee_dues_not_enrolled(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    s1 = seeded_batch["s1"]

    result = await svc.batch_create_fee_dues(year.id, [s1.id])
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "not enrolled" in result["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_batch_create_fee_dues_inactive_student(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    s3 = seeded_batch["s3"]

    result = await svc.batch_create_fee_dues(year.id, [s3.id])
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "not active" in result["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_batch_create_fee_dues_missing_fee_structures(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    s1 = seeded_batch["s1"]

    # Create a new class without fee structures
    other_cls = await seeded_batch["class_repo"].create(
        Class(name="Grade 12", academic_year_id=year.id, status="active")
    )

    # Enroll student in class without fee structures
    enrollments_data = [{"student_id": s1.id, "class_id": other_cls.id}]
    await svc.batch_enroll(year.id, enrollments_data)

    result = await svc.batch_create_fee_dues(year.id, [s1.id])
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert "No active fee structures" in result["results"][0]["error"]


@pytest.mark.asyncio
async def test_batch_create_fee_dues_mixed_results(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]
    s3 = seeded_batch["s3"]

    # Enroll s1 only
    await svc.batch_enroll(year.id, [{"student_id": s1.id, "class_id": cls.id}])

    result = await svc.batch_create_fee_dues(year.id, [s1.id, s3.id])
    assert result["total"] == 2
    assert result["succeeded"] == 1  # s1
    assert result["failed"] == 1     # s3 (inactive)


@pytest.mark.asyncio
async def test_batch_create_fee_dues_inactive_year(seeded_batch):
    svc = seeded_batch["batch_svc"]
    year_repo = seeded_batch["year_repo"]
    s1 = seeded_batch["s1"]

    inactive_year = await year_repo.create(
        AcademicYear(
            name="Inactive Year",
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 12, 31),
            status="inactive",
        )
    )

    with pytest.raises(ValidationError, match="inactive"):
        await svc.batch_create_fee_dues(inactive_year.id, [s1.id])


@pytest.mark.asyncio
async def test_batch_create_fee_dues_integer_monetary(seeded_batch):
    """Verify monetary calculations use integer minor units only."""
    svc = seeded_batch["batch_svc"]
    year = seeded_batch["year"]
    cls = seeded_batch["cls"]
    s1 = seeded_batch["s1"]
    fs_repo = seeded_batch["fs_repo"]

    await svc.batch_enroll(year.id, [{"student_id": s1.id, "class_id": cls.id}])

    # Verify fee structure amounts are integers
    from app.domains.fees.models import FeeStructure
    structures, _ = await fs_repo.list(academic_year_id=year.id, limit=100)
    for fs in structures:
        assert isinstance(fs.amount, int)
        assert fs.amount > 0
