import { api } from '../client/http-client'
import type { SubjectResponse, SubjectCreate, SubjectUpdate, Page } from '../generated/types'

export type SubjectListParams = {
  page?: number
  size?: number
  status?: string
}

export const subjectApi = {
  list: (params: SubjectListParams = {}) =>
    api.get<Page<SubjectResponse>>('/api/subjects', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<SubjectResponse>(`/api/subjects/${id}`),

  create: (data: SubjectCreate) =>
    api.post<SubjectResponse>('/api/subjects', data),

  update: (id: number, data: SubjectUpdate) =>
    api.patch<SubjectResponse>(`/api/subjects/${id}`, data),
}