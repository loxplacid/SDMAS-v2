import { api } from '../client/http-client'

// ── Types ───────────────────────────────────────────────────────────

export interface EnrollmentInfo {
  academic_year_name: string | null
  class_name: string | null
  section_name: string | null
  status: string
}

export interface TimetableEntryItem {
  id: number
  day_of_week: number
  day_name: string
  subject_name: string | null
  subject_code: string | null
  teacher_name: string | null
  room_name: string | null
  start_time: string | null
  end_time: string | null
  time_slot_name: string | null
}

export interface TimetableDayGroup {
  day_of_week: number
  day_name: string
  entries: TimetableEntryItem[]
}

export interface StudentTimetableResponse {
  enrollment: EnrollmentInfo | null
  days: TimetableDayGroup[]
}

export interface AttendanceSummary {
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface AttendanceRecord {
  id: number
  attendance_date: string
  status: string
  notes: string | null
}

export interface StudentAttendanceResponse {
  summary: AttendanceSummary
  records: AttendanceRecord[]
  current_streak: number
  monthly_breakdown: { month: string; total: number; present: number; percentage: number }[]
}

export interface EnrolledSubject {
  id: number
  name: string
  code: string
  teacher_name: string | null
  teacher_email: string | null
  total_hours: number | null
  syllabus: string | null
  textbook: string | null
}

export interface StudentSubjectsResponse {
  enrollment: EnrollmentInfo | null
  subjects: EnrolledSubject[]
}

export interface SubjectResult {
  subject_name: string
  subject_code: string
  marks_obtained: number | null
  max_marks: number
  grade: string | null
  grade_point: number | null
  remarks: string | null
  term_name: string | null
}

export interface TermResult {
  term_name: string
  subjects: SubjectResult[]
  total_marks: number
  total_max_marks: number
  percentage: number
  grade_point_average: number | null
}

export interface StudentResultsResponse {
  enrollment: EnrollmentInfo | null
  terms: TermResult[]
  overall_percentage: number
  overall_grade_point_average: number | null
}

export interface StudentAssignment {
  id: number
  title: string
  description: string | null
  instructions: string | null
  subject_name: string | null
  subject_code: string | null
  teacher_name: string | null
  assignment_type: string
  max_score: number | null
  due_at: string | null
  available_from: string | null
  is_published: boolean
  submission_id: number | null
  submitted_at: string | null
  score: number | null
  grade: string | null
  feedback: string | null
  submission_status: string | null
  is_late: boolean
}

export interface StudentAssignmentsResponse {
  pending: StudentAssignment[]
  submitted: StudentAssignment[]
  graded: StudentAssignment[]
  overdue: StudentAssignment[]
}

export interface StudentAnnouncement {
  id: number
  title: string | null
  body: string
  priority: string
  sender_name: string | null
  created_at: string
}

export interface StudentAnnouncementsResponse {
  announcements: StudentAnnouncement[]
}

export interface StudentDocument {
  id: number
  filename: string
  mime_type: string
  file_size: number
  category_name: string | null
  created_at: string
}

export interface StudentDocumentsResponse {
  documents: StudentDocument[]
}

export interface StudentPortalDashboardResponse {
  student_name: string
  student_number: string
  enrollment: EnrollmentInfo | null
  attendance: AttendanceSummary
  subjects_count: number
  pending_assignments: number
  overdue_assignments: number
  upcoming_timetable: TimetableEntryItem[]
  unread_notifications: number
  recent_announcements: StudentAnnouncement[]
}

// ── API Client ──────────────────────────────────────────────────────

const BASE = '/api/student/portal'

export const studentPortalApi = {
  getDashboard: () => api.get<StudentPortalDashboardResponse>(`${BASE}/dashboard`),
  getTimetable: () => api.get<StudentTimetableResponse>(`${BASE}/timetable`),
  getAttendance: (days = 365) => api.get<StudentAttendanceResponse>(`${BASE}/attendance`, { days }),
  getSubjects: () => api.get<StudentSubjectsResponse>(`${BASE}/subjects`),
  getResults: () => api.get<StudentResultsResponse>(`${BASE}/results`),
  getAssignments: () => api.get<StudentAssignmentsResponse>(`${BASE}/assignments`),
  getAnnouncements: () => api.get<StudentAnnouncementsResponse>(`${BASE}/announcements`),
  getDocuments: () => api.get<StudentDocumentsResponse>(`${BASE}/documents`),
}
