import { api } from '../client/http-client'

export interface CampusResponse {
  id: number
  institution_id: number
  name: string
  code: string
  address: string | null
  phone: string | null
  email: string | null
  status: string
  created_at: string
  updated_at: string
}

export const institutionApi = {
  getCampus: (id: number) =>
    api.get<CampusResponse>(`/api/institution/campuses/${id}`),
}
