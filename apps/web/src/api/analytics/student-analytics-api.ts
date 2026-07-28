import { api } from '../client/http-client'
import type {
  StudentOverview,
  StudentsByClass,
  StudentsBySection,
  EnrollmentTrend,
} from './types'

export type StudentAnalyticsParams = {
  academic_year_id?: number
  class_id?: number
}

export const studentAnalyticsApi = {
  getOverview: () =>
    api.get<StudentOverview>('/api/analytics/students/overview'),

  getByClass: (params: StudentAnalyticsParams = {}) =>
    api.get<StudentsByClass[]>('/api/analytics/students/classes', params as any),

  getBySection: (params: StudentAnalyticsParams = {}) =>
    api.get<StudentsBySection[]>('/api/analytics/students/sections', params as any),

  getEnrollmentTrends: () =>
    api.get<EnrollmentTrend[]>('/api/analytics/students/enrollment-trends'),
}
