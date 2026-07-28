import { api } from '../client/http-client'
import type { TermResponse, TermCreate, TermUpdate, Page } from '../generated/types'

export const termApi = {
  listByYear: (yearId: number, params: { page?: number; size?: number } = {}) =>
    api.get<Page<TermResponse>>(`/api/academic-years/${yearId}/terms`, params as Record<string, string | number | boolean | undefined | null>),

  getById: (id: number) =>
    api.get<TermResponse>(`/api/terms/${id}`),

  create: (yearId: number, data: TermCreate) =>
    api.post<TermResponse>(`/api/academic-years/${yearId}/terms`, data),

  update: (id: number, data: TermUpdate) =>
    api.patch<TermResponse>(`/api/terms/${id}`, data),
}