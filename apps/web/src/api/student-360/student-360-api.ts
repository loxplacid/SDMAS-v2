import { api } from '../client/http-client'
import type {
  StudentIdentity,
  EnrollmentInfo,
  AttendanceSummary,
  FinancialSummary,
  FeeDueItem,
  PaymentItem,
  AcademicRecord,
  TimelineEvent,
  StudentHealthInfo,
  TransportInfo,
  HostelInfo,
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
  timeline: TimelineEvent[]
  achievements: Record<string, unknown>[]
  behavior: Record<string, unknown>[]
  communications: Record<string, unknown>[]
}

export const student360Api = {
  get: (studentId: number) =>
    api.get<Student360Response>(`/students/${studentId}/360`),
}
