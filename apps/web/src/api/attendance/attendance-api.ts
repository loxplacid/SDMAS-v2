import { api } from '../client/http-client'
import type {
  AttendanceRecordResponse,
  AttendanceRecordCreate,
  AttendanceRecordUpdate,
  DailyAttendanceCreate,
  StudentAttendanceSummary,
  SectionAttendanceSummary,
  Page,
} from '../generated/types'

export type AttendanceListParams = {
  page?: number
  size?: number
  student_id?: number
  section_id?: number
  status?: string
  attendance_date?: string
}

export type StudentAttendanceParams = {
  page?: number
  size?: number
  academic_year_id?: number
  class_id?: number
  section_id?: number
  status?: string
  start_date?: string
  end_date?: string
}

export const attendanceApi = {
  list: (params: AttendanceListParams = {}) =>
    api.get<Page<AttendanceRecordResponse>>(
      '/attendance',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getById: (recordId: number) =>
    api.get<AttendanceRecordResponse>(`/attendance/${recordId}`),

  record: (data: AttendanceRecordCreate) =>
    api.post<AttendanceRecordResponse>('/attendance', data),

  recordDaily: (data: DailyAttendanceCreate) =>
    api.post<AttendanceRecordResponse[]>('/attendance/daily', data),

  update: (recordId: number, data: AttendanceRecordUpdate) =>
    api.patch<AttendanceRecordResponse>(`/attendance/${recordId}`, data),

  getStudentAttendance: (studentId: number, params: StudentAttendanceParams = {}) =>
    api.get<Page<AttendanceRecordResponse>>(
      `/attendance/student/${studentId}`,
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getSectionAttendance: (sectionId: number, attendanceDate: string) =>
    api.get<AttendanceRecordResponse[]>(
      `/attendance/section/${sectionId}`,
      { attendance_date: attendanceDate },
    ),

  getStudentSummary: (studentId: number, startDate: string, endDate: string) =>
    api.get<StudentAttendanceSummary>(
      `/attendance/student/${studentId}/summary`,
      { start_date: startDate, end_date: endDate },
    ),

  getSectionSummary: (sectionId: number, attendanceDate: string) =>
    api.get<SectionAttendanceSummary>(
      `/attendance/section/${sectionId}/summary`,
      { attendance_date: attendanceDate },
    ),
}