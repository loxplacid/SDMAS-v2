export interface StudentIdentity {
  id: number
  first_name: string
  last_name: string
  student_number: string
  email: string | null
  date_of_birth: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface GuardianInfo {
  name: string
  relationship: string
  contact: string
}

export interface ContactInfo {
  type: string
  value: string
  is_primary: boolean
}

export interface EnrollmentInfo {
  id: number
  academic_year_id: number
  academic_year_name: string | null
  class_id: number | null
  class_name: string | null
  section_id: number | null
  section_name: string | null
  status: string
  enrolled_at: string
}

export interface AttendanceSummary {
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface FeeDueItem {
  id: number
  fee_type_name: string | null
  original_amount: number
  amount_paid: number
  balance: number
  due_date: string | null
  status: string
}

export interface PaymentItem {
  id: number
  amount: number
  payment_date: string | null
  payment_method: string | null
  receipt_number: string | null
  created_at: string
}

export interface FinancialSummary {
  total_fees_assigned: number
  total_paid: number
  total_outstanding: number
  unpaid_count: number
  partially_paid_count: number
  paid_count: number
}

export interface AcademicRecord {
  enrollment_id: number
  academic_year_name: string | null
  class_name: string | null
  section_name: string | null
  status: string
  enrolled_at: string
}

export interface StudentHealthInfo {
  blood_group: string | null
  allergies: string | null
  medical_conditions: string | null
  emergency_contact: string | null
}

export interface TransportInfo {
  route: string | null
  pickup_point: string | null
  dropoff_point: string | null
  vehicle_number: string | null
}

export interface HostelInfo {
  hostel_name: string | null
  room_number: string | null
  bed_number: string | null
}

export interface StudentLifecycleEvent {
  id: number
  from_status: string
  to_status: string
  reason: string | null
  created_at: string
}

export interface StudentLifecycleSummary {
  current_status: string
  allowed_transitions: string[]
  lifecycle_order: string[]
  recent_events: StudentLifecycleEvent[]
}

export interface StudentDocumentBrief {
  id: number
  title: string
  category: string | null
  mime_type: string | null
  file_size: number
  uploaded_at: string | null
  lifecycle_state: string | null
}
