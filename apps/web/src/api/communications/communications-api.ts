import { api } from '../client/http-client'

export interface MessageTemplate {
  id: number
  code: string
  name: string
  subject: string | null
  body: string
  message_type: string
  channels: string[]
  variables: { key: string; label: string; type: string }[] | null
  is_active: boolean
  campus_id: number | null
  created_by: number
  created_at: string
  updated_at: string
}

export interface MessageRecipient {
  id: number
  message_id: number
  recipient_type: string
  recipient_id: number
  channel: string
  status: string
  delivered_at: string | null
  read_at: string | null
  error_message: string | null
  created_at: string
}

export interface Message {
  id: number
  template_id: number | null
  thread_id: number | null
  subject: string | null
  body: string
  message_type: string
  priority: string
  channels: string[]
  status: string
  scheduled_for: string | null
  sent_at: string | null
  campus_id: number | null
  sender_id: number
  /** P15 — operational context the message was composed from. */
  context_type: string | null
  context_id: number | null
  created_at: string
  updated_at: string
  recipients: MessageRecipient[]
  attachments: { id: number; filename: string; mime_type: string; file_size: number; created_at: string }[]
  schedule: { id: number; scheduled_at: string; status: string; timezone: string; recurrence: string } | null
  recipient_count: number
  delivered_count: number
  failed_count: number
  read_count: number
}

export interface MessageStats {
  total_sent: number
  total_delivered: number
  total_failed: number
  total_read: number
  by_type: Record<string, number>
  by_channel: Record<string, number>
}

export interface CommunicationPreference {
  id: number
  user_id: number
  channel: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface RecipientTarget {
  recipient_type: 'user' | 'student' | 'teacher' | 'parent'
  recipient_id: number
}

export interface BulkRecipientTarget {
  recipient_type: 'user' | 'student' | 'teacher' | 'parent'
  recipient_ids: number[]
}

export interface SendMessagePayload {
  template_id?: number
  thread_id?: number
  subject?: string
  body: string
  message_type: string
  priority?: string
  channels?: string[]
  recipients?: RecipientTarget[]
  recipient_groups?: BulkRecipientTarget[]
  class_ids?: number[]
  section_ids?: number[]
  schedule_at?: string
  timezone?: string
  recurrence?: string
  recurrence_end?: string
  /** P15 — the operational context the message is composed from. */
  context_type?: string
  context_id?: number
  /** P15 — explicit template-variable overrides. */
  variables?: Record<string, unknown>
}

/** P15 — operational context summary + template variables. */
export interface CommunicationContext {
  context_type: string
  context_id: number
  label: string
  detail: string
  variables: Record<string, unknown>
  guardian_ids: number[]
}

export interface ContextPreviewResult {
  subject: string
  body: string
  context_type: string
  context_id: number
  variables: Record<string, unknown>
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

const BASE = '/api/communications'

export const templateApi = {
  list: () => api.get<MessageTemplate[]>(`${BASE}/templates`),
  get: (id: number) => api.get<MessageTemplate>(`${BASE}/templates/${id}`),
  create: (data: Partial<MessageTemplate>) => api.post<MessageTemplate>(`${BASE}/templates`, data),
  update: (id: number, data: Partial<MessageTemplate>) => api.patch<MessageTemplate>(`${BASE}/templates/${id}`, data),
  delete: (id: number) => api.delete(`${BASE}/templates/${id}`),
  render: (template_id: number, variables: Record<string, string>) =>
    api.post<{ subject: string; body: string }>(`${BASE}/templates/render`, { template_id, variables }),
  renderWithContext: (template_id: number, context_type: string, context_id: number) =>
    api.post<ContextPreviewResult>(`${BASE}/templates/render-context`, { template_id, context_type, context_id }),
}

export const contextApi = {
  get: (context_type: string, context_id: number) =>
    api.get<CommunicationContext>(`${BASE}/context/${context_type}/${context_id}`),
}

export const messageApi = {
  send: (data: SendMessagePayload) => api.post<Message>(`${BASE}/send`, data),
  list: (params?: { page?: number; size?: number; message_type?: string; status?: string; context_type?: string; context_id?: number }) =>
    api.get<Page<Message>>(`${BASE}/messages`, params as Record<string, string | number | boolean | undefined | null>),
  get: (id: number) => api.get<Message>(`${BASE}/messages/${id}`),
  update: (id: number, data: { subject?: string; body?: string; priority?: string; status?: string }) =>
    api.patch<Message>(`${BASE}/messages/${id}`, data),
  delete: (id: number) => api.delete(`${BASE}/messages/${id}`),
  retry: (id: number, payload?: { recipient_ids?: number[]; channel?: string }) =>
    api.post<Message>(`${BASE}/messages/${id}/retry`, payload),
  sendNow: (id: number) => api.post<Message>(`${BASE}/messages/${id}/send-now`),
}

export const inboxApi = {
  list: (params?: { page?: number; size?: number }) =>
    api.get<Page<any>>(`${BASE}/inbox`, params as Record<string, string | number | boolean | undefined | null>),
  markRead: (recipientId: number) => api.post<any>(`${BASE}/inbox/${recipientId}/read`),
}

export const preferenceApi = {
  list: () => api.get<CommunicationPreference[]>(`${BASE}/preferences`),
  update: (channel: string, enabled: boolean) =>
    api.patch<CommunicationPreference>(`${BASE}/preferences/${channel}`, { channel, enabled }),
}

export const statsApi = {
  get: () => api.get<MessageStats>(`${BASE}/stats`),
}

export const metaApi = {
  messageTypes: () => api.get<string[]>(`${BASE}/meta/message-types`),
  channels: () => api.get<string[]>(`${BASE}/meta/channels`),
}

export const recipientApi = {
  resolve: (data: { recipient_type: string; recipient_ids?: number[]; class_ids?: number[]; section_ids?: number[] }) =>
    api.post<{ recipients: any[]; total: number }>(`${BASE}/resolve-recipients`, data),
}
