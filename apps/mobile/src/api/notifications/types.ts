/** Notification API types. */

export interface NotificationResponse {
  id: number;
  user_id: number;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  is_read: boolean;
  created_at: string;
  read_at?: string;
}

export interface UnreadCountResponse {
  count: number;
}
