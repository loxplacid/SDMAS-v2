import { api } from '../client/http-client'
import type {
  AttendanceOverview,
  AttendanceTrend,
  ClassAttendanceComparison,
  SectionAttendanceComparison,
  LowAttendanceStudent,
  TermAttendanceAnalytics,
} from './types'

export type AttendanceAnalyticsParams = {
  academic_year_id?: number
  class_id?: number
  section_id?: number
  granularity?: string
  threshold?: number
  min_records?: number
}

export const attendanceAnalyticsApi = {
  getOverview: (params: AttendanceAnalyticsParams = {}) =>
    api.get<AttendanceOverview>('/api/analytics/attendance/overview', params as any),

  getTrends: (params: AttendanceAnalyticsParams = {}) =>
    api.get<AttendanceTrend>('/api/analytics/attendance/trends', params as any),

  getClassComparison: (params: AttendanceAnalyticsParams = {}) =>
    api.get<ClassAttendanceComparison[]>('/api/analytics/attendance/classes', params as any),

  getSectionComparison: (params: AttendanceAnalyticsParams = {}) =>
    api.get<SectionAttendanceComparison[]>('/api/analytics/attendance/sections', params as any),

  getLowAttendance: (params: AttendanceAnalyticsParams = {}) =>
    api.get<LowAttendanceStudent[]>('/api/analytics/attendance/low-attendance', params as any),

  getTermAttendance: (params: AttendanceAnalyticsParams = {}) =>
    api.get<TermAttendanceAnalytics[]>('/api/analytics/attendance/terms', params as any),
}
