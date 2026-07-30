import { api } from '../client/http-client'
import type { Page } from '../generated/types'

export interface LeaveRequestResponse {
  id: number
  user_id: number
  leave_type: string
  start_date: string
  end_date: string
  reason: string | null
  duration_days: number
  workflow_instance_id: number | null
  created_at: string
  updated_at: string
}

export interface LeaveRequestDetailResponse extends LeaveRequestResponse {
  workflow_status: string | null
  workflow_current_step: string | null
}

export interface LeaveRequestCreate {
  leave_type: string
  start_date: string
  end_date: string
  reason?: string | null
}

export const LEAVE_TYPES = ['sick', 'casual', 'annual', 'personal', 'maternity', 'paternity', 'study', 'other'] as const

export const leaveApi = {
  list: (params: { page?: number; size?: number; leave_type?: string } = {}) =>
    api.get<Page<LeaveRequestResponse>>('/api/leave', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<LeaveRequestDetailResponse>(`/api/leave/${id}`),

  create: (data: LeaveRequestCreate) =>
    api.post<LeaveRequestResponse>('/api/leave', data, true),

  update: (id: number, data: Partial<LeaveRequestCreate>) =>
    api.patch<LeaveRequestResponse>(`/api/leave/${id}`, data),
}
