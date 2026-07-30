import { api } from '../client/http-client'
import type { Page } from '../generated/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AdmissionApplicationResponse {
  id: number
  campus_id: number | null
  academic_year_id: number | null
  program_id: number | null
  branch_id: number | null
  semester_id: number | null
  applicant_name: string
  date_of_birth: string | null
  email: string | null
  phone: string | null
  address: string | null
  source: string | null
  previous_education: string | null
  entrance_score: number | null
  status: string
  remarks: string | null
  applied_at: string | null
  enrolled_at: string | null
  created_at: string
  updated_at: string
}

export interface AdmissionApplicationCreate {
  applicant_name: string
  date_of_birth?: string | null
  email?: string | null
  phone?: string | null
  address?: string | null
  campus_id?: number | null
  academic_year_id?: number | null
  program_id?: number | null
  branch_id?: number | null
  semester_id?: number | null
  source?: string | null
  previous_education?: string | null
  entrance_score?: number | null
}

export interface AdmissionApplicationUpdate {
  applicant_name?: string | null
  date_of_birth?: string | null
  email?: string | null
  phone?: string | null
  address?: string | null
  academic_year_id?: number | null
  program_id?: number | null
  branch_id?: number | null
  semester_id?: number | null
  source?: string | null
  previous_education?: string | null
  entrance_score?: number | null
  remarks?: string | null
}

export interface AdmissionStatusTransition {
  new_status: string
  remarks?: string | null
}

export interface AdmissionDocumentResponse {
  id: number
  application_id: number
  document_type: string
  file_name: string
  file_url: string | null
  verification_status: string
  verified_by: number | null
  verified_at: string | null
  remarks: string | null
  created_at: string
}

export interface AdmissionDocumentCreate {
  document_type: string
  file_name: string
  file_url?: string | null
}

export interface AdmissionInterviewResponse {
  id: number
  application_id: number
  scheduled_date: string | null
  interview_mode: string | null
  panel_members: string | null
  score: number | null
  remarks: string | null
  status: string
  created_at: string
}

export interface AdmissionInterviewCreate {
  scheduled_date?: string | null
  interview_mode?: string | null
  panel_members?: string | null
}

export interface AdmissionMeritEntryResponse {
  id: number
  application_id: number
  program_id: number
  academic_year_id: number
  total_score: number
  rank: number
  category: string | null
  status: string
  created_at: string
}

export interface AdmissionSeatAllocationResponse {
  id: number
  application_id: number
  merit_entry_id: number | null
  program_id: number
  branch_id: number | null
  fee_amount: number
  allocated_at: string | null
  paid_at: string | null
  enrolled_at: string | null
  status: string
  created_at: string
}

export type ApplicationListParams = {
  page?: number
  size?: number
  status?: string
  campus_id?: number
  program_id?: number
  academic_year_id?: number
  search?: string
}

// ---------------------------------------------------------------------------
// Admission Status Constants
// ---------------------------------------------------------------------------

export const ADMISSION_STATUSES = [
  'inquiry',
  'application_submitted',
  'documents_uploaded',
  'verified',
  'interview_scheduled',
  'interview_completed',
  'merit_listed',
  'seat_allocated',
  'fee_paid',
  'enrolled',
  'student_created',
  'rejected',
] as const

export type AdmissionStatus = (typeof ADMISSION_STATUSES)[number]

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------

export const admissionApi = {
  // Applications
  listApplications: (params: ApplicationListParams = {}) =>
    api.get<Page<AdmissionApplicationResponse>>(
      '/api/admissions/applications',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getApplication: (id: number) =>
    api.get<AdmissionApplicationResponse>(`/api/admissions/applications/${id}`),

  createApplication: (data: AdmissionApplicationCreate) =>
    api.post<AdmissionApplicationResponse>('/api/admissions/applications', data, true),

  updateApplication: (id: number, data: AdmissionApplicationUpdate) =>
    api.patch<AdmissionApplicationResponse>(`/api/admissions/applications/${id}`, data),

  deleteApplication: (id: number) =>
    api.delete<void>(`/api/admissions/applications/${id}`),

  transitionStatus: (id: number, data: AdmissionStatusTransition) =>
    api.post<AdmissionApplicationResponse>(
      `/api/admissions/applications/${id}/transition`,
      data,
    ),

  // Documents
  uploadDocument: (applicationId: number, data: AdmissionDocumentCreate) =>
    api.post<AdmissionDocumentResponse>(
      `/api/admissions/applications/${applicationId}/documents`,
      data,
      true,
    ),

  getApplicationDocuments: (applicationId: number) =>
    api.get<AdmissionDocumentResponse[]>(
      `/api/admissions/applications/${applicationId}/documents`,
    ),

  verifyDocument: (documentId: number, verificationStatus: string) =>
    api.patch<AdmissionDocumentResponse>(
      `/api/admissions/documents/${documentId}/verify`,
      { verification_status: verificationStatus },
    ),

  deleteDocument: (documentId: number) =>
    api.delete<void>(`/api/admissions/documents/${documentId}`),

  // Interviews
  scheduleInterview: (applicationId: number, data: AdmissionInterviewCreate) =>
    api.post<AdmissionInterviewResponse>(
      `/api/admissions/applications/${applicationId}/interviews`,
      data,
      true,
    ),

  getApplicationInterviews: (applicationId: number) =>
    api.get<AdmissionInterviewResponse[]>(
      `/api/admissions/applications/${applicationId}/interviews`,
    ),

  updateInterview: (interviewId: number, data: Partial<AdmissionInterviewCreate & { score: number | null; status: string; remarks: string | null }>) =>
    api.patch<AdmissionInterviewResponse>(`/api/admissions/interviews/${interviewId}`, data),

  // Merit Entries
  listMeritEntries: (params: { program_id?: number; academic_year_id?: number; status?: string; page?: number; size?: number } = {}) =>
    api.get<Page<AdmissionMeritEntryResponse>>('/api/admissions/merit-entries', params as Record<string, string | number | boolean | undefined | null>),

  // Seat Allocations
  getApplicationAllocations: (applicationId: number) =>
    api.get<AdmissionSeatAllocationResponse[]>(
      `/api/admissions/applications/${applicationId}/seat-allocations`,
    ),
}
