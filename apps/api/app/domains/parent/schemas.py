from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Linked Child ─────────────────────────────────────────────────────


class LinkedChild(BaseModel):
    """Minimal child info for the parent's linked children list."""

    id: int
    first_name: str
    last_name: str
    student_number: str
    email: Optional[str] = None
    status: str
    relationship: str = "parent"
    is_primary: bool = True


# ── Link / Unlink ────────────────────────────────────────────────────


class LinkChildRequest(BaseModel):
    student_id: int = Field(..., ge=1)
    relationship: str = Field(default="parent", max_length=50)


# ── Attendance ───────────────────────────────────────────────────────


class ParentAttendanceSummary(BaseModel):
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    percentage: float = 0.0


class ParentAttendanceRecord(BaseModel):
    id: int
    attendance_date: str
    status: str
    notes: Optional[str] = None


class ParentAttendanceResponse(BaseModel):
    child: LinkedChild
    summary: ParentAttendanceSummary = ParentAttendanceSummary()
    records: list[ParentAttendanceRecord] = []
    current_streak: int = 0
    days_since_last_absence: int = 0


# ── Fees / Payments / Receipts ───────────────────────────────────────


class ParentFeeDue(BaseModel):
    id: int
    fee_type_name: Optional[str] = None
    original_amount: int = 0
    amount_paid: int = 0
    balance: int = 0
    due_date: Optional[str] = None
    status: str = "unpaid"


class ParentPayment(BaseModel):
    id: int
    amount: int
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    created_at: str


class ParentFinancialSummary(BaseModel):
    total_fees_assigned: int = 0
    total_paid: int = 0
    total_outstanding: int = 0
    unpaid_count: int = 0
    partially_paid_count: int = 0
    paid_count: int = 0


class ParentFeesResponse(BaseModel):
    child: LinkedChild
    summary: ParentFinancialSummary = ParentFinancialSummary()
    dues: list[ParentFeeDue] = []
    payments: list[ParentPayment] = []


# ── Academic / Performance ───────────────────────────────────────────


class ParentAcademicRecord(BaseModel):
    academic_year_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    status: str = "active"


class ParentSubjectGrade(BaseModel):
    subject_name: str
    grade: Optional[str] = None
    score: Optional[float] = None
    remarks: Optional[str] = None


class ParentAcademicResponse(BaseModel):
    child: LinkedChild
    current_enrollment: Optional[ParentAcademicRecord] = None
    academic_history: list[ParentAcademicRecord] = []
    grades: list[ParentSubjectGrade] = []
    attendance_summary: ParentAttendanceSummary = ParentAttendanceSummary()


# ── Announcements ────────────────────────────────────────────────────


class ParentAnnouncement(BaseModel):
    id: int
    title: Optional[str] = None
    body: str
    priority: str = "normal"
    created_at: datetime.datetime
    sender_name: Optional[str] = None


class ParentAnnouncementsResponse(BaseModel):
    announcements: list[ParentAnnouncement] = []


# ── Documents ────────────────────────────────────────────────────────


class ParentDocument(BaseModel):
    id: int
    filename: str
    mime_type: str
    file_size: int
    created_at: datetime.datetime
    category_name: Optional[str] = None


class ParentDocumentsResponse(BaseModel):
    child: LinkedChild
    documents: list[ParentDocument] = []


# ── Communications ───────────────────────────────────────────────────


class ParentCommunication(BaseModel):
    id: int
    subject: Optional[str] = None
    body: str
    message_type: str
    status: str
    created_at: datetime.datetime
    sender_name: Optional[str] = None


class ParentCommunicationsResponse(BaseModel):
    communications: list[ParentCommunication] = []


# ── Dashboard ────────────────────────────────────────────────────────


class ParentChildSummary(BaseModel):
    """Per-child summary for the parent dashboard."""

    id: int
    first_name: str
    last_name: str
    student_number: str
    status: str
    relationship: str = "parent"
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    attendance_percentage: float = 0.0
    total_outstanding: int = 0
    total_paid: int = 0
    has_unread_messages: bool = False
    recent_announcements_count: int = 0


class ParentChildResponse(BaseModel):
    """Full response for a single linked child."""
    child: LinkedChild
    attendance: ParentAttendanceSummary = ParentAttendanceSummary()
    financial: ParentFinancialSummary = ParentFinancialSummary()
    current_enrollment: Optional[ParentAcademicRecord] = None
    unread_notifications: int = 0


class ParentDashboardResponse(BaseModel):
    children: list[ParentChildSummary] = []
    total_outstanding: int = 0
    total_paid: int = 0
    unread_notifications: int = 0
    recent_announcements: list[ParentAnnouncement] = []
