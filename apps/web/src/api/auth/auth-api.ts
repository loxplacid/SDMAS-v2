import { api } from '../client/http-client'
import type { UserResponse, TokenResponse, UserCreate, UserUpdate, PasswordChange, AdminUserUpdate, Page } from '../generated/types'

export const authApi = {
  register: (data: UserCreate) =>
    api.post<UserResponse>('/auth/register', data, true),

  login: (login: string, password: string) =>
    api.login(login, password),

  refresh: (refreshToken: string) =>
    // Body-based contract: the refresh token never travels in the URL.
    api.post<TokenResponse>(
      '/auth/refresh',
      { refresh_token: refreshToken },
      true,
    ),

  getMe: () =>
    api.get<UserResponse>('/auth/me'),

  updateMe: (data: UserUpdate) =>
    api.patch<UserResponse>('/auth/me', data),

  changePassword: (data: PasswordChange) =>
    api.patch<void>('/auth/me/password', data),
}

export const adminUserApi = {
  list: (params: { page?: number; size?: number; role?: string; is_active?: boolean } = {}) =>
    api.get<Page<UserResponse>>(
      '/admin/users',
      params as Record<string, string | number | boolean | undefined | null>,
    ),

  getById: (userId: number) =>
    api.get<UserResponse>(`/admin/users/${userId}`),

  create: (data: UserCreate) =>
    api.post<UserResponse>('/admin/users', data),

  update: (userId: number, data: AdminUserUpdate) =>
    api.patch<UserResponse>(`/admin/users/${userId}`, data),

  setRoles: (userId: number, roleCodes: string[]) =>
    api.post<UserResponse>(`/admin/users/${userId}/roles`, roleCodes),
}