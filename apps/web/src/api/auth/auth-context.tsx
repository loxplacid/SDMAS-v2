import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { api, authApi, getAccessToken, clearTokens } from '../index'
import type { UserResponse } from '../generated/types'

type AuthState = {
  user: UserResponse | null
  isLoading: boolean
  isAuthenticated: boolean
  error: string | null
}

type AuthContextType = AuthState & {
  login: (login: string, password: string) => Promise<void>
  logout: () => void
  updateUser: (user: UserResponse) => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
    error: null,
  })

  const logout = useCallback(() => {
    api.logout()
    setState({ user: null, isLoading: false, isAuthenticated: false, error: null })
  }, [])

  useEffect(() => {
    api.setLogoutHandler(logout)
  }, [logout])

  useEffect(() => {
    const token = getAccessToken()
    if (!token) {
      setState({ user: null, isLoading: false, isAuthenticated: false, error: null })
      return
    }
    authApi.getMe()
      .then((user) => setState({ user, isLoading: false, isAuthenticated: true, error: null }))
      .catch(() => {
        clearTokens()
        setState({ user: null, isLoading: false, isAuthenticated: false, error: null })
      })
  }, [])

  const login = useCallback(async (login: string, password: string) => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      await api.login(login, password)
      const user = await authApi.getMe()
      setState({ user, isLoading: false, isAuthenticated: true, error: null })
    } catch (err: any) {
      const message = err?.detail || 'Login failed'
      setState({ user: null, isLoading: false, isAuthenticated: false, error: message })
      throw err
    }
  }, [])

  const updateUser = useCallback((user: UserResponse) => {
    setState((s) => ({ ...s, user }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}