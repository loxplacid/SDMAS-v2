from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.academic.models import (
    AcademicYear,
    Class,
    Section,
    Enrollment,
    Teacher,
    Subject,
    Term,
    TeacherAssignment,
)
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
    TermRepository,
    SubjectRepository,
    TeacherRepository,
    TeacherAssignmentRepository,
)
from app.domains.academic.schemas import (
    AcademicYearCreate,
    AcademicYearUpdate,
    ClassCreate,
    ClassUpdate,
    SectionCreate,
    SectionUpdate,
    EnrollmentCreate,
    EnrollmentUpdate,
    TermCreate,
    TermUpdate,
    SubjectCreate,
    SubjectUpdate,
    TeacherCreate,
    TeacherUpdate,
    TeacherAssignmentCreate,
)
from app.domains.academic.service import (
    AcademicYearService,
    ClassService,
    SectionService,
    EnrollmentService,
    TermService,
    SubjectService,
    TeacherService,
    TeacherAssignmentService,
)
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import platform_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def student_repo(db_session: AsyncSession) -> StudentRepository:
    return StudentRepository(db_session, platform_context())


@pytest.fixture
def year_service(year_repo: AcademicYearRepository) -> AcademicYearService:
    return AcademicYearService(year_repo)


@pytest.fixture
def class_service(
    class_repo: ClassRepository, year_repo: AcademicYearRepository
) -> ClassService:
    return ClassService(class_repo, year_repo)


@pytest.fixture
def section_service(
    section_repo: SectionRepository, class_repo: ClassRepository
) -> SectionService:
    return SectionService(section_repo, class_repo)


@pytest.fixture
def enrollment_service(
    enrollment_repo: EnrollmentRepository,
    year_repo: AcademicYearRepository,
    class_repo: ClassRepository,
    section_repo: SectionRepository,
    student_repo: StudentRepository,
) -> EnrollmentService:
    return EnrollmentService(
        enrollment_repo, year_repo, class_repo, section_repo, student_repo
    )


@pytest.fixture
async def seeded_year(year_service: AcademicYearService) -> AcademicYear:
    return await year_service.create_year(
        AcademicYearCreate(
            name="2026-2027",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
        )
    )


@pytest.fixture
async def seeded_class(
    class_service: ClassService, seeded_year: AcademicYear
) -> Class:
    return await class_service.create_class(
        ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
    )


@pytest.fixture
async def seeded_section(
    section_service: SectionService, seeded_class: Class
) -> Section:
    return await section_service.create_section(
        SectionCreate(name="A", class_id=seeded_class.id)
    )


@pytest.fixture
async def seeded_student(
    db_session: AsyncSession,
) -> Student:
    repo = StudentRepository(db_session, platform_context())
    s = Student(
        first_name="Test",
        last_name="Student",
        student_number="ENR001",
        status="active",
    )
    return await repo.create(s)


@pytest.fixture
def term_repo(db_session: AsyncSession) -> TermRepository:
    return TermRepository(db_session, platform_context())


@pytest.fixture
def subject_repo(db_session: AsyncSession) -> SubjectRepository:
    return SubjectRepository(db_session, platform_context())


@pytest.fixture
def teacher_repo(db_session: AsyncSession) -> TeacherRepository:
    return TeacherRepository(db_session, platform_context())


@pytest.fixture
def assignment_repo(db_session: AsyncSession) -> TeacherAssignmentRepository:
    return TeacherAssignmentRepository(db_session, platform_context())


@pytest.fixture
def term_service(
    term_repo: TermRepository, year_repo: AcademicYearRepository
) -> TermService:
    return TermService(term_repo, year_repo)


@pytest.fixture
def subject_service(
    subject_repo: SubjectRepository,
) -> SubjectService:
    return SubjectService(subject_repo)


@pytest.fixture
def teacher_service(
    teacher_repo: TeacherRepository,
) -> TeacherService:
    return TeacherService(teacher_repo)


@pytest.fixture
def assignment_service(
    assignment_repo: TeacherAssignmentRepository,
    teacher_repo: TeacherRepository,
    class_repo: ClassRepository,
    subject_repo: SubjectRepository,
) -> TeacherAssignmentService:
    return TeacherAssignmentService(
        assignment_repo, teacher_repo, class_repo, subject_repo
    )


