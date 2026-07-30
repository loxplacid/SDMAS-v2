from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.academic.models import (
    AcademicYear,
    Class,
    Section,
    Enrollment,
    Term,
    Subject,
    Teacher,
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
    VALID_ACADEMIC_STATUSES,
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
from app.domains.student.repository import StudentRepository


# ---------------------------------------------------------------------------
# AcademicYearService
# ---------------------------------------------------------------------------


class AcademicYearService:
    def __init__(self, year_repo: AcademicYearRepository) -> None:
        self.repo = year_repo

    async def create_year(self, data: AcademicYearCreate) -> AcademicYear:
        existing = await self.repo.get_by_name(data.name.strip())
        if existing is not None:
            raise ConflictError(f"AcademicYear with name '{data.name}' already exists")

        year = AcademicYear(
            name=data.name.strip(),
            start_date=data.start_date,
            end_date=data.end_date,
            status="active",
        )
        try:
            return await self.repo.create(year)
        except IntegrityError:
            raise ConflictError(f"AcademicYear with name '{data.name}' already exists")

    async def get_year(self, year_id: int) -> AcademicYear:
        return await self.repo.get_by_id(year_id)

    async def update_year(
        self, year_id: int, data: AcademicYearUpdate
    ) -> AcademicYear:
        year = await self.repo.get_by_id(year_id)

        if data.name is not None:
            name = data.name.strip()
            existing = await self.repo.get_by_name(name)
            if existing is not None and existing.id != year_id:
                raise ConflictError(f"AcademicYear with name '{name}' already exists")
            year.name = name
        if data.start_date is not None:
            year.start_date = data.start_date
        if data.end_date is not None:
            if data.end_date <= (data.start_date or year.start_date):
                raise ValidationError("end_date must be after start_date")
            year.end_date = data.end_date
        if data.status is not None:
            year.status = data.status

        try:
            return await self.repo.update(year)
        except IntegrityError:
            raise ConflictError(f"AcademicYear with name '{data.name}' already exists")

    async def delete_year(self, year_id: int) -> None:
        year = await self.repo.get_by_id(year_id)
        await self.repo.delete(year)

    async def deactivate_year(self, year_id: int) -> AcademicYear:
        year = await self.repo.get_by_id(year_id)
        if year.status == "inactive":
            raise ConflictError(f"AcademicYear with id {year_id} is already inactive")
        year.status = "inactive"
        return await self.repo.update(year)

    async def reactivate_year(self, year_id: int) -> AcademicYear:
        year = await self.repo.get_by_id(year_id)
        if year.status == "active":
            raise ConflictError(f"AcademicYear with id {year_id} is already active")
        year.status = "active"
        return await self.repo.update(year)

    async def list_years(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AcademicYear], int]:
        if status is not None and status not in VALID_ACADEMIC_STATUSES:
            raise ValidationError(f"Invalid status filter: {status}")
        return await self.repo.list(status=status, campus_id=campus_id, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# ClassService
# ---------------------------------------------------------------------------


class ClassService:
    def __init__(
        self, class_repo: ClassRepository, year_repo: AcademicYearRepository
    ) -> None:
        self.repo = class_repo
        self.year_repo = year_repo

    async def create_class(self, data: ClassCreate) -> Class:
        await self.year_repo.get_by_id(data.academic_year_id)

        name = data.name.strip()
        existing = await self.repo.get_by_name_and_year(name, data.academic_year_id)
        if existing is not None:
            raise ConflictError(
                f"Class with name '{name}' already exists in this academic year"
            )

        cls = Class(
            name=name,
            academic_year_id=data.academic_year_id,
            status="active",
        )
        return await self.repo.create(cls)

    async def get_class(self, class_id: int) -> Class:
        return await self.repo.get_by_id(class_id)

    async def update_class(self, class_id: int, data: ClassUpdate) -> Class:
        cls = await self.repo.get_by_id(class_id)

        if data.academic_year_id is not None:
            await self.year_repo.get_by_id(data.academic_year_id)
            cls.academic_year_id = data.academic_year_id

        if data.name is not None:
            name = data.name.strip()
            existing = await self.repo.get_by_name_and_year(
                name, data.academic_year_id or cls.academic_year_id
            )
            if existing is not None and existing.id != class_id:
                raise ConflictError(
                    f"Class with name '{name}' already exists in this academic year"
                )
            cls.name = name
        if data.status is not None:
            cls.status = data.status

        return await self.repo.update(cls)

    async def delete_class(self, class_id: int) -> None:
        cls = await self.repo.get_by_id(class_id)
        await self.repo.delete(cls)

    async def deactivate_class(self, class_id: int) -> Class:
        cls = await self.repo.get_by_id(class_id)
        if cls.status == "inactive":
            raise ConflictError(f"Class with id {class_id} is already inactive")
        cls.status = "inactive"
        return await self.repo.update(cls)

    async def reactivate_class(self, class_id: int) -> Class:
        cls = await self.repo.get_by_id(class_id)
        if cls.status == "active":
            raise ConflictError(f"Class with id {class_id} is already active")
        cls.status = "active"
        return await self.repo.update(cls)

    async def list_classes(
        self,
        year_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Class], int]:
        if status is not None and status not in VALID_ACADEMIC_STATUSES:
            raise ValidationError(f"Invalid status filter: {status}")
        return await self.repo.list(
            year_id=year_id, status=status, campus_id=campus_id, skip=skip, limit=limit
        )


