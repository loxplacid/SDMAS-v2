from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── Helpers ────────────────────────────────────────────────────────────


class SubjectInfo(BaseModel):
    id: int
    name: str
    code: str


class TeacherInfo(BaseModel):
    id: int
    name: str
    email: Optional[str] = None


class EnrollmentInfo(BaseModel):
    academic_year_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    status: str = "active"


# ── Timetable ──────────────────────────────────────────────────────────


class TimetableEntryItem(BaseModel):
    id: int
    day_of_week: int
    day_name: str = ""
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    teacher_name: Optional[str] = None
    room_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    time_slot_name: Optional[str] = None


class TimetableDayGroup(BaseModel):
    day_of_week: int
    day_name: str
    entries: list[TimetableEntryItem] = []


class StudentTimetableResponse(BaseModel):
    enrollment: Optional[EnrollmentInfo] = None
    days: list[TimetableDayGroup] = []


# ── Attendance ─────────────────────────────────────────────────────────


class AttendanceSummary(BaseModel):
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    percentage: float = 0.0


class AttendanceRecord(BaseModel):
    id: int
    attendance_date: str
    status: str
    notes: Optional[str] = None


class StudentAttendanceResponse(BaseModel):
    summary: AttendanceSummary = AttendanceSummary()
    records: list[AttendanceRecord] = []
    current_streak: int = 0
    monthly_breakdown: list[dict[str, Any]] = []


# ── Subjects ───────────────────────────────────────────────────────────


class EnrolledSubject(BaseModel):
    id: int
    name: str
    code: str
    teacher_name: Optional[str] = None
    teacher_email: Optional[str] = None
    total_hours: Optional[int] = None
    syllabus: Optional[str] = None
    textbook: Optional[str] = None


class StudentSubjectsResponse(BaseModel):
    enrollment: Optional[EnrollmentInfo] = None
    subjects: list[EnrolledSubject] = []


# ── Academic Results ───────────────────────────────────────────────────


class SubjectResult(BaseModel):
    subject_name: str
    subject_code: str
    marks_obtained: Optional[float] = None
    max_marks: int = 100
    grade: Optional[str] = None
    grade_point: Optional[float] = None
    remarks: Optional[str] = None
    term_name: Optional[str] = None


class TermResult(BaseModel):
    term_name: str
    subjects: list[SubjectResult] = []
    total_marks: float = 0
    total_max_marks: float = 0
    percentage: float = 0.0
    grade_point_average: Optional[float] = None


class StudentResultsResponse(BaseModel):
    enrollment: Optional[EnrollmentInfo] = None
    terms: list[TermResult] = []
    overall_percentage: float = 0.0
    overall_grade_point_average: Optional[float] = None


# ── Assignments ────────────────────────────────────────────────────────


class StudentAssignment(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    teacher_name: Optional[str] = None
    assignment_type: str = "homework"
    max_score: Optional[float] = None
    due_at: Optional[datetime.datetime] = None
    available_from: Optional[datetime.datetime] = None
    is_published: bool = False

    # Submission status (for the current student)
    submission_id: Optional[int] = None
    submitted_at: Optional[datetime.datetime] = None
    score: Optional[float] = None
    grade: Optional[str] = None
    feedback: Optional[str] = None
    submission_status: Optional[str] = None
    is_late: bool = False


class StudentAssignmentsResponse(BaseModel):
    pending: list[StudentAssignment] = []
    submitted: list[StudentAssignment] = []
    graded: list[StudentAssignment] = []
    overdue: list[StudentAssignment] = []


# ── Announcements ─────────────────────────────────────────────────────


class StudentAnnouncement(BaseModel):
    id: int
    title: Optional[str] = None
    body: str
    priority: str = "normal"
    sender_name: Optional[str] = None
    created_at: datetime.datetime


class StudentAnnouncementsResponse(BaseModel):
    announcements: list[StudentAnnouncement] = []


# ── Documents ─────────────────────────────────────────────────────────


class StudentDocument(BaseModel):
    id: int
    filename: str
    mime_type: str
    file_size: int
    category_name: Optional[str] = None
    created_at: datetime.datetime


class StudentDocumentsResponse(BaseModel):
    documents: list[StudentDocument] = []


# ── Dashboard ─────────────────────────────────────────────────────────


class StudentPortalDashboardResponse(BaseModel):
    student_name: str = ""
    student_number: str = ""
    enrollment: Optional[EnrollmentInfo] = None
    attendance: AttendanceSummary = AttendanceSummary()
    subjects_count: int = 0
    pending_assignments: int = 0
    overdue_assignments: int = 0
    upcoming_timetable: list[TimetableEntryItem] = []
    unread_notifications: int = 0
    recent_announcements: list[StudentAnnouncement] = []
