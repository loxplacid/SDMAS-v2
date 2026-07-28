from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import StudentCreate, StudentUpdate
from app.domains.student.service import StudentService


@pytest.fixture
def repo(db_session: AsyncSession) -> StudentRepository:
    return StudentRepository(db_session)


@pytest.fixture
def service(repo: StudentRepository) -> StudentService:
    return StudentService(repo)


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_valid_student(service: StudentService):
    data = StudentCreate(
        first_name="John",
        last_name="Doe",
        student_number="STU001",
        email="john@school.com",
    )
    student = await service.create_student(data)
    assert student.id is not None
    assert student.first_name == "John"
    assert student.last_name == "Doe"
    assert student.student_number == "STU001"
    assert student.email == "john@school.com"
    assert student.status == "active"
    assert student.created_at is not None
    assert student.updated_at is not None


@pytest.mark.asyncio
async def test_create_student_default_status(service: StudentService):
    data = StudentCreate(
        first_name="Jane",
        last_name="Smith",
        student_number="STU002",
    )
    student = await service.create_student(data)
    assert student.status == "active"


@pytest.mark.asyncio
async def test_create_student_whitespace_trimming(service: StudentService):
    data = StudentCreate(
        first_name="  Alice  ",
        last_name="  Johnson  ",
        student_number="  STU003  ",
    )
    student = await service.create_student(data)
    assert student.first_name == "Alice"
    assert student.last_name == "Johnson"
    assert student.student_number == "STU003"


@pytest.mark.asyncio
async def test_create_student_null_email(service: StudentService):
    data = StudentCreate(
        first_name="John",
        last_name="Doe",
        student_number="STU004",
        email=None,
    )
    student = await service.create_student(data)
    assert student.email is None


@pytest.mark.asyncio
async def test_create_student_date_of_birth(service: StudentService):
    data = StudentCreate(
        first_name="John",
        last_name="Doe",
        student_number="STU005",
        date_of_birth=datetime.date(2000, 6, 15),
    )
    student = await service.create_student(data)
    assert student.date_of_birth == datetime.date(2000, 6, 15)


@pytest.mark.asyncio
async def test_create_duplicate_student_number(service: StudentService):
    data = StudentCreate(
        first_name="John",
        last_name="Doe",
        student_number="STU001",
    )
    await service.create_student(data)
    duplicate = StudentCreate(
        first_name="Jane",
        last_name="Smith",
        student_number="STU001",
    )
    with pytest.raises(ConflictError, match="already exists"):
        await service.create_student(duplicate)


@pytest.mark.asyncio
async def test_create_invalid_email():
    with pytest.raises(ValueError, match="Invalid email format"):
        StudentCreate(
            first_name="John",
            last_name="Doe",
            student_number="STU006",
            email="not-an-email",
        )


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_student_by_id(service: StudentService):
    data = StudentCreate(
        first_name="John",
        last_name="Doe",
        student_number="STU001",
    )
    created = await service.create_student(data)
    found = await service.get_student(created.id)
    assert found.id == created.id
    assert found.first_name == "John"


@pytest.mark.asyncio
async def test_get_student_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_student(999)


@pytest.mark.asyncio
async def test_find_by_student_number(service: StudentService):
    data = StudentCreate(
        first_name="John",
        last_name="Doe",
        student_number="STU001",
    )
    await service.create_student(data)
    found = await service.find_by_student_number("STU001")
    assert found.first_name == "John"
    assert found.student_number == "STU001"


@pytest.mark.asyncio
async def test_find_by_student_number_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.find_by_student_number("NONEXISTENT")


@pytest.mark.asyncio
async def test_list_students(service: StudentService):
    await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    await service.create_student(
        StudentCreate(first_name="Jane", last_name="Smith", student_number="STU002")
    )

    students, total = await service.list_students()
    assert total == 2
    assert len(students) == 2


@pytest.mark.asyncio
async def test_list_students_empty(service: StudentService):
    students, total = await service.list_students()
    assert total == 0
    assert len(students) == 0


@pytest.mark.asyncio
async def test_list_students_filter_by_status(service: StudentService):
    s1 = await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    await service.create_student(
        StudentCreate(first_name="Jane", last_name="Smith", student_number="STU002")
    )
    await service.deactivate_student(s1.id)

    active, active_total = await service.list_students(status="active")
    assert active_total == 1
    assert active[0].first_name == "Jane"

    inactive, inactive_total = await service.list_students(status="inactive")
    assert inactive_total == 1
    assert inactive[0].first_name == "John"


@pytest.mark.asyncio
async def test_list_students_invalid_status(service: StudentService):
    with pytest.raises(ValidationError, match="Invalid status filter"):
        await service.list_students(status="bogus")


