"""Response schemas for the Teacher 360 view."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class TeacherProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    employee_number: str
    email: Optional[str] = None
    status: str
    campus_id: Optional[int] = None


class TeacherSubjectItem(BaseModel):
    subject_id: int
    subject_name: str
    code: Optional[str] = None


class AssignedClassItem(BaseModel):
    class_id: int
    class_name: str
    academic_year_name: Optional[str] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    subject_name: Optional[str] = None
    assignment_id: int


class AttendanceSummary(BaseModel):
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    percentage: float = 0.0


class LeaveItem(BaseModel):
    id: int
    leave_type: str
    start_date: str
    end_date: str
    status: Optional[str] = None
    duration_days: int = 0


class WorkloadItem(BaseModel):
    assigned_classes: int = 0
    subjects: int = 0
    timetable_periods: int = 0


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


class Teacher360Response(BaseModel):
    profile: TeacherProfile
    subjects: list[TeacherSubjectItem] = []
    assignments: list[AssignedClassItem] = []
    attendance: AttendanceSummary = AttendanceSummary()
    leave: list[LeaveItem] = []
    workload: WorkloadItem = WorkloadItem()
    pending_workflows: list[WorkflowItem] = []
    recent_activity: list[ActivityItem] = []
