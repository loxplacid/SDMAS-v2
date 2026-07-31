import { api } from '../client/http-client'

export type AttendanceIntelligenceListParams = {
  page?: number
  size?: number
  section_id?: number
  class_id?: number
  subject_id?: number
  teacher_id?: number
  academic_year_id?: number
  from_date?: string
  to_date?: string
  status?: string
}

export interface PeriodAttendanceRecordItem {
  id: number
  period_attendance_id: number
  student_id: number
  status: string
  arrival_time: string | null
  departure_time: string | null
  late_minutes: number | null
  early_departure_minutes: number | null
  absence_reason_id: number | null
  notes: string | null
}

export interface PeriodAttendanceResponse {
  id: number
  academic_year_id: number
  class_id: number
  section_id: number
  subject_id: number
  teacher_id: number
  attendance_date: string
  period_number: number
  start_time: string
  end_time: string
  campus_id: number | null
  status: string
  notes: string | null
  records: PeriodAttendanceRecordItem[]
}

export interface AbsenceReasonResponse {
  id: number
  name: string
  code: string
  description: string | null
  requires_approval: boolean
  campus_id: number | null
  status: string
}

export interface AttendanceCorrectionResponse {
  id: number
  record_type: string
  record_id: number
  requested_by: number
  requested_status: string
  previous_status: string | null
  absence_reason_id: number | null
  reason: string | null
  status: string
  reviewed_by: number | null
  reviewed_at: string | null
  review_notes: string | null
  campus_id: number | null
  created_at: string
  updated_at: string
}

export interface AttendanceThresholdResponse {
  id: number
  campus_id: number | null
  academic_year_id: number | null
  name: string
  threshold_type: string
  percentage: number
  days_absent_threshold: number | null
  consecutive_absences: number | null
  notification_enabled: boolean
  notification_channels: string | null
  applies_to: string | null
  status: string
}

export interface StudentAttendanceTrend {
  student_id: number
  start_date: string
  end_date: string
  total_periods: number
  present_count: number
  absent_count: number
  late_count: number
  excused_count: number
  attendance_percentage: number
  late_arrivals: number
  early_departures: number
}

export interface ClassAttendanceTrend {
  class_id: number
  start_date: string
  end_date: string
  total_students: number
  total_periods: number
  average_attendance_percentage: number
}

export interface SectionAttendanceTrend {
  section_id: number
  class_id: number
  start_date: string
  end_date: string
  total_students: number
  total_periods: number
  average_attendance_percentage: number
}

export interface ChronicAbsenteeismRecord {
  student_id: number
  total_periods: number
  absent_count: number
  attendance_percentage: number
  consecutive_absences: number
  threshold: number
  threshold_name: string
}

export interface LowAttendanceAlertItem {
  student_id: number
  attendance_percentage: number
  threshold: number
  threshold_name: string
  total_absences: number
}

export interface AttendanceIntelligenceDashboard {
  total_students: number
  overall_attendance_percentage: number
  present_today: number
  absent_today: number
  late_today: number
  chronic_count: number
  low_attendance_alerts: LowAttendanceAlertItem[]
  top_absenteeism: ChronicAbsenteeismRecord[]
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export const attendanceIntelligenceApi = {
  // Period Attendance
  createPeriodAttendance: (data: any) =>
    api.post<PeriodAttendanceResponse>('/api/attendance-intelligence/period-attendance', data),

  getPeriodAttendance: (id: number) =>
    api.get<PeriodAttendanceResponse>(`/api/attendance-intelligence/period-attendance/${id}`),

  listPeriodAttendance: (params: AttendanceIntelligenceListParams = {}) =>
    api.get<Page<PeriodAttendanceResponse>>('/api/attendance-intelligence/period-attendance', params as any),

  updatePeriodRecord: (recordId: number, data: any) =>
    api.patch<PeriodAttendanceRecordItem>(`/api/attendance-intelligence/period-attendance/records/${recordId}`, data),

  getStudentPeriodRecords: (studentId: number, params: any = {}) =>
    api.get<Page<PeriodAttendanceRecordItem>>(`/api/attendance-intelligence/period-attendance/student/${studentId}`, params as any),

  // Absence Reasons
  createAbsenceReason: (data: any) =>
    api.post<AbsenceReasonResponse>('/api/attendance-intelligence/absence-reasons', data),

  listAbsenceReasons: (params: any = {}) =>
    api.get<Page<AbsenceReasonResponse>>('/api/attendance-intelligence/absence-reasons', params as any),

  updateAbsenceReason: (id: number, data: any) =>
    api.patch<AbsenceReasonResponse>(`/api/attendance-intelligence/absence-reasons/${id}`, data),

  deleteAbsenceReason: (id: number) =>
    api.delete(`/api/attendance-intelligence/absence-reasons/${id}`),

  // Corrections
  createCorrection: (data: any) =>
    api.post<AttendanceCorrectionResponse>('/api/attendance-intelligence/corrections', data),

  listCorrections: (params: any = {}) =>
    api.get<Page<AttendanceCorrectionResponse>>('/api/attendance-intelligence/corrections', params as any),

  approveCorrection: (id: number, reviewNotes?: string) =>
    api.post<AttendanceCorrectionResponse>(`/api/attendance-intelligence/corrections/${id}/approve`, { review_notes: reviewNotes }),

  declineCorrection: (id: number, reviewNotes?: string) =>
    api.post<AttendanceCorrectionResponse>(`/api/attendance-intelligence/corrections/${id}/decline`, { review_notes: reviewNotes }),

  // Thresholds
  createThreshold: (data: any) =>
    api.post<AttendanceThresholdResponse>('/api/attendance-intelligence/thresholds', data),

  listThresholds: (params: any = {}) =>
    api.get<Page<AttendanceThresholdResponse>>('/api/attendance-intelligence/thresholds', params as any),

  updateThreshold: (id: number, data: any) =>
    api.patch<AttendanceThresholdResponse>(`/api/attendance-intelligence/thresholds/${id}`, data),

  deleteThreshold: (id: number) =>
    api.delete(`/api/attendance-intelligence/thresholds/${id}`),

  // Analytics
  getStudentTrend: (studentId: number, startDate: string, endDate: string) =>
    api.get<StudentAttendanceTrend>(`/api/attendance-intelligence/analytics/student/${studentId}/trend`, { start_date: startDate, end_date: endDate }),

  getClassTrend: (classId: number, startDate: string, endDate: string) =>
    api.get<ClassAttendanceTrend>(`/api/attendance-intelligence/analytics/class/${classId}/trend`, { start_date: startDate, end_date: endDate }),

  getSectionTrend: (sectionId: number, startDate: string, endDate: string) =>
    api.get<SectionAttendanceTrend>(`/api/attendance-intelligence/analytics/section/${sectionId}/trend`, { start_date: startDate, end_date: endDate }),

  getChronicAbsenteeism: (params: any = {}) =>
    api.get<ChronicAbsenteeismRecord[]>('/api/attendance-intelligence/analytics/chronic-absenteeism', params as any),

  getLowAttendanceAlerts: (params: any = {}) =>
    api.get<LowAttendanceAlertItem[]>('/api/attendance-intelligence/analytics/low-attendance-alerts', params as any),

  getDashboard: (params: any = {}) =>
    api.get<AttendanceIntelligenceDashboard>('/api/attendance-intelligence/dashboard', params as any),
}
