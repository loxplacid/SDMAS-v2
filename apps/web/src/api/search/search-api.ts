import { api } from '../client/http-client'

export interface SearchResultItem {
  id: string
  entity_type: string
  entity_id: number
  label: string
  description: string | null
  route: string
  match_field: string | null
  score: number | null
}

export interface GroupedSearchResult {
  entity_type: string
  label: string
  icon: string
  items: SearchResultItem[]
}

export interface GlobalSearchResponse {
  query: string
  total: number
  page: number
  size: number
  results: SearchResultItem[]
  grouped: GroupedSearchResult[]
  took_ms: number
}

export interface SearchHistoryItem {
  id: number
  query: string
  entity_type: string | null
  result_count: number
  created_at: string
}

export type SearchEntityType =
  | 'student'
  | 'teacher'
  | 'class'
  | 'section'
  | 'fee'
  | 'payment'
  | 'notification'
  | 'document'

export interface GlobalSearchParams {
  query: string
  types?: SearchEntityType[]
  page?: number
  size?: number
}

export const searchApi = {
  global: (params: GlobalSearchParams) =>
    api.post<GlobalSearchResponse>('/api/search', {
      query: params.query,
      types: params.types ?? null,
      page: params.page ?? 1,
      size: params.size ?? 20,
    }),

  recent: (limit = 10) =>
    api.get<SearchHistoryItem[]>('/api/search/recent', { limit }),

  frequent: (limit = 5) =>
    api.get<{ query: string; count: number }[]>('/api/search/frequent', {
      limit,
    }),

  clearHistory: (searchId?: number) =>
    api.delete<{ deleted: boolean }>(
      searchId
        ? `/api/search/recent?search_id=${searchId}`
        : '/api/search/recent',
    ),
}
