import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const ACCESS_TOKEN_KEY = 'sdmas_access_token';
const REFRESH_TOKEN_KEY = 'sdmas_refresh_token';
const USER_KEY = 'sdmas_user';

/**
 * Save an access token to secure platform storage.
 * Falls back to in-memory for unsupported environments.
 */
export async function saveAccessToken(token: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, token);
  } catch {
    console.warn('SecureStore unavailable — access token not persisted');
  }
}

/** Read the stored access token. */
export async function getAccessToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Remove the stored access token. */
export async function removeAccessToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
  } catch {
    // Ignore
  }
}

/** Save refresh token to secure storage. */
export async function saveRefreshToken(token: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
  } catch {
    console.warn('SecureStore unavailable — refresh token not persisted');
  }
}

/** Read the stored refresh token. */
export async function getRefreshToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Remove the stored refresh token. */
export async function removeRefreshToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  } catch {
    // Ignore
  }
}

/** Serialize and save user object. */
export async function saveUser<T>(user: T): Promise<void> {
  try {
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
  } catch {
    console.warn('SecureStore unavailable — user not persisted');
  }
}

/** Read and deserialize the stored user. */
export async function getUser<T>(): Promise<T | null> {
  try {
    const raw = await SecureStore.getItemAsync(USER_KEY);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

/** Remove the stored user. */
export async function removeUser(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(USER_KEY);
  } catch {
    // Ignore
  }
}

/** Clear all authentication data. */
export async function clearAuth(): Promise<void> {
  await Promise.all([
    removeAccessToken(),
    removeRefreshToken(),
    removeUser(),
  ]);
}
