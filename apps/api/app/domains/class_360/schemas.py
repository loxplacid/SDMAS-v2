"""Response schemas for the Class 360 view."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ClassIdentity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year_id: Optional[int] = None
    academic_year_name: Optional[str] = None
    status: str
    campus_id: Optional[int] = None


class SectionSummary(BaseModel):
    id: int
    name: str
    status: str = "active"
    student_count: int = 0


class AttendanceSummary(BaseModel):
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    percentage: float = 0.0


class FeeSummary(BaseModel):
    total_assigned: int = 0
    total_collected: int = 0
    total_outstanding: int = 0
    students_with_outstanding: int = 0


class TeacherAssignmentItem(BaseModel):
    teacher_id: int
    teacher_name: str
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None


class SubjectSummary(BaseModel):
    id: int
    name: str
    code: Optional[str] = None


class StudentAttentionItem(BaseModel):
    student_id: int
    student_number: str
    full_name: str
    reason: str
    attendance_percentage: float = 0.0
    outstanding: int = 0


class AcademicPerformanceItem(BaseModel):
    subject_id: int
    subject_name: str
    average_percentage: float = 0.0
    records: int = 0


class WorkflowItem(BaseModel):
    id: int
    workflow_name: str
    entity_type: str = ""
    entity_id: Optional[int] = None
    status: str = ""
    current_step: Optional[str] = None
    created_at: str = ""


class ActivityItem(BaseModel):
    date: str
    action: str
    resource_type: Optional[str] = None
    user_id: Optional[int] = None
    details: Optional[str] = None


class Class360Response(BaseModel):
    identity: ClassIdentity
    sections: list[SectionSummary] = []
    student_count: int = 0
    attendance: AttendanceSummary = AttendanceSummary()
    fees: FeeSummary = FeeSummary()
    teachers: list[TeacherAssignmentItem] = []
    subjects: list[SubjectSummary] = []
    students_requiring_attention: list[StudentAttentionItem] = []
    academic_performance: list[AcademicPerformanceItem] = []
    pending_workflows: list[WorkflowItem] = []
    recent_activity: list[ActivityItem] = []
