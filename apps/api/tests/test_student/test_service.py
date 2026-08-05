from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import StudentCreate, StudentUpdate
from app.domains.student.service import StudentService
from app.multi_tenant.models import platform_context


@pytest.fixture
def repo(db_session: AsyncSession) -> StudentRepository:
    return StudentRepository(db_session, platform_context())


@pytest.fixture
def service(repo: StudentRepository) -> StudentService:
    return StudentService(repo)


@pytest.mark.asyncio
async def test_create_student_success(service: StudentService):
    student = await service.create_student(
        StudentCreate(first_name="Alice", last_name="Smith", student_number="SVC001")
    )
    assert student.id is not None
    assert student.first_name == "Alice"
    assert student.status == "active"


@pytest.mark.asyncio
async def test_create_duplicate_raises_conflict(service: StudentService):
    await service.create_student(
        StudentCreate(first_name="Alice", last_name="Smith", student_number="SVC001")
    )
    with pytest.raises(ConflictError, match="already exists"):
        await service.create_student(
            StudentCreate(first_name="Bob", last_name="Jones", student_number="SVC001")
        )


@pytest.mark.asyncio
async def test_get_student_success(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="Charlie", last_name="Brown", student_number="SVC002")
    )
    retrieved = await service.get_student(created.id)
    assert retrieved.id == created.id
    assert retrieved.first_name == "Charlie"


@pytest.mark.asyncio
async def test_get_student_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_student(99999)


@pytest.mark.asyncio
async def test_update_student_success(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="Diana", last_name="Prince", student_number="SVC003")
    )
    updated = await service.update_student(
        created.id, StudentUpdate(first_name="Diana Updated")
    )
    assert updated.first_name == "Diana Updated"
    assert updated.last_name == "Prince"


@pytest.mark.asyncio
async def test_update_student_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.update_student(99999, StudentUpdate(first_name="Ghost"))


@pytest.mark.asyncio
async def test_delete_student_success(service: StudentService):
    created = await service.create_student(
        StudentCreate(first_name="Eve", last_name="Delete", student_number="SVC004")
    )
    await service.delete_student(created.id)
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_student(created.id)


@pytest.mark.asyncio
async def test_delete_student_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.delete_student(99999)


@pytest.mark.asyncio
async def test_list_students_empty(service: StudentService):
    students, total = await service.list_students()
    assert total == 0
    assert len(students) == 0


@pytest.mark.asyncio
async def test_list_students_pagination(service: StudentService):
    for i in range(3):
        await service.create_student(
            StudentCreate(
                first_name=f"User{i}", last_name="Test", student_number=f"SV{i:03d}"
            )
        )
    students, total = await service.list_students(skip=0, limit=2)
    assert total == 3
    assert len(students) == 2


@pytest.mark.asyncio
async def test_search_students_pagination(service: StudentService):
    for i in range(3):
        await service.create_student(
            StudentCreate(
                first_name=f"Search{i}", last_name="User", student_number=f"SR{i:03d}"
            )
        )
    results, total = await service.search_students("Search", skip=0, limit=2)
    assert total == 3
    assert len(results) == 2


@pytest.mark.asyncio
async def test_deactivate_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.deactivate_student(99999)


@pytest.mark.asyncio
async def test_reactivate_not_found(service: StudentService):
    with pytest.raises(NotFoundError, match="not found"):
        await service.reactivate_student(99999)


@pytest.mark.asyncio
async def test_list_invalid_status(service: StudentService):
    with pytest.raises(ValidationError, match="Invalid status filter"):
        await service.list_students(status="nonexistent")


@pytest.mark.asyncio
async def test_search_empty_query(service: StudentService):
    with pytest.raises(ValidationError, match="Search query is required"):
        await service.search_students("")