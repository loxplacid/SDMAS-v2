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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class PeriodAttendance(Base):
    __tablename__ = "period_attendances"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False
    )
    attendance_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    records: Mapped[List["PeriodAttendanceRecord"]] = relationship(
        back_populates="period_attendance", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<PeriodAttendance id={self.id} date={self.attendance_date} "
            f"period={self.period_number} section={self.section_id}>"
        )


class PeriodAttendanceRecord(Base):
    __tablename__ = "period_attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "period_attendance_id", "student_id",
            name="uq_period_attendance_student",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period_attendance_id: Mapped[int] = mapped_column(
        ForeignKey("period_attendances.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="present"
    )
    arrival_time: Mapped[Optional[str]] = mapped_column(
        String(5), nullable=True
    )
    departure_time: Mapped[Optional[str]] = mapped_column(
        String(5), nullable=True
    )
    late_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    early_departure_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    absence_reason_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("absence_reasons.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    period_attendance: Mapped[PeriodAttendance] = relationship(
        back_populates="records"
    )
    absence_reason: Mapped[Optional["AbsenceReason"]] = relationship(
        back_populates="period_records"
    )

    def __repr__(self) -> str:
        return (
            f"<PeriodAttendanceRecord id={self.id} "
            f"student={self.student_id} status={self.status}>"
        )


class AbsenceReason(Base):
    __tablename__ = "absence_reasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_approval: Mapped[bool] = mapped_column(
        default=False
    )
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    period_records: Mapped[List["PeriodAttendanceRecord"]] = relationship(
        back_populates="absence_reason"
    )
    corrections: Mapped[List["AttendanceCorrection"]] = relationship(
        back_populates="absence_reason"
    )

    def __repr__(self) -> str:
        return f"<AbsenceReason id={self.id} code={self.code} name={self.name}>"


class AttendanceCorrection(Base):
    __tablename__ = "attendance_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    requested_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    absence_reason_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("absence_reasons.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    absence_reason: Mapped[Optional["AbsenceReason"]] = relationship(
        back_populates="corrections"
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceCorrection id={self.id} "
            f"type={self.record_type} status={self.status}>"
        )


class AttendanceThreshold(Base):
    __tablename__ = "attendance_thresholds"
    __table_args__ = (
        UniqueConstraint(
            "campus_id", "academic_year_id", "name",
            name="uq_attendance_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=True
    )
    academic_year_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    threshold_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    days_absent_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    consecutive_absences: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    notification_enabled: Mapped[bool] = mapped_column(default=True)
    notification_channels: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default="in_app"
    )
    applies_to: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceThreshold id={self.id} "
            f"name={self.name} {self.percentage}%>"
        )
