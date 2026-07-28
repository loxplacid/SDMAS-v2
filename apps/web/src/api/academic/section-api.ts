import { api } from '../client/http-client'
import type { SectionResponse, SectionCreate, SectionUpdate, Page } from '../generated/types'

export type SectionListParams = {
  page?: number
  size?: number
  class_id?: number
  status?: string
}

export const sectionApi = {
  list: (params: SectionListParams = {}) =>
    api.get<Page<SectionResponse>>('/api/sections', params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<SectionResponse>(`/api/sections/${id}`),

  create: (data: SectionCreate) =>
    api.post<SectionResponse>('/api/sections', data),

  update: (id: number, data: SectionUpdate) =>
    api.patch<SectionResponse>(`/api/sections/${id}`, data),

  delete: (id: number) =>
    api.delete<void>(`/api/sections/${id}`),
}