import { describe, it, expect, vi, beforeEach } from 'vitest'

const BASE_URL = 'http://localhost:8000'
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

// Import after mocking
const { api, getAccessToken, clearTokens } = await import('../api/client/http-client')

beforeEach(() => {
  vi.clearAllMocks()
  clearTokens()
})

describe('Login Flow', () => {
  it('completes full login flow: POST /auth/login stores tokens', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () =>
        Promise.resolve({
          access_token: 'test-access-abc',
          refresh_token: 'test-refresh-xyz',
          token_type: 'bearer',
          expires_in: 1800,
        }),
    })

    await api.login('admin', 'Admin@12345')

    // 1. Tokens are stored after login
    expect(getAccessToken()).toBe('test-access-abc')

    // 2. Verify the request body was correct
    expect(mockFetch).toHaveBeenCalledTimes(1)
    const callUrl = mockFetch.mock.calls[0][0]
    const callOpts = mockFetch.mock.calls[0][1]

    expect(callUrl).toContain('/auth/login')
    expect(callOpts.method).toBe('POST')

    const body = JSON.parse(callOpts.body)
    expect(body).toEqual({ login: 'admin', password: 'Admin@12345' })
  })

  it('GET /auth/me is called with stored access token', async () => {
    // Setup: first call is login, second call is getMe
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            access_token: 'test-access-abc',
            refresh_token: 'test-refresh-xyz',
            token_type: 'bearer',
            expires_in: 1800,
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            id: 1,
            email: 'admin@sdmas.local',
            username: 'admin',
            display_name: 'System Administrator',
            role: 'admin',
            is_active: true,
            created_at: '2026-01-01T00:00:00',
            updated_at: '2026-01-01T00:00:00',
          }),
      })

    // Step 1: Login
    await api.login('admin', 'Admin@12345')
    expect(getAccessToken()).toBe('test-access-abc')

    // Step 2: Get current user
    const { authApi } = await import('../api/auth/auth-api')
    const user = await authApi.getMe()

    // 3. User data matches what backend returns
    expect(user.id).toBe(1)
    expect(user.username).toBe('admin')
    expect(user.role).toBe('admin')

    // 4. The getMe request includes the Authorization header
    const getMeCall = mockFetch.mock.calls[1]
    const getMeHeaders = getMeCall[1].headers
    expect(getMeHeaders['Authorization']).toBe('Bearer test-access-abc')
  })

  it('login failure does not store tokens and error has detail message', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ detail: 'Invalid username or password' }),
    })

    await expect(api.login('admin', 'wrongpassword')).rejects.toMatchObject({
      status: 401,
      detail: 'Invalid username or password',
    })

    // Tokens should NOT be stored on failure
    expect(getAccessToken()).toBeNull()
  })

  it('AuthContext login produces correct error message for "Invalid credentials" display', async () => {
    // Simulate network error (like the CORS issue that was the root cause)
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    try {
      await api.login('admin', 'Admin@12345')
      expect.unreachable('Should have thrown')
    } catch (err: any) {
      // Network errors (TypeError) don't have `.detail`
      expect(err?.detail).toBeUndefined()
      // This is exactly what auth-context.tsx and login.tsx hit before the CORS fix
      const message = err?.detail || 'Invalid credentials'
      expect(message).toBe('Invalid credentials')
    }
  })

  it('handles 403 without logging out the user', async () => {
    api.setTokens('valid-token', 'valid-refresh')

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ detail: 'Access denied' }),
    })

    const { authApi } = await import('../api/auth/auth-api')

    try {
      await authApi.getMe()
      expect.unreachable('Should have thrown')
    } catch (err: any) {
      expect(err.status).toBe(403)
      expect(err.detail).toBe('Access denied')
    }

    // Token is preserved — 403 should NOT trigger logout
    expect(getAccessToken()).toBe('valid-token')
  })

  it('login flow does NOT display "Invalid credentials" on success', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            access_token: 'test-access-abc',
            refresh_token: 'test-refresh-xyz',
            token_type: 'bearer',
            expires_in: 1800,
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () =>
          Promise.resolve({
            id: 1,
            email: 'admin@sdmas.local',
            username: 'admin',
            display_name: 'System Administrator',
            role: 'admin',
            is_active: true,
            created_at: '2026-01-01T00:00:00',
            updated_at: '2026-01-01T00:00:00',
          }),
      })

    // Full login flow — no error should surface
    let loginError: any = null
    try {
      await api.login('admin', 'Admin@12345')
      const { authApi } = await import('../api/auth/auth-api')
      const user = await authApi.getMe()
      expect(user).toBeDefined()
      expect(user.is_active).toBe(true)
    } catch (err: any) {
      loginError = err
    }

    // The string "Invalid credentials" must NOT be produced
    expect(loginError).toBeNull()
    expect(getAccessToken()).toBe('test-access-abc')
  })
})
