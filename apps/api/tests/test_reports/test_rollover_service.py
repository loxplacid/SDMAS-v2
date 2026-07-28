from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.reports.rollover_service import RolloverService
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository


@pytest.fixture
async def seeded_rollover(db_session: AsyncSession):
    """Seed data for rollover testing."""
    student_repo = StudentRepository(db_session)
    year_repo = AcademicYearRepository(db_session)
    class_repo = ClassRepository(db_session)
    section_repo = SectionRepository(db_session)
    enrollment_repo = EnrollmentRepository(db_session)
    rollover_svc = RolloverService(db_session)

    year = await year_repo.create(
        AcademicYear(
            name="Source Year 2025-2026",
            start_date=datetime.date(2025, 9, 1),
            end_date=datetime.date(2026, 8, 31),
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
        Student(first_name="Alice", last_name="Smith", student_number="RL001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="RL002", status="active")
    )
    now = datetime.datetime.now(timezone.utc)
    for s in [s1, s2]:
        await enrollment_repo.create(
            Enrollment(
                student_id=s.id, academic_year_id=year.id,
                class_id=cls.id, section_id=section.id,
                status="active", enrolled_at=now,
                created_at=now, updated_at=now,
            )
        )

    return {
        "rollover_svc": rollover_svc,
        "year_repo": year_repo,
        "class_repo": class_repo,
        "section_repo": section_repo,
        "enrollment_repo": enrollment_repo,
        "source_year": year,
        "cls": cls,
        "section": section,
        "s1": s1,
        "s2": s2,
    }


@pytest.mark.asyncio
async def test_preview_rollover(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]

    preview = await svc.preview_rollover(
        from_year_id=source_year.id,
        to_year_name="2026-2027",
        to_start_date="2026-09-01",
        to_end_date="2027-08-31",
    )
    assert preview["from_year_id"] == source_year.id
    assert preview["to_year_name"] == "2026-2027"
    assert len(preview["classes"]) >= 1
    assert len(preview["sections"]) >= 1
    assert preview["enrolled_students"] == 2
    assert preview["total_items"] > 0


@pytest.mark.asyncio
async def test_preview_rollover_duplicate_name(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]

    with pytest.raises(ConflictError, match="already exists"):
        await svc.preview_rollover(
            from_year_id=source_year.id,
            to_year_name="Source Year 2025-2026",
            to_start_date="2026-09-01",
            to_end_date="2027-08-31",
        )


@pytest.mark.asyncio
async def test_execute_rollover(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]
    enrollment_repo = seeded_rollover["enrollment_repo"]
    year_repo = seeded_rollover["year_repo"]

    result = await svc.execute_rollover(
        from_year_id=source_year.id,
        to_year_name="2026-2027",
        to_start_date="2026-09-01",
        to_end_date="2027-08-31",
    )
    assert result["success"] is True
    assert result["academic_year_name"] == "2026-2027"
    assert result["classes_created"] >= 1
    assert result["sections_created"] >= 1
    assert result["enrollments_created"] == 2

    # Verify target year exists
    new_year = await year_repo.get_by_id(result["academic_year_id"])
    assert new_year.name == "2026-2027"

    # Verify enrollments created in new year
    enrollments, _ = await enrollment_repo.list(
        academic_year_id=result["academic_year_id"], limit=100
    )
    assert len(enrollments) == 2


@pytest.mark.asyncio
async def test_execute_rollover_duplicate_name(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]

    with pytest.raises(ConflictError, match="already exists"):
        await svc.execute_rollover(
            from_year_id=source_year.id,
            to_year_name="Source Year 2025-2026",
            to_start_date="2026-09-01",
            to_end_date="2027-08-31",
        )


@pytest.mark.asyncio
async def test_execute_rollover_duplicate_prevention(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]

    # First execution should succeed
    await svc.execute_rollover(
        from_year_id=source_year.id,
        to_year_name="Unique Year",
        to_start_date="2026-09-01",
        to_end_date="2027-08-31",
    )

    # Second execution with the same name should fail
    with pytest.raises(ConflictError, match="already exists"):
        await svc.execute_rollover(
            from_year_id=source_year.id,
            to_year_name="Unique Year",
            to_start_date="2026-09-01",
            to_end_date="2027-08-31",
        )


@pytest.mark.asyncio
async def test_execute_rollover_historical_preservation(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]
    enrollment_repo = seeded_rollover["enrollment_repo"]
    year_repo = seeded_rollover["year_repo"]

    # Capture original enrollments count
    enrollments_before, _ = await enrollment_repo.list(
        academic_year_id=source_year.id, limit=100
    )
    source_enrollment_count = len(enrollments_before)

    # Execute rollover
    await svc.execute_rollover(
        from_year_id=source_year.id,
        to_year_name="Historical Preserve Year",
        to_start_date="2026-09-01",
        to_end_date="2027-08-31",
    )

    # Verify source year enrollments are preserved
    enrollments_after, _ = await enrollment_repo.list(
        academic_year_id=source_year.id, limit=100
    )
    assert len(enrollments_after) == source_enrollment_count

    # Verify source year still exists
    source_year_after = await year_repo.get_by_id(source_year.id)
    assert source_year_after.name == "Source Year 2025-2026"


@pytest.mark.asyncio
async def test_execute_rollover_invalid_source(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]

    from app.core.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        await svc.execute_rollover(
            from_year_id=99999,
            to_year_name="New Year",
            to_start_date="2026-09-01",
            to_end_date="2027-08-31",
        )


@pytest.mark.asyncio
async def test_execute_rollover_missing_required_fields(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]
    source_year = seeded_rollover["source_year"]

    with pytest.raises(ValidationError):
        await svc.execute_rollover(
            from_year_id=source_year.id,
            to_year_name="",
            to_start_date="2026-09-01",
            to_end_date="2027-08-31",
        )

    with pytest.raises(ValidationError):
        await svc.execute_rollover(
            from_year_id=source_year.id,
            to_year_name="New Year",
            to_start_date="",
            to_end_date="2027-08-31",
        )

    with pytest.raises(ValidationError):
        await svc.execute_rollover(
            from_year_id=source_year.id,
            to_year_name="New Year",
            to_start_date="2026-09-01",
            to_end_date="",
        )


@pytest.mark.asyncio
async def test_preview_rollover_invalid_source(seeded_rollover):
    svc = seeded_rollover["rollover_svc"]

    from app.core.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        await svc.preview_rollover(
            from_year_id=99999,
            to_year_name="New Year",
            to_start_date="2026-09-01",
            to_end_date="2027-08-31",
        )
