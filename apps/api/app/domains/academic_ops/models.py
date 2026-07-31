from __future__ import annotations

import datetime
from datetime import timezone
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("code", name="uq_room_code"),
        UniqueConstraint("name", "building", name="uq_room_name_building"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    building: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    floor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    room_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="classroom"
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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

    timetable_entries: Mapped[List["TimetableEntry"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Room id={self.id} name={self.name} code={self.code}>"


class TimeSlot(Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        UniqueConstraint(
            "day_of_week", "start_time", "end_time", name="uq_timeslot_day_time"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    slot_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="regular"
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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

    timetable_entries: Mapped[List["TimetableEntry"]] = relationship(
        back_populates="time_slot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<TimeSlot id={self.id} name={self.name} "
            f"day={self.day_of_week} {self.start_time}-{self.end_time}>"
        )


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"
    __table_args__ = (
        UniqueConstraint(
            "class_id", "section_id", "time_slot_id", "day_of_week",
            name="uq_timetable_entry",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    term_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("terms.id"), nullable=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    section_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sections.id"), nullable=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"), nullable=False
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False
    )
    room_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rooms.id"), nullable=True
    )
    time_slot_id: Mapped[int] = mapped_column(
        ForeignKey("time_slots.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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

    room: Mapped[Optional[Room]] = relationship(back_populates="timetable_entries")
    time_slot: Mapped[TimeSlot] = relationship(back_populates="timetable_entries")
    substitutions: Mapped[List["Substitution"]] = relationship(
        back_populates="timetable_entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<TimetableEntry id={self.id} "
            f"class={self.class_id} subject={self.subject_id} "
            f"day={self.day_of_week} slot={self.time_slot_id}>"
        )


class Substitution(Base):
    __tablename__ = "substitutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    timetable_entry_id: Mapped[int] = mapped_column(
        ForeignKey("timetable_entries.id"), nullable=False
    )
    original_teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False
    )
    substitute_teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False
    )
    substitution_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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

    timetable_entry: Mapped[TimetableEntry] = relationship(
        back_populates="substitutions"
    )

    def __repr__(self) -> str:
        return (
            f"<Substitution id={self.id} "
            f"entry={self.timetable_entry_id} "
            f"date={self.substitution_date}>"
        )


class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    term_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("terms.id"), nullable=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    section_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sections.id"), nullable=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"), nullable=False
    )
    exam_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    room_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rooms.id"), nullable=True
    )
    invigilator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teachers.id"), nullable=True
    )
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    pass_marks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
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
            f"<ExamSchedule id={self.id} "
            f"subject={self.subject_id} date={self.exam_date}>"
        )


class GradingStructure(Base):
    __tablename__ = "grading_structures"
    __table_args__ = (
        UniqueConstraint(
            "academic_year_id", "class_id", "subject_id", "name",
            name="uq_grading_structure",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("classes.id"), nullable=True
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    max_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    grade_point: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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
            f"<GradingStructure id={self.id} name={self.name} "
            f"{self.min_percentage}-{self.max_percentage}%>"
        )


class GradeRecord(Base):
    __tablename__ = "grade_records"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id", "subject_id", "term_id",
            name="uq_grade_record",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"), nullable=False
    )
    grading_structure_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("grading_structures.id"), nullable=True
    )
    marks_obtained: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    grade: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    grade_point: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    term_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("terms.id"), nullable=True
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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
            f"<GradeRecord id={self.id} "
            f"enrollment={self.enrollment_id} "
            f"subject={self.subject_id} grade={self.grade}>"
        )


class Curriculum(Base):
    __tablename__ = "curricula"
    __table_args__ = (
        UniqueConstraint(
            "academic_year_id", "class_id", "subject_id",
            name="uq_curriculum",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"), nullable=False
    )
    term_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("terms.id"), nullable=True
    )
    topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objectives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    syllabus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    textbook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
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
            f"<Curriculum id={self.id} "
            f"class={self.class_id} subject={self.subject_id}>"
        )
