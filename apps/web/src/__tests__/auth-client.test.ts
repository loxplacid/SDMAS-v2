import { describe, it, expect, vi, beforeEach } from 'vitest'

const BASE_URL = 'http://localhost:8000'

describe('Auth API Client', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('stores tokens after login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        access_token: 'test-access',
        refresh_token: 'test-refresh',
        expires_in: 1800,
      }),
    }))

    const { api, getAccessToken, clearTokens } = await import('../api/client/http-client')
    clearTokens()

    await api.login('testuser', 'testpass')

    expect(getAccessToken()).toBe('test-access')
  })

  it('attaches Authorization header for authenticated requests', async () => {
    let capturedHeaders: any = null

    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string, opts: any) => {
      capturedHeaders = opts.headers
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ items: [], total: 0, page: 1, size: 20, pages: 1 }),
      })
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('my-access-token', 'my-refresh-token')

    await m.api.get('/students')

    expect(capturedHeaders).toBeTruthy()
    expect(capturedHeaders['Authorization']).toBe('Bearer my-access-token')
  })

  it('handles 401 and attempts token refresh', async () => {
    const fetchMock = vi.fn()
    let callCount = 0
    fetchMock.mockImplementation((url: string, opts: any) => {
      callCount++
      if (callCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 401,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
      }
      if (callCount === 2) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: () => Promise.resolve({
            access_token: 'refreshed-access',
            refresh_token: 'refreshed-refresh',
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ items: [], total: 0, page: 1, size: 20, pages: 1 }),
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('expired-access', 'valid-refresh')

    const result = await m.api.get('/students')
    expect(result).toBeDefined()
    expect(callCount).toBe(3)
  })

  it('redirects to login on failed refresh', async () => {
    let logoutCalled = false
    const fetchMock = vi.fn()
    fetchMock.mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('expired-access', 'invalid-refresh')
    m.api.setLogoutHandler(() => { logoutCalled = true })

    await expect(m.api.get('/students')).rejects.toMatchObject({
      status: 401,
      detail: 'Session expired. Please log in again.',
    })
    expect(logoutCalled).toBe(true)
  })

  it('handles 403 without logging out', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ detail: 'Access denied' }),
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    await expect(m.api.get('/admin/users')).rejects.toMatchObject({
      status: 403,
      detail: 'Access denied',
    })
  })

  it('handles network errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    await expect(m.api.get('/students')).rejects.toThrow()
  })

  it('parses validation errors correctly', async () => {
    const validationBody = {
      detail: [
        { loc: ['body', 'name'], msg: 'Name is required', type: 'value_error' },
      ],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve(validationBody),
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    const err: any = await m.api.get('/test').catch(e => e)
    expect(err.status).toBe(422)
    expect(err.validation_errors).toBeDefined()
    expect(err.validation_errors.length).toBe(1)
  })

  it('handles 204 no content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    const result = await m.api.delete('/test')
    expect(result).toBeUndefined()
  })

  it('handles 404 errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ detail: 'Resource not found' }),
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    const err: any = await m.api.get('/nonexistent').catch(e => e)
    expect(err.status).toBe(404)
  })

  it('handles 409 conflict errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ detail: 'Resource already exists' }),
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    const err: any = await m.api.post('/resources').catch(e => e)
    expect(err.status).toBe(409)
  })

  it('handles non-JSON error responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve('Internal Server Error'),
    }))

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('valid-access', 'valid-refresh')

    const err: any = await m.api.get('/error').catch(e => e)
    expect(err).toBeDefined()
    expect(err.status).toBe(500)
  })

  it('does not attempt refresh for skipAuth requests on 401', async () => {
    let refreshAttempted = false
    const fetchMock = vi.fn()
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/auth/refresh')) {
        refreshAttempted = true
      }
      return Promise.resolve({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('some-token', 'some-refresh')

    await expect(m.api.get('/auth/login', undefined, true)).rejects.toMatchObject({ status: 401 })
    expect(refreshAttempted).toBe(false)
  })

  it('logout clears tokens', async () => {
    const m = await import('../api/client/http-client')
    m.clearTokens()
    m.api.setTokens('access', 'refresh')
    m.api.logout()

    let capturedAuth: string | undefined
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string, opts: any) => {
      capturedAuth = opts.headers['Authorization']
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({}),
      })
    }))

    await m.api.get('/students')
    expect(capturedAuth).toBeUndefined()
  })
})