# ===========================================================================
# ACADEMIC YEAR TESTS
# ===========================================================================

class TestAcademicYearCreate:
    @pytest.mark.asyncio
    async def test_create_valid(self, year_service: AcademicYearService):
        year = await year_service.create_year(
            AcademicYearCreate(
                name="2026-2027",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 12, 31),
            )
        )
        assert year.id is not None
        assert year.name == "2026-2027"
        assert year.status == "active"
        assert year.start_date == datetime.date(2026, 1, 1)
        assert year.end_date == datetime.date(2026, 12, 31)

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, year_service: AcademicYearService):
        await year_service.create_year(
            AcademicYearCreate(
                name="2026-2027",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 12, 31),
            )
        )
        with pytest.raises(ConflictError, match="already exists"):
            await year_service.create_year(
                AcademicYearCreate(
                    name="2026-2027",
                    start_date=datetime.date(2027, 1, 1),
                    end_date=datetime.date(2027, 12, 31),
                )
            )

    @pytest.mark.asyncio
    async def test_create_end_before_start(self):
        with pytest.raises(ValueError, match="end_date must be after start_date"):
            AcademicYearCreate(
                name="Bad",
                start_date=datetime.date(2026, 12, 31),
                end_date=datetime.date(2026, 1, 1),
            )

    @pytest.mark.asyncio
    async def test_create_empty_name(self):
        with pytest.raises(ValueError, match="empty"):
            AcademicYearCreate(
                name="   ",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 12, 31),
            )