# ---------------------------------------------------------------------------
# SectionService
# ---------------------------------------------------------------------------


class SectionService:
    def __init__(
        self, section_repo: SectionRepository, class_repo: ClassRepository
    ) -> None:
        self.repo = section_repo
        self.class_repo = class_repo

    async def create_section(self, data: SectionCreate) -> Section:
        await self.class_repo.get_by_id(data.class_id)

        name = data.name.strip()
        existing = await self.repo.get_by_name_and_class(name, data.class_id)
        if existing is not None:
            raise ConflictError(
                f"Section with name '{name}' already exists in this class"
            )

        section = Section(
            name=name,
            class_id=data.class_id,
            status="active",
        )
        return await self.repo.create(section)

    async def get_section(self, section_id: int) -> Section:
        return await self.repo.get_by_id(section_id)

    async def update_section(self, section_id: int, data: SectionUpdate) -> Section:
        section = await self.repo.get_by_id(section_id)

        if data.class_id is not None:
            await self.class_repo.get_by_id(data.class_id)
            section.class_id = data.class_id

        if data.name is not None:
            name = data.name.strip()
            existing = await self.repo.get_by_name_and_class(
                name, data.class_id or section.class_id
            )
            if existing is not None and existing.id != section_id:
                raise ConflictError(
                    f"Section with name '{name}' already exists in this class"
                )
            section.name = name
        if data.status is not None:
            section.status = data.status

        return await self.repo.update(section)

    async def delete_section(self, section_id: int) -> None:
        section = await self.repo.get_by_id(section_id)
        await self.repo.delete(section)

    async def deactivate_section(self, section_id: int) -> Section:
        section = await self.repo.get_by_id(section_id)
        if section.status == "inactive":
            raise ConflictError(f"Section with id {section_id} is already inactive")
        section.status = "inactive"
        return await self.repo.update(section)

    async def reactivate_section(self, section_id: int) -> Section:
        section = await self.repo.get_by_id(section_id)
        if section.status == "active":
            raise ConflictError(f"Section with id {section_id} is already active")
        section.status = "active"
        return await self.repo.update(section)

    async def list_sections(
        self,
        class_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Section], int]:
        if status is not None and status not in VALID_ACADEMIC_STATUSES:
            raise ValidationError(f"Invalid status filter: {status}")
        return await self.repo.list(
            class_id=class_id, status=status, campus_id=campus_id, skip=skip, limit=limit
        )


# ---------------------------------------------------------------------------
# EnrollmentService
# ---------------------------------------------------------------------------


