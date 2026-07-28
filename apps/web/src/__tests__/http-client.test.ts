import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

// Import after mocking
const { api } = await import('../api/client/http-client')

beforeEach(() => {
  vi.clearAllMocks()
  api.clearTokens()
})

describe('HTTP Client', () => {
  it('performs a successful GET request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ id: 1, name: 'Test' }),
    })

    const result = await api.get('/test')
    expect(result).toEqual({ id: 1, name: 'Test' })
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('handles 401 by attempting token refresh', async () => {
    api.setTokens('expired-token', 'refresh-token')

    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ access_token: 'new-token', refresh_token: 'new-refresh' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ id: 1 }),
      })

    const result = await api.get('/test')
    expect(result).toEqual({ id: 1 })
    expect(mockFetch).toHaveBeenCalledTimes(3)
  })

  it('handles refresh failure and throws ApiError', async () => {
    api.setTokens('expired-token', 'refresh-token')

    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ detail: 'Invalid refresh token' }),
      })

    await expect(api.get('/test')).rejects.toMatchObject({
      status: 401,
      detail: 'Session expired. Please log in again.',
    })
  })

  it('parses validation errors correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        detail: [
          { loc: ['body', 'first_name'], msg: 'Field required', type: 'value_error.missing' },
        ],
      }),
    })

    await expect(api.post('/test', {})).rejects.toMatchObject({
      status: 422,
      detail: 'Field required',
    })
  })

  it('parses non-JSON errors', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve('Internal Server Error'),
    })

    await expect(api.get('/test')).rejects.toMatchObject({
      status: 500,
    })
  })

  it('handles 204 no content', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      headers: new Headers({ 'content-type': '' }),
    })

    const result = await api.delete('/test/1')
    expect(result).toBeUndefined()
  })
})