class TestAcademicYearGet:
    @pytest.mark.asyncio
    async def test_get_by_id(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        found = await year_service.get_year(seeded_year.id)
        assert found.id == seeded_year.id
        assert found.name == "2026-2027"

    @pytest.mark.asyncio
    async def test_get_not_found(self, year_service: AcademicYearService):
        with pytest.raises(NotFoundError, match="not found"):
            await year_service.get_year(99999)


class TestAcademicYearUpdate:
    @pytest.mark.asyncio
    async def test_update_name(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        updated = await year_service.update_year(
            seeded_year.id, AcademicYearUpdate(name="2027-2028")
        )
        assert updated.name == "2027-2028"

    @pytest.mark.asyncio
    async def test_update_duplicate_name(self, year_service: AcademicYearService):
        await year_service.create_year(
            AcademicYearCreate(
                name="Year A",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 12, 31),
            )
        )
        year_b = await year_service.create_year(
            AcademicYearCreate(
                name="Year B",
                start_date=datetime.date(2027, 1, 1),
                end_date=datetime.date(2027, 12, 31),
            )
        )
        with pytest.raises(ConflictError, match="already exists"):
            await year_service.update_year(
                year_b.id, AcademicYearUpdate(name="Year A")
            )

    @pytest.mark.asyncio
    async def test_update_status(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        deactivated = await year_service.deactivate_year(seeded_year.id)
        assert deactivated.status == "inactive"
        reactivated = await year_service.reactivate_year(seeded_year.id)
        assert reactivated.status == "active"

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        await year_service.deactivate_year(seeded_year.id)
        with pytest.raises(ConflictError, match="already inactive"):
            await year_service.deactivate_year(seeded_year.id)

    @pytest.mark.asyncio
    async def test_reactivate_already_active(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        with pytest.raises(ConflictError, match="already active"):
            await year_service.reactivate_year(seeded_year.id)


class TestAcademicYearList:
    @pytest.mark.asyncio
    async def test_list_all(self, year_service: AcademicYearService):
        await year_service.create_year(
            AcademicYearCreate(
                name="Y1", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 12, 31)
            )
        )
        await year_service.create_year(
            AcademicYearCreate(
                name="Y2", start_date=datetime.date(2027, 1, 1), end_date=datetime.date(2027, 12, 31)
            )
        )
        years, total = await year_service.list_years()
        assert total == 2
        assert len(years) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        await year_service.deactivate_year(seeded_year.id)
        active, total_active = await year_service.list_years(status="active")
        assert total_active == 0
        inactive, total_inactive = await year_service.list_years(status="inactive")
        assert total_inactive == 1

    @pytest.mark.asyncio
    async def test_list_invalid_status(self, year_service: AcademicYearService):
        with pytest.raises(ValidationError, match="Invalid status filter"):
            await year_service.list_years(status="bogus")

    @pytest.mark.asyncio
    async def test_pagination(self, year_service: AcademicYearService):
        for i in range(3):
            await year_service.create_year(
                AcademicYearCreate(
                    name=f"Y{i}",
                    start_date=datetime.date(2026 + i, 1, 1),
                    end_date=datetime.date(2026 + i, 12, 31),
                )
            )
        years, total = await year_service.list_years(skip=0, limit=2)
        assert total == 3
        assert len(years) == 2


class TestAcademicYearDelete:
    @pytest.mark.asyncio
    async def test_delete_year(self, year_service: AcademicYearService, seeded_year: AcademicYear):
        await year_service.delete_year(seeded_year.id)
        with pytest.raises(NotFoundError):
            await year_service.get_year(seeded_year.id)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, year_service: AcademicYearService):
        with pytest.raises(NotFoundError):
            await year_service.delete_year(99999)


# ===========================================================================
# CLASS TESTS
# ===========================================================================

class TestClassCreate:
    @pytest.mark.asyncio
    async def test_create_valid(self, class_service: ClassService, seeded_year: AcademicYear):
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        assert cls.id is not None
        assert cls.name == "Grade 10"
        assert cls.academic_year_id == seeded_year.id
        assert cls.status == "active"

    @pytest.mark.asyncio
    async def test_create_duplicate_in_year(self, class_service: ClassService, seeded_year: AcademicYear):
        await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        with pytest.raises(ConflictError, match="already exists"):
            await class_service.create_class(
                ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
            )

    @pytest.mark.asyncio
    async def test_create_same_name_diff_year(self, class_service: ClassService):
        y1_data = AcademicYearCreate(
            name="AY1", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 12, 31)
        )
        y2_data = AcademicYearCreate(
            name="AY2", start_date=datetime.date(2027, 1, 1), end_date=datetime.date(2027, 12, 31)
        )
        year_svc = AcademicYearService(
            AcademicYearRepository(class_service.repo.session, platform_context())
        )
        y1 = await year_svc.create_year(y1_data)
        y2 = await year_svc.create_year(y2_data)

        c1 = await class_service.create_class(ClassCreate(name="Grade 10", academic_year_id=y1.id))
        assert c1.id is not None
        c2 = await class_service.create_class(ClassCreate(name="Grade 10", academic_year_id=y2.id))
        assert c2.id is not None
        assert c1.id != c2.id

    @pytest.mark.asyncio
    async def test_create_nonexistent_year(self, class_service: ClassService):
        with pytest.raises(NotFoundError):
            await class_service.create_class(ClassCreate(name="Grade 10", academic_year_id=99999))


class TestClassUpdate:
    @pytest.mark.asyncio
    async def test_update_name(self, class_service: ClassService, seeded_class: Class):
        updated = await class_service.update_class(
            seeded_class.id, ClassUpdate(name="Grade 11")
        )
        assert updated.name == "Grade 11"

    @pytest.mark.asyncio
    async def test_duplicate_name_in_year(self, class_service: ClassService, seeded_year: AcademicYear, seeded_class: Class):
        await class_service.create_class(
            ClassCreate(name="Grade 11", academic_year_id=seeded_year.id)
        )
        with pytest.raises(ConflictError, match="already exists"):
            await class_service.update_class(
                seeded_class.id, ClassUpdate(name="Grade 11")
            )

    @pytest.mark.asyncio
    async def test_deactivate_reactivate(self, class_service: ClassService, seeded_class: Class):
        d = await class_service.deactivate_class(seeded_class.id)
        assert d.status == "inactive"
        r = await class_service.reactivate_class(seeded_class.id)
        assert r.status == "active"

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive(self, class_service: ClassService, seeded_class: Class):
        await class_service.deactivate_class(seeded_class.id)
        with pytest.raises(ConflictError, match="already inactive"):
            await class_service.deactivate_class(seeded_class.id)

    @pytest.mark.asyncio
    async def test_reactivate_already_active(self, class_service: ClassService, seeded_class: Class):
        with pytest.raises(ConflictError, match="already active"):
            await class_service.reactivate_class(seeded_class.id)


