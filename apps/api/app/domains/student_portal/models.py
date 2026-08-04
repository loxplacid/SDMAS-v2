from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Assignment(Base):
    """A piece of work assigned to students by a teacher.

    This model is deliberately lightweight to serve as the foundation for
    future LMS integration (Google Classroom, Moodle, Canvas, etc.).
    Future extensions could add:
    - ``external_id`` / ``external_source`` for syncing with third-party LMS
    - ``submission_type`` (online_text, file_upload, google_doc, etc.)
    - ``rubric`` JSON for detailed grading criteria
    - ``peer_review`` configuration
    - ``plagiarism_check`` flags
    - ``lms_sync_token`` / ``lms_sync_url`` for bi-directional sync
    """

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    teacher_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    academic_year_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("terms.id", ondelete="SET NULL"), nullable=True
    )
    campus_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Type & submission
    assignment_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="homework"
    )
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passing_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Dates
    due_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    available_from: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    available_until: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_late_submission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # LMS integration (future)
    lms_external_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="External LMS ID for future integration"
    )
    lms_source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Source LMS name (google_classroom, moodle, canvas, etc.)"
    )

    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Assignment id={self.id} title={self.title}>"


class AssignmentSubmission(Base):
    """A student's submission for an assignment.

    Supports both file upload and text-based submissions.
    Future LMS integration: ``external_submission_id``, ``lms_sync_status``.
    """

    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "student_id", name="uq_submission_per_student"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    graded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    graded_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")

    # LMS integration
    lms_external_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="External submission ID from LMS"
    )

    submitted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<AssignmentSubmission id={self.id} assignment_id={self.assignment_id} student_id={self.student_id}>"
