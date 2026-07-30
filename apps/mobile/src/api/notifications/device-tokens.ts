import api from '../client';

const BASE = '/api/notifications';

export interface DeviceTokenRegisterRequest {
  token: string;
  platform: 'android' | 'ios' | 'web';
}

export interface DeviceTokenResponse {
  id: number;
  user_id: number;
  token: string;
  platform: string;
  created_at: string;
}

/** Register this device's push notification token with the backend. */
export async function registerDeviceToken(data: DeviceTokenRegisterRequest) {
  return api.post<DeviceTokenResponse>(`${BASE}/device-tokens`, data);
}

/** Remove a specific device token (e.g., on logout). */
export async function unregisterDeviceToken(token: string) {
  return api.del<void>(`${BASE}/device-tokens/${encodeURIComponent(token)}`);
}

/** Remove all device tokens for the current user on logout. */
export async function unregisterAllDeviceTokens() {
  return api.del<void>(`${BASE}/device-tokens`);
}
