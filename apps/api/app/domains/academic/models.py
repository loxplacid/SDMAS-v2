from __future__ import annotations

import datetime
from datetime import timezone
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    classes: Mapped[List[Class]] = relationship(
        back_populates="academic_year", cascade="all, delete-orphan"
    )
    enrollments: Mapped[List["Enrollment"]] = relationship(
        back_populates="academic_year", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AcademicYear id={self.id} name={self.name}>"


class Class(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("name", "academic_year_id", name="uq_class_name_per_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    academic_year: Mapped[AcademicYear] = relationship(back_populates="classes")
    sections: Mapped[List[Section]] = relationship(
        back_populates="class_", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Class id={self.id} name={self.name} year_id={self.academic_year_id}>"


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("name", "class_id", name="uq_section_name_per_class"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    class_: Mapped[Class] = relationship(back_populates="sections")

    def __repr__(self) -> str:
        return f"<Section id={self.id} name={self.name} class_id={self.class_id}>"


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "academic_year_id", name="uq_student_enrollment_per_year"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("classes.id"), nullable=True
    )
    section_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sections.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    enrolled_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    academic_year: Mapped[AcademicYear] = relationship(back_populates="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment id={self.id} student_id={self.student_id} year_id={self.academic_year_id}>"


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    employee_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Teacher id={self.id} name={self.first_name} {self.last_name}>"


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name={self.name} code={self.code}>"


# ---------------------------------------------------------------------------
# Term
# ---------------------------------------------------------------------------


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Term id={self.id} name={self.name} "
            f"year_id={self.academic_year_id}>"
        )


# ---------------------------------------------------------------------------
# TeacherAssignment
# ---------------------------------------------------------------------------


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "class_id", "subject_id",
            name="uq_assignment_class_subject",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<TeacherAssignment id={self.id} "
            f"teacher_id={self.teacher_id} "
            f"class_id={self.class_id}>"
        )