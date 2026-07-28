from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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


# ---------------------------------------------------------------------------
# AcademicYearRepository
# ---------------------------------------------------------------------------


class AcademicYearRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, year_id: int) -> AcademicYear:
        result = await self.session.execute(
            select(AcademicYear).where(AcademicYear.id == year_id)
        )
        year = result.scalar_one_or_none()
        if year is None:
            raise NotFoundError(f"AcademicYear with id {year_id} not found")
        return year

    async def get_by_name(self, name: str) -> AcademicYear | None:
        result = await self.session.execute(
            select(AcademicYear).where(AcademicYear.name == name)
        )
        return result.scalar_one_or_none()

    async def exists_by_name(self, name: str) -> bool:
        result = await self.session.execute(
            select(func.count(AcademicYear.id)).where(AcademicYear.name == name)
        )
        return (result.scalar() or 0) > 0

    async def list(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AcademicYear], int]:
        query = select(AcademicYear)
        count_query = select(func.count(AcademicYear.id))

        if status is not None:
            query = query.where(AcademicYear.status == status)
            count_query = count_query.where(AcademicYear.status == status)

        query = query.offset(skip).limit(limit).order_by(AcademicYear.start_date)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, year: AcademicYear) -> AcademicYear:
        self.session.add(year)
        await self.session.flush()
        return year

    async def update(self, year: AcademicYear) -> AcademicYear:
        await self.session.flush()
        return year

    async def delete(self, year: AcademicYear) -> None:
        await self.session.delete(year)


# ---------------------------------------------------------------------------
# ClassRepository
# ---------------------------------------------------------------------------


class ClassRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, class_id: int) -> Class:
        result = await self.session.execute(
            select(Class).where(Class.id == class_id)
        )
        cls = result.scalar_one_or_none()
        if cls is None:
            raise NotFoundError(f"Class with id {class_id} not found")
        return cls

    async def get_by_name_and_year(self, name: str, year_id: int) -> Class | None:
        result = await self.session.execute(
            select(Class).where(
                Class.name == name, Class.academic_year_id == year_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_year(
        self,
        year_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Class], int]:
        query = (
            select(Class)
            .where(Class.academic_year_id == year_id)
            .offset(skip)
            .limit(limit)
            .order_by(Class.name)
        )
        count_query = select(func.count(Class.id)).where(
            Class.academic_year_id == year_id
        )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def list(
        self,
        year_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Class], int]:
        query = select(Class)
        count_query = select(func.count(Class.id))

        if year_id is not None:
            query = query.where(Class.academic_year_id == year_id)
            count_query = count_query.where(Class.academic_year_id == year_id)
        if status is not None:
            query = query.where(Class.status == status)
            count_query = count_query.where(Class.status == status)

        query = query.offset(skip).limit(limit).order_by(Class.name)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, cls: Class) -> Class:
        self.session.add(cls)
        await self.session.flush()
        return cls

    async def update(self, cls: Class) -> Class:
        await self.session.flush()
        return cls

    async def delete(self, cls: Class) -> None:
        await self.session.delete(cls)


# ---------------------------------------------------------------------------
# SectionRepository
# ---------------------------------------------------------------------------


class SectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, section_id: int) -> Section:
        result = await self.session.execute(
            select(Section).where(Section.id == section_id)
        )
        section = result.scalar_one_or_none()
        if section is None:
            raise NotFoundError(f"Section with id {section_id} not found")
        return section

    async def get_by_name_and_class(self, name: str, class_id: int) -> Section | None:
        result = await self.session.execute(
            select(Section).where(
                Section.name == name, Section.class_id == class_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_class(
        self,
        class_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Section], int]:
        query = (
            select(Section)
            .where(Section.class_id == class_id)
            .offset(skip)
            .limit(limit)
            .order_by(Section.name)
        )
        count_query = select(func.count(Section.id)).where(
            Section.class_id == class_id
        )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def list(
        self,
        class_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Section], int]:
        query = select(Section)
        count_query = select(func.count(Section.id))

        if class_id is not None:
            query = query.where(Section.class_id == class_id)
            count_query = count_query.where(Section.class_id == class_id)
        if status is not None:
            query = query.where(Section.status == status)
            count_query = count_query.where(Section.status == status)

        query = query.offset(skip).limit(limit).order_by(Section.name)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, section: Section) -> Section:
        self.session.add(section)
        await self.session.flush()
        return section

    async def update(self, section: Section) -> Section:
        await self.session.flush()
        return section

    async def delete(self, section: Section) -> None:
        await self.session.delete(section)


