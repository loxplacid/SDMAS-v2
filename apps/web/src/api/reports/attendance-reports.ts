import { api } from '../client/http-client'
import type { ClassAttendanceSummaryReport, SectionAttendanceSummaryReport } from './types'

export type AttendanceReportParams = {
  academic_year_id?: number
  start_date?: string
  end_date?: string
}

export const attendanceReportApi = {
  getClassReport: (classId: number, params: AttendanceReportParams) =>
    api.get<ClassAttendanceSummaryReport>(
      `/api/reports/attendance/class/${classId}`,
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getSectionReport: (sectionId: number, params: AttendanceReportParams) =>
    api.get<SectionAttendanceSummaryReport>(
      `/api/reports/attendance/section/${sectionId}`,
      params as Record<string, string | number | boolean | undefined | null>,
    ),
}