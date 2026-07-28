import { api } from '../client/http-client'
import type {
  NotificationResponse,
  UnreadCountResponse,
  NotificationListParams,
} from './types'

interface NotificationListResult {
  items: NotificationResponse[]
  total: number
  page: number
  size: number
  pages: number
}

export const notificationApi = {
  async list(params?: NotificationListParams): Promise<NotificationListResult> {
    const searchParams = new URLSearchParams()
    if (params?.skip !== undefined) searchParams.set('skip', String(params.skip))
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit))
    if (params?.unread_only) searchParams.set('unread_only', 'true')
    const qs = searchParams.toString()
    return api.get<NotificationListResult>(
      `/api/notifications${qs ? `?${qs}` : ''}`
    )
  },

  async getUnreadCount(): Promise<UnreadCountResponse> {
    return api.get<UnreadCountResponse>('/api/notifications/unread-count')
  },

  async markRead(notificationId: number): Promise<NotificationResponse> {
    return api.patch<NotificationResponse>(
      `/api/notifications/${notificationId}/read`
    )
  },

  async markAllRead(): Promise<UnreadCountResponse> {
    return api.patch<UnreadCountResponse>('/api/notifications/read-all')
  },

  async delete(notificationId: number): Promise<void> {
    await api.delete(`/api/notifications/${notificationId}`)
  },
}

export type NotificationApi = typeof notificationApi
