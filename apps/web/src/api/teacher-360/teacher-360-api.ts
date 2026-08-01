import { api } from '../client/http-client'

export interface TeacherProfile {
  id: number
  first_name: string
  last_name: string
  employee_number: string
  email: string | null
  status: string
  campus_id: number | null
}

export interface TeacherSubjectItem {
  subject_id: number
  subject_name: string
  code: string | null
}

export interface AssignedClassItem {
  class_id: number
  class_name: string
  academic_year_name: string | null
  section_id: number | null
  section_name: string | null
  subject_name: string | null
  assignment_id: number
}

export interface AttendanceSummary {
  total: number
  present: number
  absent: number
  late: number
  excused: number
  percentage: number
}

export interface LeaveItem {
  id: number
  leave_type: string
  start_date: string
  end_date: string
  status: string | null
  duration_days: number
}

export interface WorkloadItem {
  assigned_classes: number
  subjects: number
  timetable_periods: number
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

export interface Teacher360Response {
  profile: TeacherProfile
  subjects: TeacherSubjectItem[]
  assignments: AssignedClassItem[]
  attendance: AttendanceSummary
  leave: LeaveItem[]
  workload: WorkloadItem
  pending_workflows: WorkflowItem[]
  recent_activity: ActivityItem[]
}

export const teacher360Api = {
  get: (teacherId: number) =>
    api.get<Teacher360Response>(`/teachers/${teacherId}/360`),
}