class TestClassList:
    @pytest.mark.asyncio
    async def test_list_by_year(self, class_service: ClassService, seeded_year: AcademicYear, seeded_class: Class):
        classes, total = await class_service.list_classes(year_id=seeded_year.id)
        assert total >= 1
        assert any(c.id == seeded_class.id for c in classes)

    @pytest.mark.asyncio
    async def test_list_all(self, class_service: ClassService, seeded_year: AcademicYear, seeded_class: Class):
        classes, total = await class_service.list_classes()
        assert total >= 1


class TestClassDelete:
    @pytest.mark.asyncio
    async def test_delete_class(self, class_service: ClassService, seeded_class: Class):
        await class_service.delete_class(seeded_class.id)
        with pytest.raises(NotFoundError):
            await class_service.get_class(seeded_class.id)


# ===========================================================================
# SECTION TESTS
# ===========================================================================

class TestSectionCreate:
    @pytest.mark.asyncio
    async def test_create_valid(self, section_service: SectionService, seeded_class: Class):
        section = await section_service.create_section(
            SectionCreate(name="A", class_id=seeded_class.id)
        )
        assert section.id is not None
        assert section.name == "A"
        assert section.class_id == seeded_class.id
        assert section.status == "active"

    @pytest.mark.asyncio
    async def test_duplicate_in_class(self, section_service: SectionService, seeded_class: Class):
        await section_service.create_section(SectionCreate(name="A", class_id=seeded_class.id))
        with pytest.raises(ConflictError, match="already exists"):
            await section_service.create_section(SectionCreate(name="A", class_id=seeded_class.id))

    @pytest.mark.asyncio
    async def test_same_name_diff_class(self, section_service: SectionService, seeded_year: AcademicYear, seeded_class: Class):
        c2 = await ClassService(
            ClassRepository(section_service.repo.session, platform_context()),
            AcademicYearRepository(section_service.repo.session, platform_context()),
        ).create_class(ClassCreate(name="Grade 11", academic_year_id=seeded_year.id))

        s1 = await section_service.create_section(SectionCreate(name="A", class_id=seeded_class.id))
        s2 = await section_service.create_section(SectionCreate(name="A", class_id=c2.id))
        assert s1.id != s2.id

    @pytest.mark.asyncio
    async def test_nonexistent_class(self, section_service: SectionService):
        with pytest.raises(NotFoundError):
            await section_service.create_section(SectionCreate(name="A", class_id=99999))


class TestSectionUpdate:
    @pytest.mark.asyncio
    async def test_update_name(self, section_service: SectionService, seeded_section: Section):
        updated = await section_service.update_section(
            seeded_section.id, SectionUpdate(name="B")
        )
        assert updated.name == "B"

    @pytest.mark.asyncio
    async def test_deactivate_reactivate(self, section_service: SectionService, seeded_section: Section):
        d = await section_service.deactivate_section(seeded_section.id)
        assert d.status == "inactive"
        r = await section_service.reactivate_section(seeded_section.id)
        assert r.status == "active"


class TestSectionList:
    @pytest.mark.asyncio
    async def test_list_by_class(self, section_service: SectionService, seeded_class: Class, seeded_section: Section):
        sections, total = await section_service.list_sections(class_id=seeded_class.id)
        assert total >= 1
        assert any(s.id == seeded_section.id for s in sections)


class TestSectionDelete:
    @pytest.mark.asyncio
    async def test_delete_section(self, section_service: SectionService, seeded_section: Section):
        await section_service.delete_section(seeded_section.id)
        with pytest.raises(NotFoundError):
            await section_service.get_section(seeded_section.id)


# ===========================================================================
# ENROLLMENT TESTS
# ===========================================================================

