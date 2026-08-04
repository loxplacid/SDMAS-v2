from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Report card (single student)
# ---------------------------------------------------------------------------


class ReportCardSubject(BaseModel):
    """One subject line inside a report card term block."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    subject_name: str
    subject_code: str
    marks_obtained: Optional[float] = None
    max_marks: int = 100
    grade: Optional[str] = None
    grade_point: Optional[float] = None
    remarks: Optional[str] = None


class ReportCardTerm(BaseModel):
    """Per-term breakdown of a student's report card."""

    term_id: Optional[int] = None
    term_name: str = "General"
    subjects: List[ReportCardSubject] = []
    total_marks: float = 0
    total_max_marks: int = 0
    percentage: Optional[float] = None
    grade_point_average: Optional[float] = None


class AttendanceSummaryOut(BaseModel):
    """Attendance summary embedded in a report card."""

    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    percentage: float = 0.0


class StudentReportCard(BaseModel):
    """Full report card for one student in one academic year."""

    student_id: int
    student_name: str
    student_number: str
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    academic_year_name: str
    term_filter: Optional[str] = None
    terms: List[ReportCardTerm] = []
    overall_percentage: Optional[float] = None
    overall_grade_point_average: Optional[float] = None
    attendance: AttendanceSummaryOut = AttendanceSummaryOut()
    teacher_remarks: List[str] = []


# ---------------------------------------------------------------------------
# Class marksheet (list of students x subjects)
# ---------------------------------------------------------------------------


class MarksheetCell(BaseModel):
    """One subject cell inside a class marksheet row."""

    subject_id: int
    subject_name: str
    subject_code: str
    marks_obtained: Optional[float] = None
    max_marks: int = 100
    grade: Optional[str] = None
    grade_point: Optional[float] = None


class ClassMarksheetRow(BaseModel):
    """One student's row in the class marksheet."""

    student_id: int
    student_name: str
    student_number: str
    subjects: List[MarksheetCell] = []
    total_marks: float = 0
    max_marks: int = 0
    percentage: Optional[float] = None
    grade_point_average: Optional[float] = None
    attendance_percentage: Optional[float] = None


class MarksheetSubject(BaseModel):
    """One subject column in a class marksheet."""

    id: int
    name: str
    code: str


class ClassMarksheet(BaseModel):
    """Marksheet listing every enrolled student in a class."""

    class_id: int
    class_name: str
    academic_year_name: str
    term_filter: Optional[str] = None
    subjects: List[MarksheetSubject] = []  # the column set
    rows: List[ClassMarksheetRow] = []
