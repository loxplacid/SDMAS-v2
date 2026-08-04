import { api } from '../client/http-client'
import type {
  StudentIdentity,
  EnrollmentInfo,
  AttendanceSummary,
  FinancialSummary,
  FeeDueItem,
  PaymentItem,
  AcademicRecord,
  StudentHealthInfo,
  TransportInfo,
  HostelInfo,
  StudentLifecycleSummary,
  StudentDocumentBrief,
} from './types'

export interface Student360Response {
  identity: StudentIdentity
  guardians: { name: string; relationship: string; contact: string }[]
  contacts: { type: string; value: string; is_primary: boolean }[]
  enrollments: EnrollmentInfo[]
  current_enrollment: EnrollmentInfo | null
  attendance: AttendanceSummary
  attendance_records: { id: number; attendance_date: string; status: string; notes: string | null }[]
  financial: FinancialSummary
  fee_dues: FeeDueItem[]
  payments: PaymentItem[]
  academic_history: AcademicRecord[]
  health: StudentHealthInfo
  transport: TransportInfo | null
  hostel: HostelInfo | null
  achievements: Record<string, unknown>[]
  behavior: Record<string, unknown>[]
  communications: Record<string, unknown>[]
  risk_findings: RiskFindingBrief[]
  lifecycle: StudentLifecycleSummary | null
  documents: StudentDocumentBrief[]
}

export interface RiskFindingBrief {
  id: number
  rule_code: string
  category: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  score: number
  reason: string
  recommended_action: string
  detected_at: string
}

export interface LifecycleTransitionInput {
  to_status: string
  reason?: string | null
}

export interface LifecycleState {
  student_id: number
  current_status: string
  allowed_transitions: string[]
  lifecycle_order: string[]
  recent_events: StudentLifecycleSummary['recent_events']
}

export const student360Api = {
  get: (studentId: number) =>
    api.get<Student360Response>(`/students/${studentId}/360`),
  transition: (studentId: number, input: LifecycleTransitionInput) =>
    api.post<LifecycleState>(`/students/${studentId}/lifecycle/transitions`, input),
}