class TestEnrollmentCreate:
    @pytest.mark.asyncio
    async def test_create_valid(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear, seeded_student: Student
    ):
        enrollment = await enrollment_service.create_enrollment(
            EnrollmentCreate(
                student_id=seeded_student.id,
                academic_year_id=seeded_year.id,
            )
        )
        assert enrollment.id is not None
        assert enrollment.student_id == seeded_student.id
        assert enrollment.academic_year_id == seeded_year.id
        assert enrollment.class_id is None
        assert enrollment.section_id is None
        assert enrollment.status == "active"

    @pytest.mark.asyncio
    async def test_create_with_class_and_section(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear,
        seeded_class: Class, seeded_section: Section, seeded_student: Student
    ):
        enrollment = await enrollment_service.create_enrollment(
            EnrollmentCreate(
                student_id=seeded_student.id,
                academic_year_id=seeded_year.id,
                class_id=seeded_class.id,
                section_id=seeded_section.id,
            )
        )
        assert enrollment.class_id == seeded_class.id
        assert enrollment.section_id == seeded_section.id

    @pytest.mark.asyncio
    async def test_duplicate_enrollment(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear, seeded_student: Student
    ):
        await enrollment_service.create_enrollment(
            EnrollmentCreate(
                student_id=seeded_student.id,
                academic_year_id=seeded_year.id,
            )
        )
        with pytest.raises(ConflictError, match="already enrolled"):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(
                    student_id=seeded_student.id,
                    academic_year_id=seeded_year.id,
                )
            )

    @pytest.mark.asyncio
    async def test_nonexistent_student(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear
    ):
        with pytest.raises(NotFoundError):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(student_id=99999, academic_year_id=seeded_year.id)
            )

    @pytest.mark.asyncio
    async def test_nonexistent_academic_year(
        self, enrollment_service: EnrollmentService, seeded_student: Student
    ):
        with pytest.raises(NotFoundError):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(student_id=seeded_student.id, academic_year_id=99999)
            )

    @pytest.mark.asyncio
    async def test_inactive_student(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear, db_session: AsyncSession
    ):
        repo = StudentRepository(db_session, platform_context())
        s = Student(first_name="Inactive", last_name="Student", student_number="INACTIVE", status="inactive")
        await repo.create(s)
        with pytest.raises(ValidationError, match="inactive student"):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(student_id=s.id, academic_year_id=seeded_year.id)
            )

    @pytest.mark.asyncio
    async def test_inactive_academic_year(
        self, enrollment_service: EnrollmentService, seeded_student: Student, seeded_year: AcademicYear, year_service: AcademicYearService
    ):
        await year_service.deactivate_year(seeded_year.id)
        with pytest.raises(ValidationError, match="inactive academic year"):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(student_id=seeded_student.id, academic_year_id=seeded_year.id)
            )

    @pytest.mark.asyncio
    async def test_inactive_class(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear,
        seeded_class: Class, seeded_student: Student, class_service: ClassService
    ):
        await class_service.deactivate_class(seeded_class.id)
        with pytest.raises(ValidationError, match="inactive class"):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(
                    student_id=seeded_student.id, academic_year_id=seeded_year.id,
                    class_id=seeded_class.id,
                )
            )

    @pytest.mark.asyncio
    async def test_class_wrong_year(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear,
        seeded_class: Class, seeded_student: Student, year_service: AcademicYearService
    ):
        year2 = await year_service.create_year(
            AcademicYearCreate(
                name="Other Year",
                start_date=datetime.date(2027, 1, 1),
                end_date=datetime.date(2027, 12, 31),
            )
        )
        with pytest.raises(ValidationError, match="does not belong"):
            await enrollment_service.create_enrollment(
                EnrollmentCreate(
                    student_id=seeded_student.id, academic_year_id=year2.id,
                    class_id=seeded_class.id,
                )
            )

    @pytest.mark.asyncio
    async def test_enroll_in_different_years(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear,
        seeded_student: Student, year_service: AcademicYearService
    ):
        year2 = await year_service.create_year(
            AcademicYearCreate(
                name="AY2",
                start_date=datetime.date(2027, 1, 1),
                end_date=datetime.date(2027, 12, 31),
            )
        )
        e1 = await enrollment_service.create_enrollment(
            EnrollmentCreate(student_id=seeded_student.id, academic_year_id=seeded_year.id)
        )
        e2 = await enrollment_service.create_enrollment(
            EnrollmentCreate(student_id=seeded_student.id, academic_year_id=year2.id)
        )
        assert e1.id != e2.id