class EnrollmentService:
    def __init__(
        self,
        enrollment_repo: EnrollmentRepository,
        year_repo: AcademicYearRepository,
        class_repo: ClassRepository,
        section_repo: SectionRepository,
        student_repo: StudentRepository,
    ) -> None:
        self.repo = enrollment_repo
        self.year_repo = year_repo
        self.class_repo = class_repo
        self.section_repo = section_repo
        self.student_repo = student_repo

    async def create_enrollment(self, data: EnrollmentCreate) -> Enrollment:
        student = await self.student_repo.get_by_id(data.student_id)
        if student.status != "active":
            raise ValidationError("Cannot enroll an inactive student")

        year = await self.year_repo.get_by_id(data.academic_year_id)
        if year.status != "active":
            raise ValidationError("Cannot enroll in an inactive academic year")

        if data.class_id is not None:
            cls = await self.class_repo.get_by_id(data.class_id)
            if cls.status != "active":
                raise ValidationError("Cannot enroll in an inactive class")
            if cls.academic_year_id != data.academic_year_id:
                raise ValidationError("Class does not belong to the specified academic year")

        if data.section_id is not None:
            section = await self.section_repo.get_by_id(data.section_id)
            if section.status != "active":
                raise ValidationError("Cannot enroll in an inactive section")
            if data.class_id is not None and section.class_id != data.class_id:
                raise ValidationError("Section does not belong to the specified class")

        existing = await self.repo.get_by_student_and_year(
            data.student_id, data.academic_year_id
        )
        if existing is not None:
            raise ConflictError(
                f"Student is already enrolled in academic year {data.academic_year_id}"
            )

        enrollment = Enrollment(
            student_id=data.student_id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            section_id=data.section_id,
            status="active",
        )
        return await self.repo.create(enrollment)

    async def get_enrollment(self, enrollment_id: int) -> Enrollment:
        return await self.repo.get_by_id(enrollment_id)

    async def update_enrollment(
        self, enrollment_id: int, data: EnrollmentUpdate
    ) -> Enrollment:
        enrollment = await self.repo.get_by_id(enrollment_id)

        if data.class_id is not None:
            cls = await self.class_repo.get_by_id(data.class_id)
            if cls.academic_year_id != enrollment.academic_year_id:
                raise ValidationError("Class does not belong to the enrollment's academic year")
            enrollment.class_id = data.class_id

        if data.section_id is not None:
            section = await self.section_repo.get_by_id(data.section_id)
            class_id = data.class_id or enrollment.class_id
            if class_id is not None and section.class_id != class_id:
                raise ValidationError("Section does not belong to the enrollment's class")
            enrollment.section_id = data.section_id

        if data.status is not None:
            enrollment.status = data.status

        return await self.repo.update(enrollment)

    async def delete_enrollment(self, enrollment_id: int) -> None:
        enrollment = await self.repo.get_by_id(enrollment_id)
        await self.repo.delete(enrollment)

    async def list_enrollments(
        self,
        student_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Enrollment], int]:
        return await self.repo.list(
            student_id=student_id,
            academic_year_id=academic_year_id,
            class_id=class_id,
            section_id=section_id,
            campus_id=campus_id,
            skip=skip,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# TermService
# ---------------------------------------------------------------------------


class TermService:
    def __init__(
        self,
        term_repo: TermRepository,
        year_repo: AcademicYearRepository,
    ) -> None:
        self.repo = term_repo
        self.year_repo = year_repo

    async def create_term(self, year_id: int, data: TermCreate) -> Term:
        await self.year_repo.get_by_id(year_id)

        overlapping = await self.repo.find_overlapping(
            year_id, data.start_date, data.end_date
        )
        if overlapping is not None:
            raise ConflictError(
                f"Term '{data.name}' overlaps with an existing term "
                f"'{overlapping.name}' ({overlapping.start_date} - "
                f"{overlapping.end_date})"
            )

        term = Term(
            academic_year_id=year_id,
            name=data.name.strip(),
            start_date=data.start_date,
            end_date=data.end_date,
            status="active",
        )
        return await self.repo.create(term)

    async def get_term(self, term_id: int) -> Term:
        return await self.repo.get_by_id(term_id)

    async def update_term(self, term_id: int, data: TermUpdate) -> Term:
        term = await self.repo.get_by_id(term_id)

        if data.name is not None:
            term.name = data.name.strip()

        start = data.start_date or term.start_date
        end = data.end_date or term.end_date

        if data.start_date is not None or data.end_date is not None:
            overlapping = await self.repo.find_overlapping(
                term.academic_year_id, start, end, exclude_id=term_id
            )
            if overlapping is not None:
                raise ConflictError(
                    f"Updated dates overlap with term '{overlapping.name}'"
                )
            term.start_date = start
            term.end_date = end

        if data.status is not None:
            term.status = data.status

        return await self.repo.update(term)

    async def list_terms(
        self,
        year_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Term], int]:
        if year_id is not None:
            terms = await self.repo.find_by_academic_year(year_id)
            return terms, len(terms)
        terms, total = await self._list_all(skip, limit)
        return terms, total

    async def _list_all(
        self, skip: int, limit: int
    ) -> tuple[Sequence[Term], int]:
        from sqlalchemy import func, select

        count_result = await self.repo.session.execute(
            select(func.count(Term.id))
        )
        total = count_result.scalar() or 0
        result = await self.repo.session.execute(
            select(Term).offset(skip).limit(limit).order_by(Term.start_date)
        )
        return result.scalars().all(), total


# ---------------------------------------------------------------------------
# SubjectService
# ---------------------------------------------------------------------------


