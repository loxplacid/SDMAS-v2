from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.academic.models import AcademicYear, Class
from app.domains.academic.repository import AcademicYearRepository, ClassRepository
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
def fee_type_repo(db_session: AsyncSession) -> FeeTypeRepository:
    return FeeTypeRepository(db_session)


@pytest.fixture
def fee_structure_repo(db_session: AsyncSession) -> FeeStructureRepository:
    return FeeStructureRepository(db_session)


@pytest.fixture
def fee_due_repo(db_session: AsyncSession) -> FeeDueRepository:
    return FeeDueRepository(db_session)


@pytest.fixture
def payment_repo(db_session: AsyncSession) -> PaymentRepository:
    return PaymentRepository(db_session)


@pytest.fixture
def student_repo(db_session: AsyncSession) -> StudentRepository:
    return StudentRepository(db_session)


@pytest.fixture
def year_repo(db_session: AsyncSession) -> AcademicYearRepository:
    return AcademicYearRepository(db_session)


@pytest.fixture
def class_repo(db_session: AsyncSession) -> ClassRepository:
    return ClassRepository(db_session)


@pytest.fixture
async def seed_fee_type(fee_type_repo: FeeTypeRepository) -> FeeType:
    return await fee_type_repo.create(FeeType(name="Tuition", description="Tuition fee"))


@pytest.fixture
async def seed_fee_structure(
    fee_structure_repo: FeeStructureRepository,
    year_repo: AcademicYearRepository,
    class_repo: ClassRepository,
    seed_fee_type: FeeType,
) -> FeeStructure:
    import datetime
    year = await year_repo.create(
        AcademicYear(
            name="FS Year", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31), status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    return await fee_structure_repo.create(
        FeeStructure(
            academic_year_id=year.id, class_id=cls.id,
            fee_type_id=seed_fee_type.id, amount=50000, frequency="annual",
        )
    )


# ---------------------------------------------------------------------------
# FeeTypeRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fee_type_create(fee_type_repo: FeeTypeRepository):
    ft = await fee_type_repo.create(FeeType(name="Library Fee"))
    assert ft.id is not None
    assert ft.name == "Library Fee"
    assert ft.status == "active"


@pytest.mark.asyncio
async def test_fee_type_get_by_id(fee_type_repo: FeeTypeRepository, seed_fee_type: FeeType):
    ft = await fee_type_repo.get_by_id(seed_fee_type.id)
    assert ft.id == seed_fee_type.id
    assert ft.name == "Tuition"


@pytest.mark.asyncio
async def test_fee_type_get_by_id_not_found(fee_type_repo: FeeTypeRepository):
    with pytest.raises(NotFoundError, match="not found"):
        await fee_type_repo.get_by_id(999)


@pytest.mark.asyncio
async def test_fee_type_get_by_name(fee_type_repo: FeeTypeRepository, seed_fee_type: FeeType):
    ft = await fee_type_repo.get_by_name("Tuition")
    assert ft is not None
    assert ft.id == seed_fee_type.id


@pytest.mark.asyncio
async def test_fee_type_exists_by_name(fee_type_repo: FeeTypeRepository, seed_fee_type: FeeType):
    assert await fee_type_repo.exists_by_name("Tuition") is True
    assert await fee_type_repo.exists_by_name("Nonexistent") is False


@pytest.mark.asyncio
async def test_fee_type_list(fee_type_repo: FeeTypeRepository):
    for name in ["A", "B", "C"]:
        await fee_type_repo.create(FeeType(name=name))
    items, total = await fee_type_repo.list()
    assert total >= 3


@pytest.mark.asyncio
async def test_fee_type_list_filter_by_status(fee_type_repo: FeeTypeRepository):
    ft = await fee_type_repo.create(FeeType(name="Test Inactive"))
    ft.status = "inactive"
    await fee_type_repo.update(ft)
    items, total = await fee_type_repo.list(status="inactive")
    assert total == 1
    assert items[0].name == "Test Inactive"


@pytest.mark.asyncio
async def test_fee_type_update(fee_type_repo: FeeTypeRepository, seed_fee_type: FeeType):
    ft = seed_fee_type
    ft.name = "Updated Tuition"
    updated = await fee_type_repo.update(ft)
    assert updated.name == "Updated Tuition"


@pytest.mark.asyncio
async def test_fee_type_delete(fee_type_repo: FeeTypeRepository, seed_fee_type: FeeType):
    ft_id = seed_fee_type.id
    await fee_type_repo.delete(seed_fee_type)
    await fee_type_repo.session.flush()
    with pytest.raises(NotFoundError, match="not found"):
        await fee_type_repo.get_by_id(ft_id)


# ---------------------------------------------------------------------------
# FeeStructureRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fee_structure_create(
    fee_structure_repo: FeeStructureRepository, seed_fee_type: FeeType,
    year_repo: AcademicYearRepository, class_repo: ClassRepository,
):
    import datetime
    year = await year_repo.create(
        AcademicYear(name="Struct Year", start_date=datetime.date(2026, 1, 1),
                      end_date=datetime.date(2026, 12, 31), status="active")
    )
    cls = await class_repo.create(Class(name="Grade 9", academic_year_id=year.id, status="active"))
    fs = await fee_structure_repo.create(
        FeeStructure(academic_year_id=year.id, class_id=cls.id,
                     fee_type_id=seed_fee_type.id, amount=30000, frequency="annual")
    )
    assert fs.id is not None
    assert fs.amount == 30000