class TestEnrollmentUpdate:
    @pytest.mark.asyncio
    async def test_update_class(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear,
        seeded_student: Student, class_service: ClassService
    ):
        c2 = await class_service.create_class(
            ClassCreate(name="Grade 11", academic_year_id=seeded_year.id)
        )
        enrollment = await enrollment_service.create_enrollment(
            EnrollmentCreate(student_id=seeded_student.id, academic_year_id=seeded_year.id)
        )
        updated = await enrollment_service.update_enrollment(
            enrollment.id, EnrollmentUpdate(class_id=c2.id)
        )
        assert updated.class_id == c2.id


class TestEnrollmentDelete:
    @pytest.mark.asyncio
    async def test_delete_enrollment(
        self, enrollment_service: EnrollmentService, seeded_year: AcademicYear, seeded_student: Student
    ):
        enrollment = await enrollment_service.create_enrollment(
            EnrollmentCreate(student_id=seeded_student.id, academic_year_id=seeded_year.id)
        )
        await enrollment_service.delete_enrollment(enrollment.id)
        with pytest.raises(NotFoundError):
            await enrollment_service.get_enrollment(enrollment.id)


# ===========================================================================
# TERM TESTS
# ===========================================================================


class TestTermService:
    @pytest.mark.asyncio
    async def test_create_term(
        self, term_service: TermService, seeded_year: AcademicYear
    ):
        term = await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
        )
        assert term.id is not None
        assert term.name == "Term 1"
        assert term.academic_year_id == seeded_year.id
        assert term.status == "active"

    @pytest.mark.asyncio
    async def test_create_duplicate_name_allowed_if_not_overlapping(
        self, term_service: TermService, seeded_year: AcademicYear
    ):
        await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
        )
        # Same name but non-overlapping dates - allowed
        term2 = await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-04-01",
                end_date="2026-06-30",
            ),
        )
        assert term2.id is not None

    @pytest.mark.asyncio
    async def test_overlapping_terms(
        self, term_service: TermService, seeded_year: AcademicYear
    ):
        await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-01-01",
                end_date="2026-06-30",
            ),
        )
        with pytest.raises(ConflictError, match="overlaps"):
            await term_service.create_term(
                seeded_year.id,
                TermCreate(
                    name="Term 2",
                    start_date="2026-03-01",
                    end_date="2026-09-30",
                ),
            )

    @pytest.mark.asyncio
    async def test_get_term(
        self, term_service: TermService, seeded_year: AcademicYear
    ):
        term = await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
        )
        found = await term_service.get_term(term.id)
        assert found.name == "Term 1"

    @pytest.mark.asyncio
    async def test_get_term_not_found(self, term_service: TermService):
        with pytest.raises(NotFoundError):
            await term_service.get_term(99999)

    @pytest.mark.asyncio
    async def test_list_terms_by_year(
        self, term_service: TermService, seeded_year: AcademicYear
    ):
        await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
        )
        await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 2",
                start_date="2026-04-01",
                end_date="2026-06-30",
            ),
        )
        terms, total = await term_service.list_terms(year_id=seeded_year.id)
        assert total == 2

    @pytest.mark.asyncio
    async def test_update_term_name(
        self, term_service: TermService, seeded_year: AcademicYear
    ):
        term = await term_service.create_term(
            seeded_year.id,
            TermCreate(
                name="Term 1",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
        )
        updated = await term_service.update_term(
            term.id, TermUpdate(name="First Term")
        )
        assert updated.name == "First Term"

    @pytest.mark.asyncio
    async def test_create_term_invalid_year(
        self, term_service: TermService
    ):
        with pytest.raises(NotFoundError):
            await term_service.create_term(
                99999,
                TermCreate(
                    name="Bad",
                    start_date="2026-01-01",
                    end_date="2026-03-31",
                ),
            )


# ===========================================================================
# SUBJECT TESTS
# ===========================================================================


class TestSubjectService:
    @pytest.mark.asyncio
    async def test_create_subject(self, subject_service: SubjectService):
        subject = await subject_service.create_subject(
            SubjectCreate(name="Mathematics", code="MATH101")
        )
        assert subject.id is not None
        assert subject.name == "Mathematics"
        assert subject.code == "MATH101"
        assert subject.status == "active"

    @pytest.mark.asyncio
    async def test_create_duplicate_name(
        self, subject_service: SubjectService
    ):
        await subject_service.create_subject(
            SubjectCreate(name="Mathematics", code="MATH101")
        )
        with pytest.raises(ConflictError, match="already exists"):
            await subject_service.create_subject(
                SubjectCreate(name="Mathematics", code="MATH102")
            )

    @pytest.mark.asyncio
    async def test_create_duplicate_code(
        self, subject_service: SubjectService
    ):
        await subject_service.create_subject(
            SubjectCreate(name="Mathematics", code="MATH101")
        )
        with pytest.raises(ConflictError, match="already exists"):
            await subject_service.create_subject(
                SubjectCreate(name="Algebra", code="MATH101")
            )

    @pytest.mark.asyncio
    async def test_get_subject(self, subject_service: SubjectService):
        subject = await subject_service.create_subject(
            SubjectCreate(name="Science", code="SCI101")
        )
        found = await subject_service.get_subject(subject.id)
        assert found.name == "Science"

    @pytest.mark.asyncio
    async def test_get_not_found(self, subject_service: SubjectService):
        with pytest.raises(NotFoundError):
            await subject_service.get_subject(99999)

    @pytest.mark.asyncio
    async def test_list_subjects(self, subject_service: SubjectService):
        await subject_service.create_subject(
            SubjectCreate(name="Math", code="MATH101")
        )
        await subject_service.create_subject(
            SubjectCreate(name="Science", code="SCI101")
        )
        subjects, total = await subject_service.list_subjects()
        assert total == 2

    @pytest.mark.asyncio
    async def test_update_subject(self, subject_service: SubjectService):
        subject = await subject_service.create_subject(
            SubjectCreate(name="Math", code="MATH101")
        )
        updated = await subject_service.update_subject(
            subject.id, SubjectUpdate(name="Advanced Math")
        )
        assert updated.name == "Advanced Math"


# ===========================================================================
# TEACHER TESTS
# ===========================================================================


class TestTeacherService:
    @pytest.mark.asyncio
    async def test_create_teacher(self, teacher_service: TeacherService):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP001",
                email="john@school.com",
            )
        )
        assert teacher.id is not None
        assert teacher.first_name == "John"
        assert teacher.last_name == "Doe"
        assert teacher.employee_number == "EMP001"
        assert teacher.email == "john@school.com"
        assert teacher.status == "active"

    @pytest.mark.asyncio
    async def test_create_duplicate_employee_number(
        self, teacher_service: TeacherService
    ):
        await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP001",
            )
        )
        with pytest.raises(ConflictError, match="already exists"):
            await teacher_service.create_teacher(
                TeacherCreate(
                    first_name="Jane",
                    last_name="Smith",
                    employee_number="EMP001",
                )
            )

    @pytest.mark.asyncio
    async def test_get_teacher(self, teacher_service: TeacherService):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="Jane", last_name="Smith", employee_number="EMP002"
            )
        )
        found = await teacher_service.get_teacher(teacher.id)
        assert found.first_name == "Jane"

    @pytest.mark.asyncio
    async def test_get_not_found(self, teacher_service: TeacherService):
        with pytest.raises(NotFoundError):
            await teacher_service.get_teacher(99999)

    @pytest.mark.asyncio
    async def test_list_teachers(self, teacher_service: TeacherService):
        await teacher_service.create_teacher(
            TeacherCreate(
                first_name="A", last_name="B", employee_number="EMP010"
            )
        )
        await teacher_service.create_teacher(
            TeacherCreate(
                first_name="C", last_name="D", employee_number="EMP011"
            )
        )
        teachers, total = await teacher_service.list_teachers()
        assert total == 2

    @pytest.mark.asyncio
    async def test_update_teacher(self, teacher_service: TeacherService):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="Original",
                last_name="Name",
                employee_number="EMP020",
            )
        )
        updated = await teacher_service.update_teacher(
            teacher.id, TeacherUpdate(first_name="Updated")
        )
        assert updated.first_name == "Updated"