@pytest.mark.asyncio
async def test_search_students_by_name(service: StudentService):
    await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    await service.create_student(
        StudentCreate(first_name="Jane", last_name="Smith", student_number="STU002")
    )
    await service.create_student(
        StudentCreate(first_name="Alice", last_name="Jones", student_number="STU003")
    )

    results, total = await service.search_students("john")
    assert total == 1
    assert len(results) == 1
    assert results[0].first_name == "John"


@pytest.mark.asyncio
async def test_search_students_by_number(service: StudentService):
    await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    results, total = await service.search_students("STU001")
    assert total == 1
    assert len(results) == 1
    assert results[0].student_number == "STU001"


@pytest.mark.asyncio
async def test_search_students_by_email(service: StudentService):
    await service.create_student(
        StudentCreate(
            first_name="John",
            last_name="Doe",
            student_number="STU001",
            email="john@school.com",
        )
    )
    results, total = await service.search_students("john@school.com")
    assert total == 1
    assert len(results) == 1
    assert results[0].email == "john@school.com"


@pytest.mark.asyncio
async def test_search_students_empty_query(service: StudentService):
    with pytest.raises(ValidationError, match="Search query is required"):
        await service.search_students("")
    with pytest.raises(ValidationError, match="Search query is required"):
        await service.search_students("   ")


@pytest.mark.asyncio
async def test_search_students_no_match(service: StudentService):
    await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    results, total = await service.search_students("zzzzz")
    assert total == 0
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_students_with_pagination(service: StudentService):
    for i in range(5):
        await service.create_student(
            StudentCreate(
                first_name=f"Search{i}",
                last_name="User",
                student_number=f"SEA{i:03d}",
            )
        )
    results, total = await service.search_students("Search", skip=0, limit=2)
    assert total == 5
    assert len(results) == 2


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_student_fields(service: StudentService):
    created = await service.create_student(
        StudentCreate(
            first_name="John",
            last_name="Doe",
            student_number="STU001",
            email="john@old.com",
        )
    )
    updated = await service.update_student(
        created.id,
        StudentUpdate(first_name="Jonathan", email="jonathan@school.com"),
    )
    assert updated.first_name == "Jonathan"
    assert updated.last_name == "Doe"
    assert updated.email == "jonathan@school.com"
    assert updated.student_number == "STU001"


@pytest.mark.asyncio
async def test_update_student_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.update_student(999, StudentUpdate(first_name="Ghost"))


@pytest.mark.asyncio
async def test_update_student_invalid_email():
    with pytest.raises(ValueError, match="Invalid email format"):
        StudentUpdate(email="bad")


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_student(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="Delete", last_name="Me", student_number="STU100")
    )
    await service.delete_student(created.id)
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_student(created.id)


@pytest.mark.asyncio
async def test_delete_nonexistent_student(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.delete_student(999)


@pytest.mark.asyncio
async def test_delete_then_recreate_same_number(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="Temp", last_name="Student", student_number="STU101")
    )
    await service.delete_student(created.id)
    recreated = await service.create_student(
        StudentCreate(first_name="New", last_name="Student", student_number="STU101")
    )
    assert recreated.student_number == "STU101"
    assert recreated.first_name == "New"
    assert recreated.status == "active"


# ---------------------------------------------------------------------------
# DEACTIVATE / REACTIVATE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deactivate_student(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    deactivated = await service.deactivate_student(created.id)
    assert deactivated.status == "inactive"


@pytest.mark.asyncio
async def test_deactivate_already_inactive(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    await service.deactivate_student(created.id)
    with pytest.raises(ConflictError, match="already inactive"):
        await service.deactivate_student(created.id)


@pytest.mark.asyncio
async def test_reactivate_student(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    await service.deactivate_student(created.id)
    reactivated = await service.reactivate_student(created.id)
    assert reactivated.status == "active"


@pytest.mark.asyncio
async def test_reactivate_already_active(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="John", last_name="Doe", student_number="STU001")
    )
    with pytest.raises(ConflictError, match="already active"):
        await service.reactivate_student(created.id)


@pytest.mark.asyncio
async def test_deactivate_reactivate_cycle(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="Cycle", last_name="Test", student_number="STU002")
    )
    await service.deactivate_student(created.id)
    assert (await service.get_student(created.id)).status == "inactive"
    await service.reactivate_student(created.id)
    assert (await service.get_student(created.id)).status == "active"
    await service.deactivate_student(created.id)
    assert (await service.get_student(created.id)).status == "inactive"


