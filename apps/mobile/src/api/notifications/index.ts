import api from '../client';
import type { NotificationResponse, UnreadCountResponse } from './types';

const BASE = '/api/notifications';

export async function listNotifications(params?: {
  skip?: number;
  limit?: number;
  unread_only?: boolean;
}) {
  return api.get<{ items: NotificationResponse[]; total: number; page: number; size: number }>(
    BASE,
    { params: params as Record<string, string | number | boolean | undefined> },
  );
}

export async function getUnreadCount() {
  return api.get<UnreadCountResponse>(`${BASE}/unread-count`);
}

export async function markAsRead(notificationId: number) {
  return api.patch<NotificationResponse>(`${BASE}/${notificationId}/read`);
}

export async function markAllAsRead() {
  return api.patch<UnreadCountResponse>(`${BASE}/read-all`);
}