# ===========================================================================
# TEACHER ASSIGNMENT TESTS
# ===========================================================================


class TestTeacherAssignmentService:
    @pytest.mark.asyncio
    async def test_assign_teacher(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        subject_service: SubjectService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP100",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        subject = await subject_service.create_subject(
            SubjectCreate(name="Math", code="MATH100")
        )

        assignment = await assignment_service.assign_teacher(
            TeacherAssignmentCreate(
                teacher_id=teacher.id,
                class_id=cls.id,
                subject_id=subject.id,
            )
        )
        assert assignment.id is not None
        assert assignment.teacher_id == teacher.id
        assert assignment.class_id == cls.id
        assert assignment.subject_id == subject.id
        assert assignment.status == "active"

    @pytest.mark.asyncio
    async def test_assign_without_subject(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="Jane",
                last_name="Doe",
                employee_number="EMP101",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 11", academic_year_id=seeded_year.id)
        )

        assignment = await assignment_service.assign_teacher(
            TeacherAssignmentCreate(
                teacher_id=teacher.id,
                class_id=cls.id,
            )
        )
        assert assignment.subject_id is None

    @pytest.mark.asyncio
    async def test_duplicate_assignment(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        subject_service: SubjectService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP102",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        subject = await subject_service.create_subject(
            SubjectCreate(name="Physics", code="PHY100")
        )
        await assignment_service.assign_teacher(
            TeacherAssignmentCreate(
                teacher_id=teacher.id,
                class_id=cls.id,
                subject_id=subject.id,
            )
        )
        with pytest.raises(ConflictError, match="already assigned"):
            await assignment_service.assign_teacher(
                TeacherAssignmentCreate(
                    teacher_id=teacher.id,
                    class_id=cls.id,
                    subject_id=subject.id,
                )
            )

    @pytest.mark.asyncio
    async def test_unassign(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP103",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        assignment = await assignment_service.assign_teacher(
            TeacherAssignmentCreate(
                teacher_id=teacher.id,
                class_id=cls.id,
            )
        )
        await assignment_service.unassign(assignment.id)
        with pytest.raises(NotFoundError):
            await assignment_service.get_assignment(assignment.id)

    @pytest.mark.asyncio
    async def test_list_by_class(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP104",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        await assignment_service.assign_teacher(
            TeacherAssignmentCreate(
                teacher_id=teacher.id,
                class_id=cls.id,
            )
        )
        assignments, total = await assignment_service.list_assignments(
            class_id=cls.id
        )
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_by_teacher(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP105",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        await assignment_service.assign_teacher(
            TeacherAssignmentCreate(
                teacher_id=teacher.id,
                class_id=cls.id,
            )
        )
        assignments, total = await assignment_service.list_assignments(
            teacher_id=teacher.id
        )
        assert total == 1

    @pytest.mark.asyncio
    async def test_assign_inactive_teacher(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP106",
            )
        )
        await teacher_service.update_teacher(
            teacher.id, TeacherUpdate(status="inactive")
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        with pytest.raises(ValidationError, match="inactive teacher"):
            await assignment_service.assign_teacher(
                TeacherAssignmentCreate(
                    teacher_id=teacher.id,
                    class_id=cls.id,
                )
            )

    @pytest.mark.asyncio
    async def test_assign_to_inactive_class(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP107",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        await class_service.deactivate_class(cls.id)
        with pytest.raises(ValidationError, match="inactive class"):
            await assignment_service.assign_teacher(
                TeacherAssignmentCreate(
                    teacher_id=teacher.id,
                    class_id=cls.id,
                )
            )

    @pytest.mark.asyncio
    async def test_inactive_subject(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_service: TeacherService,
        subject_service: SubjectService,
        seeded_year: AcademicYear,
        class_service: ClassService,
    ):
        teacher = await teacher_service.create_teacher(
            TeacherCreate(
                first_name="John",
                last_name="Doe",
                employee_number="EMP108",
            )
        )
        cls = await class_service.create_class(
            ClassCreate(name="Grade 10", academic_year_id=seeded_year.id)
        )
        subject = await subject_service.create_subject(
            SubjectCreate(name="Chemistry", code="CHEM100")
        )
        await subject_service.update_subject(
            subject.id, SubjectUpdate(status="inactive")
        )
        with pytest.raises(ValidationError, match="inactive subject"):
            await assignment_service.assign_teacher(
                TeacherAssignmentCreate(
                    teacher_id=teacher.id,
                    class_id=cls.id,
                    subject_id=subject.id,
                )
            )