class SubjectService:
    def __init__(self, subject_repo: SubjectRepository) -> None:
        self.repo = subject_repo

    async def create_subject(self, data: SubjectCreate) -> Subject:
        existing = await self.repo.get_by_name(data.name.strip())
        if existing is not None:
            raise ConflictError(
                f"Subject with name '{data.name}' already exists"
            )

        existing_code = await self.repo.get_by_code(data.code)
        if existing_code is not None:
            raise ConflictError(
                f"Subject with code '{data.code}' already exists"
            )

        subject = Subject(
            name=data.name.strip(),
            code=data.code,
            description=data.description,
            status="active",
        )
        return await self.repo.create(subject)

    async def get_subject(self, subject_id: int) -> Subject:
        return await self.repo.get_by_id(subject_id)

    async def update_subject(
        self, subject_id: int, data: SubjectUpdate
    ) -> Subject:
        subject = await self.repo.get_by_id(subject_id)

        if data.name is not None:
            name = data.name.strip()
            existing = await self.repo.get_by_name(name)
            if existing is not None and existing.id != subject_id:
                raise ConflictError(
                    f"Subject with name '{name}' already exists"
                )
            subject.name = name

        if data.code is not None:
            existing = await self.repo.get_by_code(data.code)
            if existing is not None and existing.id != subject_id:
                raise ConflictError(
                    f"Subject with code '{data.code}' already exists"
                )
            subject.code = data.code

        if data.description is not None:
            subject.description = data.description

        if data.status is not None:
            subject.status = data.status

        return await self.repo.update(subject)

    async def list_subjects(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Subject], int]:
        return await self.repo.list(status=status, campus_id=campus_id, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# TeacherService
# ---------------------------------------------------------------------------


class TeacherService:
    def __init__(self, teacher_repo: TeacherRepository) -> None:
        self.repo = teacher_repo

    async def create_teacher(self, data: TeacherCreate) -> Teacher:
        existing = await self.repo.get_by_employee_number(
            data.employee_number
        )
        if existing is not None:
            raise ConflictError(
                f"Teacher with employee number "
                f"'{data.employee_number}' already exists"
            )

        teacher = Teacher(
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            employee_number=data.employee_number,
            email=data.email,
            status="active",
        )
        return await self.repo.create(teacher)

    async def get_teacher(self, teacher_id: int) -> Teacher:
        return await self.repo.get_by_id(teacher_id)

    async def update_teacher(
        self, teacher_id: int, data: TeacherUpdate
    ) -> Teacher:
        teacher = await self.repo.get_by_id(teacher_id)

        if data.first_name is not None:
            teacher.first_name = data.first_name.strip()
        if data.last_name is not None:
            teacher.last_name = data.last_name.strip()
        if data.email is not None:
            teacher.email = data.email
        if data.status is not None:
            teacher.status = data.status

        return await self.repo.update(teacher)

    async def list_teachers(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Teacher], int]:
        return await self.repo.list(status=status, campus_id=campus_id, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# TeacherAssignmentService
# ---------------------------------------------------------------------------


class TeacherAssignmentService:
    def __init__(
        self,
        assignment_repo: TeacherAssignmentRepository,
        teacher_repo: TeacherRepository,
        class_repo: ClassRepository,
        subject_repo: SubjectRepository,
    ) -> None:
        self.repo = assignment_repo
        self.teacher_repo = teacher_repo
        self.class_repo = class_repo
        self.subject_repo = subject_repo

    async def assign_teacher(
        self, data: TeacherAssignmentCreate
    ) -> TeacherAssignment:
        teacher = await self.teacher_repo.get_by_id(data.teacher_id)
        if teacher.status != "active":
            raise ValidationError("Cannot assign an inactive teacher")

        cls = await self.class_repo.get_by_id(data.class_id)
        if cls.status != "active":
            raise ValidationError("Cannot assign to an inactive class")

        if data.subject_id is not None:
            subject = await self.subject_repo.get_by_id(data.subject_id)
            if subject.status != "active":
                raise ValidationError(
                    "Cannot assign to an inactive subject"
                )

            existing = await self.repo.find_by_class_and_subject(
                data.class_id, data.subject_id
            )
            if existing is not None:
                raise ConflictError(
                    f"Teacher already assigned to "
                    f"class {data.class_id} for subject "
                    f"{data.subject_id}"
                )

        assignment = TeacherAssignment(
            teacher_id=data.teacher_id,
            class_id=data.class_id,
            subject_id=data.subject_id,
            status="active",
        )
        return await self.repo.create(assignment)

    async def get_assignment(self, assignment_id: int) -> TeacherAssignment:
        return await self.repo.get_by_id(assignment_id)

    async def unassign(self, assignment_id: int) -> None:
        assignment = await self.repo.get_by_id(assignment_id)
        await self.repo.delete(assignment)

    async def list_assignments(
        self,
        class_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[TeacherAssignment], int]:
        if class_id is not None:
            items = await self.repo.find_by_class(class_id)
            return items, len(items)
        if teacher_id is not None:
            items = await self.repo.find_by_teacher(teacher_id)
            return items, len(items)

        from sqlalchemy import func, select

        count_result = await self.repo.session.execute(
            select(func.count(TeacherAssignment.id))
        )
        total = count_result.scalar() or 0
        result = await self.repo.session.execute(
            select(TeacherAssignment)
            .offset(skip)
            .limit(limit)
            .order_by(TeacherAssignment.id)
        )
        return result.scalars().all(), total