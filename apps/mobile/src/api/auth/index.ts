import api from '../client';
import type { TokenResponse, UserLogin, UserResponse, PasswordChange, UserUpdate } from './types';

const BASE = '/auth';

/** Authenticate with username/email and password. */
export async function loginUser(data: UserLogin) {
  return api.post<TokenResponse>(`${BASE}/login`, data, {
    authenticated: false,
  });
}

/**
 * Refresh an expired access token.
 *
 * NOTE: Token refresh is handled automatically by the HTTP client on 401
 * (see `client.ts` -> `attemptTokenRefresh`). This function is exposed
 * for manual usage and sends `refresh_token` in the JSON **body** —
 * the single coherent contract with the FastAPI backend. The token
 * never travels in the URL (it would leak into proxy/access logs).
 */
export async function refreshToken(refresh_token: string) {
  return api.post<TokenResponse>(
    `${BASE}/refresh`,
    { refresh_token },
    { authenticated: false },
  );
}

/** Get the currently authenticated user's profile. */
export async function getMe() {
  return api.get<UserResponse>(`${BASE}/me`);
}

/** Update the current user's profile. */
export async function updateMe(data: UserUpdate) {
  return api.patch<UserResponse>(`${BASE}/me`, data);
}

/** Change the current user's password. */
export async function changeMyPassword(data: PasswordChange) {
  return api.patch<{ detail: string }>(`${BASE}/me/password`, data);
}