@pytest.mark.asyncio
async def test_fee_structure_get_by_id(fee_structure_repo: FeeStructureRepository, seed_fee_structure: FeeStructure):
    fs = await fee_structure_repo.get_by_id(seed_fee_structure.id)
    assert fs.id == seed_fee_structure.id


@pytest.mark.asyncio
async def test_fee_structure_get_by_id_not_found(fee_structure_repo: FeeStructureRepository):
    with pytest.raises(NotFoundError, match="not found"):
        await fee_structure_repo.get_by_id(999)


@pytest.mark.asyncio
async def test_fee_structure_get_by_year_class_type(
    fee_structure_repo: FeeStructureRepository, seed_fee_structure: FeeStructure,
):
    fs = await fee_structure_repo.get_by_year_class_type(
        seed_fee_structure.academic_year_id, seed_fee_structure.class_id, seed_fee_structure.fee_type_id
    )
    assert fs is not None
    assert fs.id == seed_fee_structure.id


@pytest.mark.asyncio
async def test_fee_structure_list(fee_structure_repo: FeeStructureRepository):
    items, total = await fee_structure_repo.list()
    assert total >= 0


@pytest.mark.asyncio
async def test_fee_structure_get_by_year_class_type_not_found(
    fee_structure_repo: FeeStructureRepository,
):
    fs = await fee_structure_repo.get_by_year_class_type(999, 999, 999)
    assert fs is None


# ---------------------------------------------------------------------------
# FeeDueRepository
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_fee_due(
    fee_due_repo: FeeDueRepository,
    seed_fee_structure: FeeStructure,
    student_repo: StudentRepository,
) -> FeeDue:
    s = await student_repo.create(Student(first_name="Fee", last_name="Due", student_number="FD001", status="active"))
    return await fee_due_repo.create(
        FeeDue(
            student_id=s.id, academic_year_id=seed_fee_structure.academic_year_id,
            fee_structure_id=seed_fee_structure.id, original_amount=50000,
            amount_paid=0, status="unpaid",
        )
    )


