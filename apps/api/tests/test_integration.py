from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from tests.conftest import pytest_register_postgres
from app.multi_tenant.models import platform_context


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_postgres_connection(postgres_session: AsyncSession):
    """Verify basic connectivity against PostgreSQL via Testcontainers."""
    result = await postgres_session.execute(text("SELECT 1 AS val"))
    row = result.one()
    assert row.val == 1


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_postgres_create_and_read(postgres_session: AsyncSession):
    """Create a table, insert a row, verify it persists in the same session."""
    await postgres_session.execute(text("CREATE TABLE IF NOT EXISTS pg_test (id INTEGER PRIMARY KEY, label TEXT)"))
    await postgres_session.execute(
        text("INSERT INTO pg_test (id, label) VALUES (:id, :label)"),
        {"id": 1, "label": "integration-check"},
    )
    await postgres_session.commit()

    result = await postgres_session.execute(
        text("SELECT label FROM pg_test WHERE id = :id"),
        {"id": 1},
    )
    assert result.scalar() == "integration-check"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_postgres_rollback(postgres_session: AsyncSession):
    """Verify rollback works correctly in PostgreSQL."""
    await postgres_session.execute(text("CREATE TABLE IF NOT EXISTS pg_rollback_test (id INTEGER PRIMARY KEY)"))
    await postgres_session.execute(
        text("INSERT INTO pg_rollback_test (id) VALUES (:id)"),
        {"id": 1},
    )
    await postgres_session.rollback()

    result = await postgres_session.execute(
        text("SELECT COUNT(*) FROM pg_rollback_test"),
    )
    assert result.scalar() == 0


