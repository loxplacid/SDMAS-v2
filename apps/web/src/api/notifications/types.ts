export interface NotificationResponse {
  id: number
  user_id: number | null
  type: string
  title: string
  message: string
  data: Record<string, unknown> | null
  read_at: string | null
  created_at: string
}

export interface UnreadCountResponse {
  count: number
}

export interface NotificationListParams {
  skip?: number
  limit?: number
  unread_only?: boolean
}