# ---------------------------------------------------------------------------
# LIFE-CYCLE INTEGRATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_lifecycle(service: StudentService):
    created = await service.create_student(
        StudentCreate(
            first_name="  Alice  ",
            last_name="Johnson",
            student_number="STU100",
            email="alice@school.com",
            date_of_birth=datetime.date(2000, 6, 15),
        )
    )
    assert created.first_name == "Alice"
    assert created.date_of_birth == datetime.date(2000, 6, 15)

    retrieved = await service.get_student(created.id)
    assert retrieved.first_name == "Alice"

    updated = await service.update_student(
        created.id, StudentUpdate(first_name="Alicia", email="alicia@school.com")
    )
    assert updated.first_name == "Alicia"
    assert updated.email == "alicia@school.com"

    deactivated = await service.deactivate_student(created.id)
    assert deactivated.status == "inactive"

    reactivated = await service.reactivate_student(created.id)
    assert reactivated.status == "active"

    final = await service.get_student(created.id)
    assert final.first_name == "Alicia"
    assert final.email == "alicia@school.com"
    assert final.status == "active"


# ---------------------------------------------------------------------------
# DATA CONSISTENCY
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_updates_consistency(service: StudentService):
    student = await service.create_student(
        StudentCreate(
            first_name="Consistency",
            last_name="Check",
            student_number="STU050",
            email="test@school.com",
        )
    )
    await service.update_student(student.id, StudentUpdate(first_name="Verified"))
    await service.update_student(student.id, StudentUpdate(last_name="Confirmed"))
    await service.update_student(student.id, StudentUpdate(email="verified@school.com"))

    final = await service.get_student(student.id)
    assert final.first_name == "Verified"
    assert final.last_name == "Confirmed"
    assert final.email == "verified@school.com"
    assert final.student_number == "STU050"
    assert final.status == "active"


@pytest.mark.asyncio
async def test_updated_at_changes(service: StudentService):
    student = await service.create_student(
        StudentCreate(first_name="Time", last_name="Tracker", student_number="STU060")
    )
    original_updated = student.updated_at

    await service.update_student(student.id, StudentUpdate(first_name="Time2"))
    updated = await service.get_student(student.id)
    assert updated.updated_at != original_updated


@pytest.mark.asyncio
async def test_updated_at_after_update_greater_than_created_at(service: StudentService):
    student = await service.create_student(
        StudentCreate(first_name="Time2", last_name="Tracker", student_number="STU061")
    )
    await service.update_student(student.id, StudentUpdate(first_name="Time3"))
    updated = await service.get_student(student.id)
    assert updated.updated_at >= updated.created_at


# ---------------------------------------------------------------------------
# REPOSITORY DIRECT TESTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repository_get_by_id_not_found(repo: StudentRepository):
    with pytest.raises(NotFoundError, match="not found"):
        await repo.get_by_id(999)


@pytest.mark.asyncio
async def test_repository_exists_by_student_number(repo: StudentRepository):
    s = Student(first_name="Exists", last_name="Test", student_number="EX001", status="active")
    await repo.create(s)
    assert await repo.exists_by_student_number("EX001") is True
    assert await repo.exists_by_student_number("NONEXISTENT") is False


@pytest.mark.asyncio
async def test_repository_delete_via_repo(repo: StudentRepository):
    s = Student(first_name="RepoDel", last_name="Test", student_number="RD001", status="active")
    await repo.create(s)
    assert await repo.exists_by_student_number("RD001") is True
    await repo.delete(s)
    assert await repo.exists_by_student_number("RD001") is False


@pytest.mark.asyncio
async def test_repository_search_multiple_fields(service: StudentService):
    await service.create_student(
        StudentCreate(
            first_name="Robert", last_name="Jones", student_number="STU020", email="rob@school.com"
        )
    )
    await service.create_student(
        StudentCreate(
            first_name="Roberta", last_name="Smith", student_number="STU021", email="roberta@school.com"
        )
    )
    await service.create_student(
        StudentCreate(first_name="Alice", last_name="Robertson", student_number="STU022")
    )

    r1, t1 = await service.search_students("roberta")
    assert t1 == 1
    assert len(r1) == 1
    r2, t2 = await service.search_students("jones")
    assert t2 == 1
    assert len(r2) == 1
    r3, t3 = await service.search_students("STU022")
    assert t3 == 1
    assert len(r3) == 1


@pytest.mark.asyncio
async def test_repository_list_pagination(repo: StudentRepository, db_session: AsyncSession):
    for i in range(5):
        s = Student(
            first_name=f"Test{i}",
            last_name="User",
            student_number=f"STU{i:03d}",
            status="active",
        )
        db_session.add(s)
    await db_session.flush()

    students, total = await repo.list(skip=0, limit=2)
    assert total == 5
    assert len(students) == 2


@pytest.mark.asyncio
async def test_repository_search_pagination(repo: StudentRepository, db_session: AsyncSession):
    for i in range(5):
        s = Student(
            first_name=f"Page{i}",
            last_name="Test",
            student_number=f"PG{i:03d}",
            status="active",
        )
        db_session.add(s)
    await db_session.flush()

    results, total = await repo.search("Page", skip=0, limit=2)
    assert total == 5
    assert len(results) == 2