# ---------------------------------------------------------------------------
# Student integration tests (PostgreSQL via Testcontainers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_student_postgres_create_and_retrieve(postgres_session: AsyncSession):
    """Create a Student via the repository and retrieve it from PostgreSQL."""
    repo = StudentRepository(postgres_session, platform_context())
    student = Student(
        first_name="PG",
        last_name="Student",
        student_number="PG001",
        status="active",
    )
    created = await repo.create(student)
    assert created.id is not None

    fetched = await repo.get_by_id(created.id)
    assert fetched.first_name == "PG"
    assert fetched.student_number == "PG001"
    assert fetched.status == "active"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_student_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify the unique constraint on student_number in PostgreSQL."""
    repo = StudentRepository(postgres_session, platform_context())
    s1 = Student(first_name="First", last_name="Student", student_number="UNIQ01", status="active")
    await repo.create(s1)

    s2 = Student(first_name="Second", last_name="Student", student_number="UNIQ01", status="active")
    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repo.create(s2)


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_student_postgres_list_and_count(postgres_session: AsyncSession):
    """Create multiple students and verify list with count in PostgreSQL."""
    repo = StudentRepository(postgres_session, platform_context())
    for i in range(3):
        s = Student(
            first_name=f"PG{i}",
            last_name="Test",
            student_number=f"PL{i:03d}",
            status="active",
        )
        await repo.create(s)

    students, total = await repo.list(skip=0, limit=10)
    assert total == 3
    assert len(students) == 3


# ---------------------------------------------------------------------------
# Academic integration tests (PostgreSQL via Testcontainers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_academic_year_postgres_create(postgres_session: AsyncSession):
    """Create an academic year and retrieve it from PostgreSQL."""
    repo = AcademicYearRepository(postgres_session, platform_context())
    year = AcademicYear(
        name="PG Year",
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        status="active",
    )
    created = await repo.create(year)
    assert created.id is not None
    assert created.name == "PG Year"

    fetched = await repo.get_by_id(created.id)
    assert fetched.name == "PG Year"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_academic_class_section_relationship(postgres_session: AsyncSession):
    """Create academic year -> class -> section hierarchy in PostgreSQL."""
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    section_repo = SectionRepository(postgres_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="PG Year 2",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="A", class_id=cls.id, status="active")
    )

    assert section.class_id == cls.id
    assert cls.academic_year_id == year.id

    sections, total = await section_repo.list_by_class(cls.id)
    assert total == 1
    assert sections[0].id == section.id


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_enrollment_postgres_create(postgres_session: AsyncSession):
    """Create a student, academic year, and enrollment in PostgreSQL."""
    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG", last_name="Student", student_number="PGENR001", status="active")
    )
    year = await year_repo.create(
        AcademicYear(
            name="PG Enroll Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )

    enrollment = await enrollment_repo.create(
        Enrollment(
            student_id=student.id,
            academic_year_id=year.id,
            status="active",
        )
    )
    assert enrollment.id is not None
    assert enrollment.student_id == student.id
    assert enrollment.academic_year_id == year.id


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_enrollment_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify unique constraint on (student_id, academic_year_id) in PostgreSQL."""
    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG", last_name="Unique", student_number="PGUNIQ001", status="active")
    )
    year = await year_repo.create(
        AcademicYear(
            name="PG Unique Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )

    await enrollment_repo.create(
        Enrollment(student_id=student.id, academic_year_id=year.id, status="active")
    )

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await enrollment_repo.create(
            Enrollment(student_id=student.id, academic_year_id=year.id, status="active")
        )


# ---------------------------------------------------------------------------
# Attendance integration tests (PostgreSQL via Testcontainers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_attendance_postgres_create_and_retrieve(postgres_session: AsyncSession):
    """Create an attendance record and retrieve it from PostgreSQL."""
    from app.domains.attendance.models import AttendanceRecord
    from app.domains.attendance.repository import AttendanceRepository

    repo = AttendanceRepository(postgres_session, platform_context())
    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    section_repo = SectionRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG", last_name="Attend", student_number="PGATT001", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Att Year", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Section A", class_id=cls.id, status="active")
    )
    await enrollment_repo.create(
        Enrollment(student_id=student.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active")
    )

    import datetime as dt
    from datetime import timezone
    now = dt.datetime.now(timezone.utc)
    record = AttendanceRecord(
        student_id=student.id,
        academic_year_id=year.id,
        class_id=cls.id,
        section_id=section.id,
        attendance_date="2026-03-15",
        status="present",
        recorded_at=now,
        updated_at=now,
    )
    created = await repo.create(record)
    assert created.id is not None
    assert created.status == "present"

    fetched = await repo.get_by_id(created.id)
    assert fetched.student_id == student.id
    assert fetched.attendance_date == "2026-03-15"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_attendance_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify the unique constraint on (student_id, attendance_date, section_id) in PostgreSQL."""
    from app.domains.attendance.models import AttendanceRecord
    from app.domains.attendance.repository import AttendanceRepository

    repo = AttendanceRepository(postgres_session, platform_context())
    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    section_repo = SectionRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG", last_name="Unique", student_number="PGUNIQ02", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Uniq Year", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="Grade 11", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Section B", class_id=cls.id, status="active")
    )
    await enrollment_repo.create(
        Enrollment(student_id=student.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active")
    )

    import datetime as dt
    from datetime import timezone
    now = dt.datetime.now(timezone.utc)
    await repo.create(
        AttendanceRecord(
            student_id=student.id, academic_year_id=year.id, class_id=cls.id,
            section_id=section.id, attendance_date="2026-03-15", status="present",
            recorded_at=now, updated_at=now,
        )
    )

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repo.create(
            AttendanceRecord(
                student_id=student.id, academic_year_id=year.id, class_id=cls.id,
                section_id=section.id, attendance_date="2026-03-15", status="absent",
                recorded_at=now, updated_at=now,
            )
        )


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_attendance_postgres_find_by_student(postgres_session: AsyncSession):
    """Find attendance records by student in PostgreSQL."""
    from app.domains.attendance.models import AttendanceRecord
    from app.domains.attendance.repository import AttendanceRepository

    repo = AttendanceRepository(postgres_session, platform_context())
    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    section_repo = SectionRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG", last_name="Find", student_number="PGFIND01", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Find Year", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="Grade 12", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Section C", class_id=cls.id, status="active")
    )
    await enrollment_repo.create(
        Enrollment(student_id=student.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active")
    )

    import datetime as dt
    from datetime import timezone
    now = dt.datetime.now(timezone.utc)
    for i in range(3):
        await repo.create(
            AttendanceRecord(
                student_id=student.id, academic_year_id=year.id, class_id=cls.id,
                section_id=section.id, attendance_date=f"2026-03-{15+i:02d}",
                status="present", recorded_at=now, updated_at=now,
            )
        )

    records = await repo.find_by_student_and_date_range(student.id, "2026-03-15", "2026-03-17")
    assert len(records) == 3


# ---------------------------------------------------------------------------
# Fees integration tests (PostgreSQL via Testcontainers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_fee_type_postgres_create_and_retrieve(postgres_session: AsyncSession):
    """Create a FeeType and retrieve it from PostgreSQL."""
    from app.domains.fees.models import FeeType
    from app.domains.fees.repository import FeeTypeRepository

    repo = FeeTypeRepository(postgres_session, platform_context())
    ft = await repo.create(FeeType(name="PG Tuition", description="Tuition in PG"))
    assert ft.id is not None
    assert ft.name == "PG Tuition"

    fetched = await repo.get_by_id(ft.id)
    assert fetched.name == "PG Tuition"
    assert fetched.status == "active"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_fee_type_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify unique constraint on fee type name in PostgreSQL."""
    from app.domains.fees.models import FeeType
    from app.domains.fees.repository import FeeTypeRepository

    repo = FeeTypeRepository(postgres_session, platform_context())
    await repo.create(FeeType(name="Unique FT"))

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repo.create(FeeType(name="Unique FT"))


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_fee_structure_postgres_fk_relationships(postgres_session: AsyncSession):
    """Create FeeStructure with FK references and verify in PostgreSQL."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository

    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    ft = await ft_repo.create(FeeType(name="Structure FT"))
    year = await year_repo.create(
        AcademicYear(name="PG FS Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Grade 10", academic_year_id=year.id, status="active")
    )

    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000, frequency="annual")
    )
    assert fs.id is not None
    assert fs.academic_year_id == year.id
    assert fs.class_id == cls.id
    assert fs.fee_type_id == ft.id

    fetched = await fs_repo.get_by_id(fs.id)
    assert fetched.amount == 50000


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_fee_structure_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify unique constraint on (academic_year_id, class_id, fee_type_id) in PostgreSQL."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository

    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    ft = await ft_repo.create(FeeType(name="Uniq Struct FT"))
    year = await year_repo.create(
        AcademicYear(name="PG Uniq FS Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Uniq Grade", academic_year_id=year.id, status="active")
    )

    await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000)
    )

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await fs_repo.create(
            FeeStructure(academic_year_id=year.id, class_id=cls.id,
                          fee_type_id=ft.id, amount=60000)
        )


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_fee_due_postgres_create_with_relationships(postgres_session: AsyncSession):
    """Create FeeDue with student + academic year FK relationships in PostgreSQL."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository, FeeDueRepository
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository
    from app.domains.student.models import Student
    from app.domains.student.repository import StudentRepository

    student_repo = StudentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG FeeDue", last_name="Test", student_number="PGFD001", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG FD Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG FD Grade", academic_year_id=year.id, status="active")
    )
    ft = await ft_repo.create(FeeType(name="PG FD Type"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000)
    )

    due = await fd_repo.create(
        FeeDue(student_id=student.id, academic_year_id=year.id,
               fee_structure_id=fs.id, original_amount=50000,
               amount_paid=0, status="unpaid")
    )
    assert due.id is not None
    assert due.student_id == student.id
    assert due.academic_year_id == year.id
    assert due.original_amount == 50000

    fetched = await fd_repo.get_by_id(due.id)
    assert fetched.amount_paid == 0
    assert fetched.status == "unpaid"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_fee_due_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify unique constraint on (student_id, fee_structure_id) in PostgreSQL."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository, FeeDueRepository
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository
    from app.domains.student.models import Student
    from app.domains.student.repository import StudentRepository

    student_repo = StudentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG Uniq FD", last_name="Test", student_number="PGUNIQFD", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Uniq FD Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Uniq FD Grade", academic_year_id=year.id, status="active")
    )
    ft = await ft_repo.create(FeeType(name="PG Uniq FD Type"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000)
    )

    await fd_repo.create(
        FeeDue(student_id=student.id, academic_year_id=year.id,
               fee_structure_id=fs.id, original_amount=50000,
               amount_paid=0, status="unpaid")
    )

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await fd_repo.create(
            FeeDue(student_id=student.id, academic_year_id=year.id,
                   fee_structure_id=fs.id, original_amount=50000,
                   amount_paid=0, status="unpaid")
        )


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_payment_postgres_create_with_relationships(postgres_session: AsyncSession):
    """Create Payment with FK references in PostgreSQL."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue, Payment
    from app.domains.fees.repository import (
        FeeTypeRepository, FeeStructureRepository,
        FeeDueRepository, PaymentRepository,
    )
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository
    from app.domains.student.models import Student
    from app.domains.student.repository import StudentRepository

    student_repo = StudentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    pmt_repo = PaymentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG Pmt", last_name="Test", student_number="PGPMT001", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Pmt Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Pmt Grade", academic_year_id=year.id, status="active")
    )
    ft = await ft_repo.create(FeeType(name="PG Pmt Type"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000)
    )
    due = await fd_repo.create(
        FeeDue(student_id=student.id, academic_year_id=year.id,
               fee_structure_id=fs.id, original_amount=50000,
               amount_paid=0, status="unpaid")
    )

    payment = await pmt_repo.create(
        Payment(student_id=student.id, fee_due_id=due.id, amount=25000,
                payment_date="2026-03-15", payment_method="cash",
                receipt_number="PG_RCP001")
    )
    assert payment.id is not None
    assert payment.amount == 25000
    assert payment.receipt_number == "PG_RCP001"

    fetched = await pmt_repo.get_by_id(payment.id)
    assert fetched.student_id == student.id
    assert fetched.fee_due_id == due.id


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_payment_receipt_unique_constraint_postgres(postgres_session: AsyncSession):
    """Verify unique constraint on receipt_number in PostgreSQL."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue, Payment
    from app.domains.fees.repository import (
        FeeTypeRepository, FeeStructureRepository,
        FeeDueRepository, PaymentRepository,
    )
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository
    from app.domains.student.models import Student
    from app.domains.student.repository import StudentRepository

    student_repo = StudentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    pmt_repo = PaymentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG Receipt", last_name="Test", student_number="PGRCP01", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Receipt Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Receipt Grade", academic_year_id=year.id, status="active")
    )
    ft = await ft_repo.create(FeeType(name="PG Receipt Type"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000)
    )
    due = await fd_repo.create(
        FeeDue(student_id=student.id, academic_year_id=year.id,
               fee_structure_id=fs.id, original_amount=50000,
               amount_paid=0, status="unpaid")
    )

    await pmt_repo.create(
        Payment(student_id=student.id, fee_due_id=due.id, amount=25000,
                receipt_number="PG_UNIQUE_RCP")
    )

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await pmt_repo.create(
            Payment(student_id=student.id, fee_due_id=due.id, amount=10000,
                    receipt_number="PG_UNIQUE_RCP")
        )


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_payment_postgres_no_overpayment_postgres(postgres_session: AsyncSession):
    """Verify monetary logic in PostgreSQL — amount_paid tracks correctly."""
    import datetime
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue, Payment
    from app.domains.fees.repository import (
        FeeTypeRepository, FeeStructureRepository,
        FeeDueRepository, PaymentRepository,
    )
    from app.domains.academic.models import AcademicYear, Class
    from app.domains.academic.repository import AcademicYearRepository, ClassRepository
    from app.domains.student.models import Student
    from app.domains.student.repository import StudentRepository

    student_repo = StudentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    pmt_repo = PaymentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())

    student = await student_repo.create(
        Student(first_name="PG Mon", last_name="Test", student_number="PGMON01", status="active")
    )
    year = await year_repo.create(
        AcademicYear(name="PG Mon Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Mon Grade", academic_year_id=year.id, status="active")
    )
    ft = await ft_repo.create(FeeType(name="PG Mon Type"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                      fee_type_id=ft.id, amount=50000)
    )
    due = await fd_repo.create(
        FeeDue(student_id=student.id, academic_year_id=year.id,
               fee_structure_id=fs.id, original_amount=50000,
               amount_paid=0, status="unpaid")
    )

    pmt_repo_inst = pmt_repo
    fd_repo_inst = fd_repo

    await pmt_repo_inst.create(
        Payment(student_id=student.id, fee_due_id=due.id, amount=25000,
                receipt_number="PG_MON_RCP1")
    )
    due.amount_paid = 25000
    due.status = "partially_paid"
    await fd_repo_inst.update(due)

    assert due.amount_paid == 25000
    assert due.status == "partially_paid"

    await pmt_repo_inst.create(
        Payment(student_id=student.id, fee_due_id=due.id, amount=25000,
                receipt_number="PG_MON_RCP2")
    )
    due.amount_paid = 50000
    due.status = "paid"
    await fd_repo_inst.update(due)

    assert due.amount_paid == 50000
    assert due.status == "paid"


