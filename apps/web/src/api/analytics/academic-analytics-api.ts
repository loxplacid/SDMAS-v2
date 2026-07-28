import { api } from '../client/http-client'
import type {
  AcademicOverview,
  TeacherWorkload,
  SubjectDistribution,
} from './types'

export const academicAnalyticsApi = {
  getOverview: () =>
    api.get<AcademicOverview>('/api/analytics/academic/overview'),

  getTeacherWorkload: () =>
    api.get<TeacherWorkload[]>('/api/analytics/academic/teacher-workload'),

  getSubjectDistribution: () =>
    api.get<SubjectDistribution[]>('/api/analytics/academic/subjects'),
}