# ---------------------------------------------------------------------------
# EnrollmentRepository
# ---------------------------------------------------------------------------


class EnrollmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, enrollment_id: int) -> Enrollment:
        result = await self.session.execute(
            select(Enrollment).where(Enrollment.id == enrollment_id)
        )
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            raise NotFoundError(f"Enrollment with id {enrollment_id} not found")
        return enrollment

    async def get_by_student_and_year(
        self, student_id: int, year_id: int
    ) -> Enrollment | None:
        result = await self.session.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.academic_year_id == year_id,
            )
        )
        return result.scalar_one_or_none()

    async def exists_enrollment(
        self, student_id: int, year_id: int
    ) -> bool:
        result = await self.session.execute(
            select(func.count(Enrollment.id)).where(
                Enrollment.student_id == student_id,
                Enrollment.academic_year_id == year_id,
            )
        )
        return (result.scalar() or 0) > 0

    async def list(
        self,
        student_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Enrollment], int]:
        query = select(Enrollment)
        count_query = select(func.count(Enrollment.id))

        if student_id is not None:
            query = query.where(Enrollment.student_id == student_id)
            count_query = count_query.where(Enrollment.student_id == student_id)
        if academic_year_id is not None:
            query = query.where(Enrollment.academic_year_id == academic_year_id)
            count_query = count_query.where(
                Enrollment.academic_year_id == academic_year_id
            )
        if class_id is not None:
            query = query.where(Enrollment.class_id == class_id)
            count_query = count_query.where(Enrollment.class_id == class_id)
        if section_id is not None:
            query = query.where(Enrollment.section_id == section_id)
            count_query = count_query.where(Enrollment.section_id == section_id)

        query = query.offset(skip).limit(limit).order_by(Enrollment.id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, enrollment: Enrollment) -> Enrollment:
        self.session.add(enrollment)
        await self.session.flush()
        return enrollment

    async def update(self, enrollment: Enrollment) -> Enrollment:
        await self.session.flush()
        return enrollment

    async def delete(self, enrollment: Enrollment) -> None:
        await self.session.delete(enrollment)


# ---------------------------------------------------------------------------
# TermRepository
# ---------------------------------------------------------------------------


class TermRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, term_id: int) -> Term:
        result = await self.session.execute(
            select(Term).where(Term.id == term_id)
        )
        term = result.scalar_one_or_none()
        if term is None:
            raise NotFoundError(f"Term with id {term_id} not found")
        return term

    async def find_by_academic_year(
        self, academic_year_id: int
    ) -> Sequence[Term]:
        result = await self.session.execute(
            select(Term)
            .where(Term.academic_year_id == academic_year_id)
            .order_by(Term.start_date)
        )
        return result.scalars().all()

    async def find_overlapping(
        self,
        academic_year_id: int,
        start_date: str,
        end_date: str,
        exclude_id: Optional[int] = None,
    ) -> Term | None:
        from sqlalchemy import and_

        conditions = [
            Term.academic_year_id == academic_year_id,
            Term.start_date < end_date,
            Term.end_date > start_date,
        ]
        if exclude_id is not None:
            conditions.append(Term.id != exclude_id)

        result = await self.session.execute(
            select(Term).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def create(self, term: Term) -> Term:
        self.session.add(term)
        await self.session.flush()
        return term

    async def update(self, term: Term) -> Term:
        await self.session.flush()
        return term


# ---------------------------------------------------------------------------
# SubjectRepository
# ---------------------------------------------------------------------------


class SubjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, subject_id: int) -> Subject:
        result = await self.session.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        subject = result.scalar_one_or_none()
        if subject is None:
            raise NotFoundError(f"Subject with id {subject_id} not found")
        return subject

    async def get_by_name(self, name: str) -> Subject | None:
        result = await self.session.execute(
            select(Subject).where(Subject.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Subject | None:
        result = await self.session.execute(
            select(Subject).where(Subject.code == code)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Subject], int]:
        query = select(Subject)
        count_query = select(func.count(Subject.id))

        if status is not None:
            query = query.where(Subject.status == status)
            count_query = count_query.where(Subject.status == status)

        query = query.offset(skip).limit(limit).order_by(Subject.name)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, subject: Subject) -> Subject:
        self.session.add(subject)
        await self.session.flush()
        return subject

    async def update(self, subject: Subject) -> Subject:
        await self.session.flush()
        return subject


# ---------------------------------------------------------------------------
# TeacherRepository
# ---------------------------------------------------------------------------


class TeacherRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, teacher_id: int) -> Teacher:
        result = await self.session.execute(
            select(Teacher).where(Teacher.id == teacher_id)
        )
        teacher = result.scalar_one_or_none()
        if teacher is None:
            raise NotFoundError(f"Teacher with id {teacher_id} not found")
        return teacher

    async def get_by_employee_number(
        self, employee_number: str
    ) -> Teacher | None:
        result = await self.session.execute(
            select(Teacher).where(
                Teacher.employee_number == employee_number
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Teacher], int]:
        query = select(Teacher)
        count_query = select(func.count(Teacher.id))

        if status is not None:
            query = query.where(Teacher.status == status)
            count_query = count_query.where(Teacher.status == status)

        query = (
            query.offset(skip)
            .limit(limit)
            .order_by(Teacher.last_name, Teacher.first_name)
        )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, teacher: Teacher) -> Teacher:
        self.session.add(teacher)
        await self.session.flush()
        return teacher

    async def update(self, teacher: Teacher) -> Teacher:
        await self.session.flush()
        return teacher


# ---------------------------------------------------------------------------
# TeacherAssignmentRepository
# ---------------------------------------------------------------------------


class TeacherAssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, assignment_id: int) -> TeacherAssignment:
        result = await self.session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.id == assignment_id
            )
        )
        assignment = result.scalar_one_or_none()
        if assignment is None:
            raise NotFoundError(
                f"TeacherAssignment with id {assignment_id} not found"
            )
        return assignment

    async def find_by_class(
        self, class_id: int
    ) -> Sequence[TeacherAssignment]:
        result = await self.session.execute(
            select(TeacherAssignment)
            .where(TeacherAssignment.class_id == class_id)
            .order_by(TeacherAssignment.id)
        )
        return result.scalars().all()

    async def find_by_teacher(
        self, teacher_id: int
    ) -> Sequence[TeacherAssignment]:
        result = await self.session.execute(
            select(TeacherAssignment)
            .where(TeacherAssignment.teacher_id == teacher_id)
            .order_by(TeacherAssignment.id)
        )
        return result.scalars().all()

    async def find_by_class_and_subject(
        self, class_id: int, subject_id: int
    ) -> TeacherAssignment | None:
        result = await self.session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.class_id == class_id,
                TeacherAssignment.subject_id == subject_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, assignment: TeacherAssignment
    ) -> TeacherAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def update(
        self, assignment: TeacherAssignment
    ) -> TeacherAssignment:
        await self.session.flush()
        return assignment

    async def delete(self, assignment: TeacherAssignment) -> None:
        await self.session.delete(assignment)