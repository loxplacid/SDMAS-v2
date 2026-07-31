import { api } from '../client/http-client'

// ── Types ───────────────────────────────────────────────────────────

export interface LinkedChild {
  id: number
  first_name: string
  last_name: string
  student_number: string
  email: string | null
  status: string
  relationship: string
  is_primary: boolean
}

export interface ParentChildSummary {
  id: number
  first_name: string
  last_name: string
  student_number: string
  status: string
  relationship: string
  class_name: string | null
  section_name: string | null
  attendance_percentage: number
  total_outstanding: number
  total_paid: number
  has_unread_messages: boolean
  recent_announcements_count: number
}

export interface ParentAttendanceSummary {
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface ParentAttendanceRecord {
  id: number
  attendance_date: string
  status: string
  notes: string | null
}

export interface ParentAttendanceResponse {
  child: LinkedChild
  summary: ParentAttendanceSummary
  records: ParentAttendanceRecord[]
  current_streak: number
  days_since_last_absence: number
}

export interface ParentFinancialSummary {
  total_fees_assigned: number
  total_paid: number
  total_outstanding: number
  unpaid_count: number
  partially_paid_count: number
  paid_count: number
}

export interface ParentFeeDue {
  id: number
  fee_type_name: string | null
  original_amount: number
  amount_paid: number
  balance: number
  due_date: string | null
  status: string
}

export interface ParentPayment {
  id: number
  amount: number
  payment_date: string | null
  payment_method: string | null
  receipt_number: string | null
  created_at: string
}

export interface ParentFeesResponse {
  child: LinkedChild
  summary: ParentFinancialSummary
  dues: ParentFeeDue[]
  payments: ParentPayment[]
}

export interface ParentAcademicRecord {
  academic_year_name: string | null
  class_name: string | null
  section_name: string | null
  status: string
}

export interface ParentSubjectGrade {
  subject_name: string
  grade: string | null
  score: number | null
  remarks: string | null
}

export interface ParentAcademicResponse {
  child: LinkedChild
  current_enrollment: ParentAcademicRecord | null
  academic_history: ParentAcademicRecord[]
  grades: ParentSubjectGrade[]
  attendance_summary: ParentAttendanceSummary
}

export interface ParentAnnouncement {
  id: number
  title: string | null
  body: string
  priority: string
  created_at: string
  sender_name: string | null
}

export interface ParentAnnouncementsResponse {
  announcements: ParentAnnouncement[]
}

export interface ParentDocument {
  id: number
  filename: string
  mime_type: string
  file_size: number
  created_at: string
  category_name: string | null
}

export interface ParentDocumentsResponse {
  child: LinkedChild
  documents: ParentDocument[]
}

export interface ParentCommunication {
  id: number
  subject: string | null
  body: string
  message_type: string
  status: string
  created_at: string
  sender_name: string | null
}

export interface ParentCommunicationsResponse {
  communications: ParentCommunication[]
}

export interface ParentDashboardResponse {
  children: ParentChildSummary[]
  total_outstanding: number
  total_paid: number
  unread_notifications: number
  recent_announcements: ParentAnnouncement[]
}

export interface ParentChildResponse {
  child: LinkedChild
  attendance: ParentAttendanceSummary
  financial: ParentFinancialSummary
  current_enrollment: ParentAcademicRecord | null
  unread_notifications: number
}

// ── API Client ──────────────────────────────────────────────────────

const BASE = '/api/parent'

export const parentApi = {
  // Dashboard
  getDashboard: () => api.get<ParentDashboardResponse>(`${BASE}/dashboard`),

  // Children
  listChildren: () => api.get<LinkedChild[]>(`${BASE}/children`),
  getChild: (studentId: number) => api.get<ParentChildResponse>(`${BASE}/children/${studentId}`),
  linkChild: (studentId: number, relationship = 'parent') =>
    api.post<LinkedChild>(`${BASE}/children/link`, { student_id: studentId, relationship }),
  unlinkChild: (studentId: number) => api.delete(`${BASE}/children/${studentId}`),

  // Attendance
  getChildAttendance: (studentId: number, days = 90) =>
    api.get<ParentAttendanceResponse>(`${BASE}/children/${studentId}/attendance`, { days }),

  // Fees
  getChildFees: (studentId: number) =>
    api.get<ParentFeesResponse>(`${BASE}/children/${studentId}/fees`),

  // Academic
  getChildAcademic: (studentId: number) =>
    api.get<ParentAcademicResponse>(`${BASE}/children/${studentId}/academic`),

  // Documents
  getChildDocuments: (studentId: number) =>
    api.get<ParentDocumentsResponse>(`${BASE}/children/${studentId}/documents`),

  // Announcements
  getAnnouncements: () => api.get<ParentAnnouncementsResponse>(`${BASE}/announcements`),

  // Communications
  getCommunications: () => api.get<ParentCommunicationsResponse>(`${BASE}/communications`),
}
