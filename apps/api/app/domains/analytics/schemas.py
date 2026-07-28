from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class AnalyticsOverview(BaseModel):
    total_students: int
    active_students: int
    inactive_students: int
    current_academic_year: Optional[str] = None
    total_classes: int
    total_sections: int
    total_teachers: int
    total_subjects: int
    overall_attendance_percentage: float = 0.0
    total_collected: int = 0
    total_outstanding: int = 0
    collection_percentage: float = 0.0
    low_attendance_count: int = 0
    unpaid_count: int = 0
    partially_paid_count: int = 0


# ---------------------------------------------------------------------------
# Attendance analytics
# ---------------------------------------------------------------------------


class AttendanceOverview(BaseModel):
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    attendance_percentage: float


class AttendanceTrendPoint(BaseModel):
    date: str
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    total: int = 0


class AttendanceTrend(BaseModel):
    trend: list[AttendanceTrendPoint]
    granularity: str  # daily, weekly, monthly


class ClassAttendanceComparison(BaseModel):
    class_id: int
    class_name: str
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    attendance_percentage: float


class SectionAttendanceComparison(BaseModel):
    section_id: int
    section_name: str
    class_name: str
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    attendance_percentage: float


class LowAttendanceStudent(BaseModel):
    student_id: int
    student_name: str
    student_number: str
    total_records: int
    present_count: int
    attendance_percentage: float
    threshold: int


class TermAttendanceAnalytics(BaseModel):
    term_id: int
    term_name: str
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    attendance_percentage: float


# ---------------------------------------------------------------------------
# Financial analytics
# ---------------------------------------------------------------------------


class FinanceOverview(BaseModel):
    total_fees_amount: int
    total_collected: int
    total_outstanding: int
    collection_percentage: float
    students_with_outstanding: int
    fully_paid_students: int
    partially_paid_students: int
    unpaid_students: int


class CollectionTrendPoint(BaseModel):
    date: str
    amount: int = 0
    count: int = 0


class CollectionTrend(BaseModel):
    trend: list[CollectionTrendPoint]
    granularity: str


class FeeTypeCollection(BaseModel):
    fee_type_id: int
    fee_type_name: str
    total_expected: int
    total_collected: int
    outstanding: int
    collection_percentage: float


class ClassFeeCollection(BaseModel):
    class_id: int
    class_name: str
    total_expected: int
    total_collected: int
    outstanding: int
    collection_percentage: float


class PaymentMethodDistribution(BaseModel):
    payment_method: str
    transaction_count: int
    total_amount: int


class FeeStatusDistribution(BaseModel):
    status: str
    count: int
    total_amount: int


# ---------------------------------------------------------------------------
# Student analytics
# ---------------------------------------------------------------------------


class StudentOverview(BaseModel):
    total_students: int
    active_students: int
    inactive_students: int


class StudentsByClass(BaseModel):
    class_id: int
    class_name: str
    student_count: int


class StudentsBySection(BaseModel):
    section_id: int
    section_name: str
    class_name: str
    student_count: int


class EnrollmentTrend(BaseModel):
    academic_year_id: int
    academic_year_name: str
    enrollment_count: int


# ---------------------------------------------------------------------------
# Academic analytics
# ---------------------------------------------------------------------------


class AcademicOverview(BaseModel):
    active_academic_year: Optional[str] = None
    total_classes: int
    total_sections: int
    total_teachers: int
    total_subjects: int
    total_terms: int


class TeacherWorkload(BaseModel):
    teacher_id: int
    teacher_name: str
    employee_number: str
    assignment_count: int
    subjects: list[str]
    classes: list[str]


class SubjectDistribution(BaseModel):
    subject_id: int
    subject_name: str
    subject_code: str
    assignment_count: int