@pytest.mark.asyncio
async def test_fee_due_create(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    assert seed_fee_due.id is not None
    assert seed_fee_due.original_amount == 50000
    assert seed_fee_due.amount_paid == 0
    assert seed_fee_due.status == "unpaid"


@pytest.mark.asyncio
async def test_fee_due_get_by_id(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    due = await fee_due_repo.get_by_id(seed_fee_due.id)
    assert due.id == seed_fee_due.id


@pytest.mark.asyncio
async def test_fee_due_get_by_id_not_found(fee_due_repo: FeeDueRepository):
    with pytest.raises(NotFoundError, match="not found"):
        await fee_due_repo.get_by_id(999)


@pytest.mark.asyncio
async def test_fee_due_get_by_student_and_structure(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    due = await fee_due_repo.get_by_student_and_structure(
        seed_fee_due.student_id, seed_fee_due.fee_structure_id
    )
    assert due is not None
    assert due.id == seed_fee_due.id


@pytest.mark.asyncio
async def test_fee_due_list(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    items, total = await fee_due_repo.list()
    assert total >= 1


@pytest.mark.asyncio
async def test_fee_due_find_by_student(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    dues = await fee_due_repo.find_by_student(seed_fee_due.student_id)
    assert len(dues) >= 1


@pytest.mark.asyncio
async def test_fee_due_find_by_student_filter_status(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    dues = await fee_due_repo.find_by_student(seed_fee_due.student_id, status="unpaid")
    assert len(dues) >= 1


@pytest.mark.asyncio
async def test_fee_due_find_by_student_empty(fee_due_repo: FeeDueRepository):
    dues = await fee_due_repo.find_by_student(999)
    assert len(dues) == 0


@pytest.mark.asyncio
async def test_fee_due_find_by_academic_year(fee_due_repo: FeeDueRepository, seed_fee_due: FeeDue):
    dues = await fee_due_repo.find_by_academic_year(seed_fee_due.academic_year_id)
    assert len(dues) >= 1


# ---------------------------------------------------------------------------
# PaymentRepository
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_payment(
    payment_repo: PaymentRepository,
    seed_fee_due: FeeDue,
    student_repo: StudentRepository,
) -> Payment:
    s = await student_repo.get_by_id(seed_fee_due.student_id)
    return await payment_repo.create(
        Payment(
            student_id=s.id, fee_due_id=seed_fee_due.id, amount=25000,
            payment_date="2026-03-15", payment_method="cash",
            receipt_number="RCP001",
        )
    )


@pytest.mark.asyncio
async def test_payment_create(payment_repo: PaymentRepository, seed_payment: Payment):
    assert seed_payment.id is not None
    assert seed_payment.amount == 25000
    assert seed_payment.receipt_number == "RCP001"


@pytest.mark.asyncio
async def test_payment_get_by_id(payment_repo: PaymentRepository, seed_payment: Payment):
    p = await payment_repo.get_by_id(seed_payment.id)
    assert p.id == seed_payment.id


@pytest.mark.asyncio
async def test_payment_get_by_id_not_found(payment_repo: PaymentRepository):
    with pytest.raises(NotFoundError, match="not found"):
        await payment_repo.get_by_id(999)


@pytest.mark.asyncio
async def test_payment_get_by_receipt_number(payment_repo: PaymentRepository, seed_payment: Payment):
    p = await payment_repo.get_by_receipt_number("RCP001")
    assert p is not None
    assert p.id == seed_payment.id


@pytest.mark.asyncio
async def test_payment_get_by_receipt_number_not_found(payment_repo: PaymentRepository):
    p = await payment_repo.get_by_receipt_number("NONEXISTENT")
    assert p is None


@pytest.mark.asyncio
async def test_payment_list(payment_repo: PaymentRepository, seed_payment: Payment):
    items, total = await payment_repo.list()
    assert total >= 1


@pytest.mark.asyncio
async def test_payment_find_by_student(payment_repo: PaymentRepository, seed_payment: Payment):
    payments = await payment_repo.find_by_student(seed_payment.student_id)
    assert len(payments) >= 1


@pytest.mark.asyncio
async def test_payment_find_by_fee_due(payment_repo: PaymentRepository, seed_payment: Payment):
    payments = await payment_repo.find_by_fee_due(seed_payment.fee_due_id)
    assert len(payments) >= 1


@pytest.mark.asyncio
async def test_payment_find_by_date_range(payment_repo: PaymentRepository, seed_payment: Payment):
    payments = await payment_repo.find_by_date_range("2026-01-01", "2026-12-31")
    assert len(payments) >= 1