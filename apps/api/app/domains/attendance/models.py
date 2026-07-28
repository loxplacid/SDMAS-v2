from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "attendance_date", "section_id",
            name="uq_attendance_student_date_section",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id"), nullable=False
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id"), nullable=False
    )
    attendance_date: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
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
            f"<AttendanceRecord id={self.id} "
            f"student_id={self.student_id} "
            f"date={self.attendance_date} "
            f"status={self.status}>"
        )