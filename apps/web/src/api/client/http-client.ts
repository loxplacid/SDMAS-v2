import type { ApiError } from '../generated/types'

// In development, use relative URLs (go through Vite proxy).
// In production, set VITE_API_BASE_URL to the backend origin.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

let accessToken: string | null = null
let refreshToken: string | null = null
let onLogout: (() => void) | null = null
let refreshPromise: Promise<boolean> | null = null

const inflightRequests = new Map<string, Promise<unknown>>()

function storeTokens(access: string, refresh: string) {
  accessToken = access
  refreshToken = refresh
}

export function clearTokens() {
  accessToken = null
  refreshToken = null
}

function setLogoutHandler(handler: () => void) {
  onLogout = handler
}

export function getAccessToken() {
  return accessToken
}

async function tryRefresh(): Promise<boolean> {
  if (!refreshToken) return false
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    try {
      const url = BASE_URL ? `${BASE_URL}/auth/refresh` : '/auth/refresh'
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken! }),
      })
      if (!res.ok) return false
      const data = await res.json()
      storeTokens(data.access_token, data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

function parseApiError(status: number, body: any): ApiError {
  if (body?.detail && Array.isArray(body.detail)) {
    return {
      status,
      detail: body.detail[0]?.msg || 'Validation error',
      validation_errors: body.detail,
    }
  }
  if (typeof body?.detail === 'string') {
    return { status, detail: body.detail }
  }
  return { status, detail: `Request failed with status ${status}` }
}

type RequestOptions = {
  method?: string
  body?: unknown
  params?: Record<string, string | number | boolean | undefined | null>
  skipAuth?: boolean
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params, skipAuth = false } = options

  const urlStr = BASE_URL ? `${BASE_URL}${path}` : path
  const url = new URL(urlStr, BASE_URL ? undefined : window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    }
  }

  const cacheKey = method === 'GET' ? url.toString() : null
  if (cacheKey) {
    const existing = inflightRequests.get(cacheKey)
    if (existing) return existing as Promise<T>
  }

  const execute = async (): Promise<T> => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (!skipAuth && accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`
    }

    let res = await fetch(url.toString(), {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })

    if (res.status === 401 && !skipAuth && refreshToken) {
      const refreshed = await tryRefresh()
      if (refreshed) {
        headers['Authorization'] = `Bearer ${accessToken}`
        res = await fetch(url.toString(), {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
        })
      } else {
        clearTokens()
        onLogout?.()
        throw { status: 401, detail: 'Session expired. Please log in again.' } as ApiError
      }
    }

    if (res.status === 204) {
      return undefined as T
    }

    const contentType = res.headers.get('content-type')
    const isJson = contentType && contentType.includes('application/json')

    if (!res.ok) {
      const errorBody = isJson ? await res.json() : { detail: `HTTP ${res.status}: ${res.statusText}` }

      if (res.status === 403) {
        throw { status: 403, detail: errorBody?.detail || 'Access denied' } as ApiError
      }

      throw parseApiError(res.status, errorBody)
    }

    if (isJson) {
      return res.json() as Promise<T>
    }

    if (contentType && contentType.includes('text/csv')) {
      return res.blob() as Promise<T>
    }

    return undefined as T
  }

  const promise = execute().finally(() => {
    if (cacheKey) inflightRequests.delete(cacheKey)
  })

  if (cacheKey) {
    inflightRequests.set(cacheKey, promise)
  }

  return promise
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined | null>, skipAuth?: boolean) =>
    request<T>(path, { method: 'GET', params, skipAuth }),

  post: <T>(path: string, body?: unknown, skipAuth?: boolean) =>
    request<T>(path, { method: 'POST', body, skipAuth }),

  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body }),

  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),

  login: async (login: string, password: string) => {
    const data = await request<{ access_token: string; refresh_token: string; expires_in: number }>(
      '/auth/login',
      { method: 'POST', body: { login, password }, skipAuth: true }
    )
    storeTokens(data.access_token, data.refresh_token)
    return data
  },

  logout: () => {
    clearTokens()
  },

  setTokens: storeTokens,
  setLogoutHandler,
  clearTokens,
}