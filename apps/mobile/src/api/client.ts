import { getAccessToken, getRefreshToken, saveAccessToken, saveRefreshToken, clearAuth } from '@utils/storage';

// ─── Config ──────────────────────────────────────────────────────────
const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8000';

// ─── Types ───────────────────────────────────────────────────────────
export interface ApiError {
  status: number;
  message: string;
  detail?: string;
}

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

export interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  authenticated?: boolean;
  /** Skip automatic 401 → refresh flow */
  skipAuthRefresh?: boolean;
}

// ─── Response wrapper ────────────────────────────────────────────────
export class ApiResponse<T> {
  constructor(
    public readonly data: T | null,
    public readonly error: ApiError | null,
    public readonly ok: boolean,
  ) {}

  static success<T>(data: T): ApiResponse<T> {
    return new ApiResponse<T>(data, null, true);
  }

  static failure<T>(error: ApiError): ApiResponse<T> {
    return new ApiResponse<T>(null, error, false);
  }
}

// ─── Token refresh state ─────────────────────────────────────────────
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return false;

      const res = await fetch(`${BASE_URL}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        await clearAuth();
        return false;
      }

      const data = await res.json();
      await saveAccessToken(data.access_token);
      await saveRefreshToken(data.refresh_token);
      return true;
    } catch {
      await clearAuth();
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// ─── Core request function ───────────────────────────────────────────
async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const {
    method = 'GET',
    body,
    params,
    authenticated = true,
    skipAuthRefresh = false,
  } = options;

  // Build URL
  let urlStr = `${BASE_URL}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const qs = searchParams.toString();
    if (qs) urlStr += `?${qs}`;
  }

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (authenticated) {
    const token = await getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  // Build request init
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(urlStr, init);

    // 401 → attempt token refresh (once)
    if (response.status === 401 && authenticated && !skipAuthRefresh) {
      const refreshed = await attemptTokenRefresh();
      if (refreshed) {
        // Retry the original request with the new token
        const newToken = await getAccessToken();
        if (newToken) {
          headers['Authorization'] = `Bearer ${newToken}`;
        }
        const retryResponse = await fetch(urlStr, { ...init, headers });

        if (!retryResponse.ok) {
          return parseErrorResponse<T>(retryResponse);
        }

        if (retryResponse.status === 204) {
          return ApiResponse.success<T>(null as T);
        }

        const data = await retryResponse.json();
        return ApiResponse.success(data as T);
      }

      // Refresh failed — force logout
      await clearAuth();
      return ApiResponse.failure<T>({
        status: 401,
        message: 'Session expired. Please sign in again.',
        detail: 'Token refresh failed',
      });
    }

    if (!response.ok) {
      return parseErrorResponse<T>(response);
    }

    // 204 No Content
    if (response.status === 204) {
      return ApiResponse.success<T>(null as T);
    }

    const data = await response.json();
    return ApiResponse.success(data as T);
  } catch (err) {
    const message =
      err instanceof TypeError
        ? 'Unable to connect. Check your network connection.'
        : err instanceof Error
          ? err.message
          : 'An unexpected error occurred.';

    return ApiResponse.failure<T>({
      status: 0,
      message,
      detail: 'Network or server unavailable',
    });
  }
}

// ─── Error response parser ───────────────────────────────────────────
async function parseErrorResponse<T>(response: Response): Promise<ApiResponse<T>> {
  try {
    const body = await response.json();
    const message =
      body.detail ||
      body.message ||
      body.error ||
      `Request failed (${response.status})`;
    return ApiResponse.failure<T>({
      status: response.status,
      message,
      detail: JSON.stringify(body),
    });
  } catch {
    return ApiResponse.failure<T>({
      status: response.status,
      message: `Request failed (${response.status})`,
    });
  }
}

// ─── Public API ──────────────────────────────────────────────────────
export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method'>) =>
    request<T>(path, { ...options, method: 'GET' }),

  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'POST', body }),

  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'PATCH', body }),

  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'PUT', body }),

  del: <T>(path: string, options?: Omit<RequestOptions, 'method'>) =>
    request<T>(path, { ...options, method: 'DELETE' }),
};

export default api;
