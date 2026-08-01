import { api } from '../client/http-client'

export interface ClassIdentity {
  id: number
  name: string
  academic_year_id: number | null
  academic_year_name: string | null
  status: string
  campus_id: number | null
}

export interface SectionSummary {
  id: number
  name: string
  status: string
  student_count: number
}

export interface AttendanceSummary {
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface FeeSummary {
  total_assigned: number
  total_collected: number
  total_outstanding: number
  students_with_outstanding: number
}

export interface TeacherAssignmentItem {
  teacher_id: number
  teacher_name: string
  subject_id: number | null
  subject_name: string | null
}

export interface SubjectSummary {
  id: number
  name: string
  code: string | null
}

export interface StudentAttentionItem {
  student_id: number
  student_number: string
  full_name: string
  reason: string
  attendance_percentage: number
  outstanding: number
}

export interface AcademicPerformanceItem {
  subject_id: number
  subject_name: string
  average_percentage: number
  records: number
}

export interface WorkflowItem {
  id: number
  workflow_name: string
  entity_type: string
  entity_id: number | null
  status: string
  current_step: string | null
  created_at: string
}

export interface ActivityItem {
  date: string
  action: string
  resource_type: string | null
  user_id: number | null
  details: string | null
}

export interface Class360Response {
  identity: ClassIdentity
  sections: SectionSummary[]
  student_count: number
  attendance: AttendanceSummary
  fees: FeeSummary
  teachers: TeacherAssignmentItem[]
  subjects: SubjectSummary[]
  students_requiring_attention: StudentAttentionItem[]
  academic_performance: AcademicPerformanceItem[]
  pending_workflows: WorkflowItem[]
  recent_activity: ActivityItem[]
}

export const class360Api = {
  get: (classId: number) =>
    api.get<Class360Response>(`/classes/${classId}/360`),
}
