from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class StudentIdentity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    student_number: str
    email: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class GuardianInfo(BaseModel):
    name: str
    relationship: str
    contact: str


class ContactInfo(BaseModel):
    type: str
    value: str
    is_primary: bool = False


class EnrollmentInfo(BaseModel):
    id: int
    academic_year_id: int
    academic_year_name: Optional[str] = None
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    status: str
    enrolled_at: str


class AttendanceSummary(BaseModel):
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    percentage: float = 0.0


class FeeDueItem(BaseModel):
    id: int
    fee_type_name: Optional[str] = None
    original_amount: int
    amount_paid: int
    balance: int = 0
    due_date: Optional[str] = None
    status: str


class PaymentItem(BaseModel):
    id: int
    amount: int
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_number: Optional[str] = None
    created_at: str


class FinancialSummary(BaseModel):
    total_fees_assigned: int = 0
    total_paid: int = 0
    total_outstanding: int = 0
    unpaid_count: int = 0
    partially_paid_count: int = 0
    paid_count: int = 0


class AcademicRecord(BaseModel):
    enrollment_id: int
    academic_year_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    status: str
    enrolled_at: str


class StudentHealthInfo(BaseModel):
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    emergency_contact: Optional[str] = None


class TransportInfo(BaseModel):
    route: Optional[str] = None
    pickup_point: Optional[str] = None
    dropoff_point: Optional[str] = None
    vehicle_number: Optional[str] = None


class HostelInfo(BaseModel):
    hostel_name: Optional[str] = None
    room_number: Optional[str] = None
    bed_number: Optional[str] = None


class RiskFindingBrief(BaseModel):
    id: int
    rule_code: str
    category: str
    severity: str
    score: float
    reason: str
    recommended_action: str
    detected_at: datetime.datetime


class Student360Response(BaseModel):
    identity: StudentIdentity
    guardians: list[GuardianInfo] = []
    contacts: list[ContactInfo] = []
    enrollments: list[EnrollmentInfo] = []
    current_enrollment: Optional[EnrollmentInfo] = None
    attendance: AttendanceSummary = AttendanceSummary()
    attendance_records: list[dict] = []
    financial: FinancialSummary = FinancialSummary()
    fee_dues: list[FeeDueItem] = []
    payments: list[PaymentItem] = []
    academic_history: list[AcademicRecord] = []
    health: StudentHealthInfo = StudentHealthInfo()
    transport: Optional[TransportInfo] = None
    hostel: Optional[HostelInfo] = None
    achievements: list[dict] = []
    behavior: list[dict] = []
    communications: list[dict] = []
    risk_findings: list[RiskFindingBrief] = []
