import React, { createContext, useCallback, useEffect, useMemo, useReducer } from 'react';
import type { UserResponse, UserLogin } from '@api/auth/types';
import { loginUser, getMe } from '@api/auth';
import {
  saveAccessToken,
  saveRefreshToken,
  getAccessToken,
  getRefreshToken,
  clearAuth,
  saveUser,
  getUser,
} from '@utils/storage';

// ─── State ───────────────────────────────────────────────────────────
interface AuthState {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
}

type AuthAction =
  | { type: 'RESTORE_SESSION'; user: UserResponse }
  | { type: 'LOGIN_START' }
  | { type: 'LOGIN_SUCCESS'; user: UserResponse }
  | { type: 'LOGIN_FAILURE'; error: string }
  | { type: 'LOGOUT' }
  | { type: 'CLEAR_ERROR' }
  | { type: 'UPDATE_USER'; user: UserResponse };

const initialState: AuthState = {
  user: null,
  isLoading: true, // starts loading until session restore completes
  isAuthenticated: false,
  error: null,
};

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'RESTORE_SESSION':
      return { ...state, user: action.user, isAuthenticated: true, isLoading: false };
    case 'LOGIN_START':
      return { ...state, isLoading: true, error: null };
    case 'LOGIN_SUCCESS':
      return { user: action.user, isLoading: false, isAuthenticated: true, error: null };
    case 'LOGIN_FAILURE':
      return { ...state, isLoading: false, error: action.error };
    case 'LOGOUT':
      return { user: null, isLoading: false, isAuthenticated: false, error: null };
    case 'CLEAR_ERROR':
      return { ...state, error: null };
    case 'UPDATE_USER':
      return { ...state, user: action.user };
    default:
      return state;
  }
}

// ─── Context ─────────────────────────────────────────────────────────
interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  login: (credentials: UserLogin) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ─── Provider ────────────────────────────────────────────────────────
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Restore session on mount
  useEffect(() => {
    (async () => {
      try {
        const token = await getAccessToken();
        if (!token) {
          dispatch({ type: 'LOGOUT' });
          return;
        }

        // Try to restore cached user first
        const cachedUser = await getUser<UserResponse>();
        if (cachedUser) {
          dispatch({ type: 'RESTORE_SESSION', user: cachedUser });
        } else {
          dispatch({ type: 'LOGIN_START' });
        }

        // Verify the token is still valid by fetching /me
        const response = await getMe();
        if (response.ok && response.data) {
          dispatch({ type: 'RESTORE_SESSION', user: response.data });
          await saveUser(response.data);
        } else if (response.error?.status === 401) {
          // Token expired — check refresh
          const refreshToken = await getRefreshToken();
          if (!refreshToken) {
            await clearAuth();
            dispatch({ type: 'LOGOUT' });
            return;
          }
          // Refresh (handled by client.ts automatically on retry)
          const retry = await getMe();
          if (retry.ok && retry.data) {
            dispatch({ type: 'RESTORE_SESSION', user: retry.data });
            await saveUser(retry.data);
          } else {
            await clearAuth();
            dispatch({ type: 'LOGOUT' });
          }
        } else {
          dispatch({ type: 'RESTORE_SESSION', user: cachedUser || undefined as unknown as UserResponse });
        }
      } catch {
        dispatch({ type: 'LOGOUT' });
      }
    })();
  }, []);

  const login = useCallback(async (credentials: UserLogin) => {
    dispatch({ type: 'LOGIN_START' });
    try {
      const response = await loginUser(credentials);
      if (!response.ok || !response.data) {
        dispatch({
          type: 'LOGIN_FAILURE',
          error: response.error?.message || 'Login failed. Please check your credentials.',
        });
        return;
      }

      const { access_token, refresh_token } = response.data;
      await saveAccessToken(access_token);
      await saveRefreshToken(refresh_token);

      // Fetch user profile
      const userResponse = await getMe();
      if (userResponse.ok && userResponse.data) {
        await saveUser(userResponse.data);
        dispatch({ type: 'LOGIN_SUCCESS', user: userResponse.data });
      } else {
        dispatch({
          type: 'LOGIN_FAILURE',
          error: 'Logged in but failed to load profile. Please try again.',
        });
      }
    } catch (err) {
      dispatch({
        type: 'LOGIN_FAILURE',
        error: err instanceof Error ? err.message : 'An unexpected error occurred.',
      });
    }
  }, []);

  const logout = useCallback(async () => {
    await clearAuth();
    dispatch({ type: 'LOGOUT' });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'CLEAR_ERROR' });
  }, []);

  const refreshUser = useCallback(async () => {
    const response = await getMe();
    if (response.ok && response.data) {
      await saveUser(response.data);
      dispatch({ type: 'UPDATE_USER', user: response.data });
    }
  }, []);

  const value = useMemo(
    () => ({
      user: state.user,
      isLoading: state.isLoading,
      isAuthenticated: state.isAuthenticated,
      error: state.error,
      login,
      logout,
      clearError,
      refreshUser,
    }),
    [state, login, logout, clearError, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