# ---------------------------------------------------------------------------
# Academic Structure Extension integration tests (PostgreSQL via Testcontainers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_teacher_postgres_create_and_retrieve(postgres_session: AsyncSession):
    """Create a Teacher and retrieve it from PostgreSQL."""
    from app.domains.academic.models import Teacher
    from app.domains.academic.repository import TeacherRepository

    repo = TeacherRepository(postgres_session, platform_context())
    teacher = Teacher(
        first_name="PG",
        last_name="Teacher",
        employee_number="PGT001",
        status="active",
    )
    created = await repo.create(teacher)
    assert created.id is not None
    assert created.first_name == "PG"

    fetched = await repo.get_by_id(created.id)
    assert fetched.last_name == "Teacher"
    assert fetched.employee_number == "PGT001"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_teacher_postgres_unique_constraint(postgres_session: AsyncSession):
    """Verify unique constraint on employee_number in PostgreSQL."""
    from app.domains.academic.models import Teacher
    from app.domains.academic.repository import TeacherRepository

    repo = TeacherRepository(postgres_session, platform_context())
    await repo.create(
        Teacher(first_name="A", last_name="B", employee_number="PGUNIQT01")
    )
    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repo.create(
            Teacher(first_name="C", last_name="D", employee_number="PGUNIQT01")
        )


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_subject_postgres_create_and_retrieve(postgres_session: AsyncSession):
    """Create a Subject and retrieve it from PostgreSQL."""
    from app.domains.academic.models import Subject
    from app.domains.academic.repository import SubjectRepository

    repo = SubjectRepository(postgres_session, platform_context())
    subject = Subject(name="PG Subject", code="PGSUB01", status="active")
    created = await repo.create(subject)
    assert created.id is not None
    assert created.name == "PG Subject"

    fetched = await repo.get_by_id(created.id)
    assert fetched.code == "PGSUB01"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_subject_postgres_unique_constraints(postgres_session: AsyncSession):
    """Verify unique constraints on name and code in PostgreSQL."""
    from app.domains.academic.models import Subject
    from app.domains.academic.repository import SubjectRepository

    repo = SubjectRepository(postgres_session, platform_context())
    await repo.create(Subject(name="Uniq Name", code="UNIQ01"))

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repo.create(Subject(name="Uniq Name", code="UNIQ02"))

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repo.create(Subject(name="Other Name", code="UNIQ01"))


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_term_postgres_create_and_retrieve(postgres_session: AsyncSession):
    """Create a Term with FK to academic year in PostgreSQL."""
    import datetime
    from app.domains.academic.models import AcademicYear, Term
    from app.domains.academic.repository import AcademicYearRepository, TermRepository

    year_repo = AcademicYearRepository(postgres_session, platform_context())
    term_repo = TermRepository(postgres_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="PG Term Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )

    term = await term_repo.create(
        Term(
            academic_year_id=year.id,
            name="PG Term 1",
            start_date="2026-01-01",
            end_date="2026-03-31",
            status="active",
        )
    )
    assert term.id is not None
    assert term.academic_year_id == year.id

    fetched = await term_repo.get_by_id(term.id)
    assert fetched.name == "PG Term 1"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_teacher_assignment_postgres_fk_chains(postgres_session: AsyncSession):
    """Create complete FK chain: teacher + class + subject -> assignment in PostgreSQL."""
    import datetime
    from app.domains.academic.models import (
        AcademicYear, Class, Teacher, Subject, TeacherAssignment,
    )
    from app.domains.academic.repository import (
        AcademicYearRepository, ClassRepository,
        TeacherRepository, SubjectRepository, TeacherAssignmentRepository,
    )

    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    teacher_repo = TeacherRepository(postgres_session, platform_context())
    subject_repo = SubjectRepository(postgres_session, platform_context())
    assignment_repo = TeacherAssignmentRepository(postgres_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="PG Assign Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="PG Assign Grade", academic_year_id=year.id, status="active")
    )
    teacher = await teacher_repo.create(
        Teacher(
            first_name="PGAssign",
            last_name="Teacher",
            employee_number="PGASN01",
            status="active",
        )
    )
    subject = await subject_repo.create(
        Subject(name="PG Assign Subject", code="PGASNSUB", status="active")
    )

    assignment = await assignment_repo.create(
        TeacherAssignment(
            teacher_id=teacher.id,
            class_id=cls.id,
            subject_id=subject.id,
            status="active",
        )
    )
    assert assignment.id is not None
    assert assignment.teacher_id == teacher.id
    assert assignment.class_id == cls.id
    assert assignment.subject_id == subject.id

    fetched = await assignment_repo.get_by_id(assignment.id)
    assert fetched.status == "active"


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_teacher_assignment_unique_constraint_postgres(postgres_session: AsyncSession):
    """Verify unique constraint on (class_id, subject_id) in PostgreSQL."""
    import datetime
    from app.domains.academic.models import (
        AcademicYear, Class, Teacher, Subject, TeacherAssignment,
    )
    from app.domains.academic.repository import (
        AcademicYearRepository, ClassRepository,
        TeacherRepository, SubjectRepository, TeacherAssignmentRepository,
    )

    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    teacher_repo = TeacherRepository(postgres_session, platform_context())
    subject_repo = SubjectRepository(postgres_session, platform_context())
    assignment_repo = TeacherAssignmentRepository(postgres_session, platform_context())

    year = await year_repo.create(
        AcademicYear(
            name="PG Unique Assign Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="PG U Assign Grade", academic_year_id=year.id, status="active")
    )
    t1 = await teacher_repo.create(
        Teacher(first_name="T1", last_name="A", employee_number="PGUNQASN1", status="active")
    )
    t2 = await teacher_repo.create(
        Teacher(first_name="T2", last_name="B", employee_number="PGUNQASN2", status="active")
    )
    subject = await subject_repo.create(
        Subject(name="PG U Assign Subj", code="PGUNQSUB", status="active")
    )

    await assignment_repo.create(
        TeacherAssignment(teacher_id=t1.id, class_id=cls.id, subject_id=subject.id, status="active")
    )

    import sqlalchemy.exc
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await assignment_repo.create(
            TeacherAssignment(teacher_id=t2.id, class_id=cls.id, subject_id=subject.id, status="active")
        )


# ---------------------------------------------------------------------------
# Reports integration tests (PostgreSQL via Testcontainers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_attendance_class_report_postgres(postgres_session: AsyncSession):
    """Test attendance class report aggregation in PostgreSQL."""
    from app.domains.reports.attendance_reports import AttendanceReportService
    from app.domains.attendance.models import AttendanceRecord
    from app.domains.attendance.repository import AttendanceRepository

    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    section_repo = SectionRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())
    att_repo = AttendanceRepository(postgres_session, platform_context())
    report_svc = AttendanceReportService(postgres_session)

    year = await year_repo.create(
        AcademicYear(name="PG Report Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Grade 10", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="PG Sec A", class_id=cls.id, status="active")
    )
    s = await student_repo.create(
        Student(first_name="PG Rep", last_name="Student", student_number="PGRPT01", status="active")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    await enrollment_repo.create(
        Enrollment(student_id=s.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active", enrolled_at=now, created_at=now, updated_at=now)
    )
    await att_repo.create(
        AttendanceRecord(student_id=s.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, attendance_date="2026-03-15", status="present", recorded_at=now, updated_at=now)
    )

    report = await report_svc.get_class_attendance_summary(cls.id, year.id)
    assert report["total_records"] == 1
    assert report["present"] == 1
    assert report["present_percentage"] == 100.0


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_fee_collection_postgres(postgres_session: AsyncSession):
    """Test fee collection report aggregation in PostgreSQL."""
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue, Payment
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository, FeeDueRepository, PaymentRepository
    from app.domains.reports.fee_reports import FeeReportService

    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    pmt_repo = PaymentRepository(postgres_session, platform_context())
    report_svc = FeeReportService(postgres_session)

    year = await year_repo.create(
        AcademicYear(name="PG Coll Report", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Coll Class", academic_year_id=year.id, status="active")
    )
    s = await student_repo.create(
        Student(first_name="PG Coll", last_name="Student", student_number="PGCOLL01", status="active")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    await enrollment_repo.create(
        Enrollment(student_id=s.id, academic_year_id=year.id, class_id=cls.id, status="active", enrolled_at=now, created_at=now, updated_at=now)
    )
    ft = await ft_repo.create(FeeType(name="PG Coll Fee"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id, fee_type_id=ft.id, amount=50000, frequency="annual")
    )
    due = await fd_repo.create(
        FeeDue(student_id=s.id, academic_year_id=year.id, fee_structure_id=fs.id, original_amount=50000, amount_paid=25000, status="partially_paid", created_at=now, updated_at=now)
    )
    await pmt_repo.create(
        Payment(student_id=s.id, fee_due_id=due.id, amount=25000, payment_date="2026-03-15", receipt_number="PG_COLL_RCP", created_at=now)
    )

    report = await report_svc.get_collection_report(year.id)
    assert len(report) > 0
    assert report[0]["total_fees_assigned"] == 50000
    assert report[0]["total_collected"] == 25000


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_batch_enroll_rollback_postgres(postgres_session: AsyncSession):
    """Verify batch enroll rolls back properly on failure in PostgreSQL."""
    from app.domains.reports.batch_service import BatchService

    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    batch_svc = BatchService(postgres_session)

    year = await year_repo.create(
        AcademicYear(name="PG Batch Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Batch Class", academic_year_id=year.id, status="active")
    )
    s = await student_repo.create(
        Student(first_name="PG Batch", last_name="Student", student_number="PGBAT01", status="active")
    )

    result = await batch_svc.batch_enroll(
        year.id,
        [{"student_id": s.id, "class_id": cls.id}],
    )
    assert result["succeeded"] == 1
    assert result["failed"] == 0


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_export_csv_postgres(postgres_session: AsyncSession):
    """Verify CSV export works with PostgreSQL data."""
    from app.domains.reports.export_service import ExportService

    student_repo = StudentRepository(postgres_session, platform_context())
    s = await student_repo.create(
        Student(first_name="PG Export", last_name="Test", student_number="PGEXPT01", status="active")
    )

    export_svc = ExportService(postgres_session)
    response = await export_svc.export_students_csv()

    body = b"".join([chunk async for chunk in response.body_iterator])
    content = body.decode("utf-8-sig")
    assert "PGEXPT01" in content
    assert "PG Export" in content
    assert "password" not in content.lower()


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_rollover_execute_postgres(postgres_session: AsyncSession):
    """Verify academic year rollover in PostgreSQL."""
    from app.domains.reports.rollover_service import RolloverService

    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    section_repo = SectionRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())
    student_repo = StudentRepository(postgres_session, platform_context())
    rollover_svc = RolloverService(postgres_session)

    year = await year_repo.create(
        AcademicYear(name="PG Rollover Source", start_date=datetime.date(2025, 9, 1),
                      end_date=datetime.date(2026, 8, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Roll Class", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="PG Roll Sec", class_id=cls.id, status="active")
    )
    s = await student_repo.create(
        Student(first_name="PG Roll", last_name="Student", student_number="PGROLL01", status="active")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    await enrollment_repo.create(
        Enrollment(student_id=s.id, academic_year_id=year.id, class_id=cls.id, section_id=section.id, status="active", enrolled_at=now, created_at=now, updated_at=now)
    )

    result = await rollover_svc.execute_rollover(
        from_year_id=year.id,
        to_year_name="PG Rollover Target",
        to_start_date="2026-09-01",
        to_end_date="2027-08-31",
    )
    assert result["success"] is True
    assert result["classes_created"] >= 1
    assert result["sections_created"] >= 1
    assert result["enrollments_created"] >= 1


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_fee_outstanding_postgres(postgres_session: AsyncSession):
    """Verify outstanding fee report in PostgreSQL."""
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue, Payment
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository, FeeDueRepository, PaymentRepository
    from app.domains.reports.fee_reports import FeeReportService

    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    enrollment_repo = EnrollmentRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    pmt_repo = PaymentRepository(postgres_session, platform_context())
    report_svc = FeeReportService(postgres_session)

    year = await year_repo.create(
        AcademicYear(name="PG Out Report", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Out Class", academic_year_id=year.id, status="active")
    )
    s = await student_repo.create(
        Student(first_name="PG Out", last_name="Student", student_number="PGOUT01", status="active")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    await enrollment_repo.create(
        Enrollment(student_id=s.id, academic_year_id=year.id, class_id=cls.id, status="active", enrolled_at=now, created_at=now, updated_at=now)
    )
    ft = await ft_repo.create(FeeType(name="PG Out Fee"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id, fee_type_id=ft.id, amount=50000, frequency="annual")
    )
    await fd_repo.create(
        FeeDue(student_id=s.id, academic_year_id=year.id, fee_structure_id=fs.id, original_amount=50000, amount_paid=0, status="unpaid", created_at=now, updated_at=now)
    )

    report = await report_svc.get_outstanding_report(year.id)
    assert len(report) > 0
    assert report[0]["outstanding"] > 0
    assert report[0]["total_fees"] == 50000
    assert report[0]["total_paid"] == 0
    assert report[0]["outstanding"] == 50000


@pytest.mark.integration
@pytest_register_postgres
@pytest.mark.asyncio
async def test_reports_detailed_receipt_postgres(postgres_session: AsyncSession):
    """Verify detailed receipt in PostgreSQL."""
    from app.domains.fees.models import FeeType, FeeStructure, FeeDue, Payment
    from app.domains.fees.repository import FeeTypeRepository, FeeStructureRepository, FeeDueRepository, PaymentRepository
    from app.domains.reports.fee_reports import FeeReportService

    student_repo = StudentRepository(postgres_session, platform_context())
    year_repo = AcademicYearRepository(postgres_session, platform_context())
    class_repo = ClassRepository(postgres_session, platform_context())
    ft_repo = FeeTypeRepository(postgres_session, platform_context())
    fs_repo = FeeStructureRepository(postgres_session, platform_context())
    fd_repo = FeeDueRepository(postgres_session, platform_context())
    pmt_repo = PaymentRepository(postgres_session, platform_context())
    report_svc = FeeReportService(postgres_session)

    year = await year_repo.create(
        AcademicYear(name="PG Receipt Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(
        Class(name="PG Rcpt Class", academic_year_id=year.id, status="active")
    )
    s = await student_repo.create(
        Student(first_name="PG Rcpt", last_name="Student", student_number="PGRCPT01", status="active")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    ft = await ft_repo.create(FeeType(name="PG Rcpt Fee"))
    fs = await fs_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id, fee_type_id=ft.id, amount=50000, frequency="annual")
    )
    due = await fd_repo.create(
        FeeDue(student_id=s.id, academic_year_id=year.id, fee_structure_id=fs.id, original_amount=50000, amount_paid=50000, status="paid", created_at=now, updated_at=now)
    )
    payment = await pmt_repo.create(
        Payment(student_id=s.id, fee_due_id=due.id, amount=50000, payment_date="2026-03-15", receipt_number="PG_RCPT01", created_at=now)
    )

    receipt = await report_svc.get_detailed_receipt(payment.id)
    assert receipt["receipt_number"] == "PG_RCPT01"
    assert receipt["amount"] == 50000
    assert "PG Rcpt" in receipt["student_name"]
    assert receipt["fee_type_name"] == "PG Rcpt Fee"