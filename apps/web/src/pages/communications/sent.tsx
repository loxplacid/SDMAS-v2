import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { messageApi, contextApi } from '../../api/communications/communications-api'
import type { Message } from '../../api/communications/communications-api'
import {
  PageHeader, Card, Button, Select, Table, Modal, Loading, ErrorState, Badge, Pagination, useToast,
} from '../../components/ui'
import { formatDate } from '../../lib/utils'

export function SentMessagesPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  // P15 — context-linked history: ?context_type=student&context_id=101
  // filters the list to messages composed from that operational context
  // (deep-linkable from Student 360 / case / fee surfaces).
  const contextType = searchParams.get('context_type')
  const contextIdRaw = searchParams.get('context_id')
  // Guard malformed deep links (?context_id=abc) — never send NaN to the API.
  const contextId = contextIdRaw && !Number.isNaN(Number(contextIdRaw))
    ? Number(contextIdRaw)
    : null
  const [contextLabel, setContextLabel] = useState<string | null>(null)
  const hasContextFilter = !!(contextType && contextId)
  const [messages, setMessages] = useState<Message[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const loadMessages = useCallback(() => {
    setLoading(true)
    const params: any = { page, size: pageSize }
    if (typeFilter) params.message_type = typeFilter
    if (statusFilter) params.status = statusFilter
    if (contextType && contextId) {
      params.context_type = contextType
      params.context_id = contextId
    }
    messageApi.list(params)
      .then((res) => {
        setMessages(res.items)
        setTotal(res.total)
      })
      .catch((err: any) => setError(err?.detail || 'Failed to load messages'))
      .finally(() => setLoading(false))
  }, [page, pageSize, typeFilter, statusFilter, contextType, contextId])

  useEffect(() => { loadMessages() }, [loadMessages])

  // P15 — resolve the linked context to a human label for the filter chip.
  useEffect(() => {
    if (!contextType || !contextId) {
      setContextLabel(null)
      return
    }
    let cancelled = false
    contextApi.get(contextType, contextId)
      .then((c) => { if (!cancelled) setContextLabel(c.label) })
      .catch(() => { if (!cancelled) setContextLabel(null) })
    return () => { cancelled = true }
  }, [contextType, contextId])

  const clearContextFilter = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('context_type')
    next.delete('context_id')
    setSearchParams(next)
    setPage(1)
  }

  // P15 — the entity a context-linked message points back to.
  const contextHref = (msg: Message): string => {
    if (msg.context_type === 'student') return `/students/${msg.context_id}`
    if (msg.context_type === 'case') return `/cases/${msg.context_id}`
    return '#'
  }

  const handleRetry = useCallback(async (msgId: number) => {
    try {
      await messageApi.retry(msgId)
      showToast('Delivery retry initiated', 'success')
      loadMessages()
    } catch (err: any) { showToast(err?.detail || 'Retry failed', 'error') }
  }, [showToast, loadMessages])

  const handleSendNow = useCallback(async (msgId: number) => {
    try {
      await messageApi.sendNow(msgId)
      showToast('Message sent', 'success')
      loadMessages()
    } catch (err: any) { showToast(err?.detail || 'Failed to send', 'error') }
  }, [showToast, loadMessages])

  const openDetail = (msg: Message) => {
    setSelectedMessage(msg)
    setDetailOpen(true)
  }

  const statusColor = (status: string) => {
    const map: Record<string, string> = {
      draft: 'default',
      sent: 'success',
      scheduled: 'info',
      failed: 'error',
      partial: 'warning',
    }
    return map[status] || 'default'
  }

  const columns = [
    { key: 'subject', header: 'Subject' },
    { key: 'message_type', header: 'Type' },
    { key: 'status', header: 'Status' },
    { key: 'recipient_count', header: 'Recipients' },
    { key: 'delivered_count', header: 'Delivered' },
    { key: 'failed_count', header: 'Failed' },
    { key: 'created_at', header: 'Created' },
    { key: 'actions', header: '' },
  ]

  const tableData = messages.map((msg) => ({
    ...msg,
    subject: msg.subject || '(no subject)',
    message_type: (
      <span className="capitalize text-xs">{msg.message_type.replace(/_/g, ' ')}</span>
    ),
    status: <Badge variant={statusColor(msg.status) as any}>{msg.status}</Badge>,
    recipient_count: msg.recipient_count,
    delivered_count: (
      <span className="text-[var(--color-success-dark)]">{msg.delivered_count}</span>
    ),
    failed_count: (
      <span className={`${msg.failed_count > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-text-tertiary)]'}`}>
        {msg.failed_count}
      </span>
    ),
    created_at: formatDate(msg.created_at),
    actions: (
      <div className="flex gap-1">
        <Button variant="secondary" size="sm" onClick={() => openDetail(msg)}>View</Button>
        {msg.status === 'failed' || msg.status === 'partial' ? (
          <Button variant="secondary" size="sm" onClick={() => handleRetry(msg.id)}>Retry</Button>
        ) : null}
        {msg.status === 'scheduled' ? (
          <Button variant="secondary" size="sm" onClick={() => handleSendNow(msg.id)}>Send Now</Button>
        ) : null}
      </div>
    ),
  }))

  if (error) return <ErrorState message={error} onRetry={loadMessages} />

  return (
    <div className="space-y-6 animate-fade-in-up">
      <PageHeader
        title={hasContextFilter && contextLabel ? `Communications — ${contextLabel}` : 'Sent Messages'}
        subtitle={hasContextFilter && contextLabel
          ? 'Communication history for this operational context'
          : 'Track delivery status of your communications'}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate('/communications')}>
              Back to Hub
            </Button>
            <Button size="sm" onClick={() => navigate('/communications/compose')}>
              New Message
            </Button>
          </div>
        }
      />

      <Card>
        {/* P15 — context-filter chip (deep-linked from an entity). */}
        {hasContextFilter && (
          <div className="flex items-center justify-between gap-3 mb-4 rounded-xl border border-[var(--color-brand-accent)]/30 bg-[var(--color-brand-accent)]/5 px-4 py-2.5">
            <p className="text-sm text-[var(--color-text-secondary)] min-w-0 truncate">
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand-accent)] mr-2">Context</span>
              {contextLabel || `${contextType} #${contextId}`}
            </p>
            <button
              type="button"
              onClick={clearContextFilter}
              className="flex-shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors"
            >
              Clear filter ×
            </button>
          </div>
        )}
        <div className="flex gap-4 mb-4">
          <div className="w-48">
            <Select
              label="Type"
              options={[
                { value: '', label: 'All Types' },
                { value: 'announcement', label: 'Announcement' },
                { value: 'targeted', label: 'Targeted' },
                { value: 'class', label: 'Class' },
                { value: 'section', label: 'Section' },
                { value: 'parent', label: 'Parent' },
                { value: 'teacher', label: 'Teacher' },
                { value: 'staff', label: 'Staff' },
              ]}
              value={typeFilter}
              onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
            />
          </div>
          <div className="w-48">
            <Select
              label="Status"
              options={[
                { value: '', label: 'All Statuses' },
                { value: 'draft', label: 'Draft' },
                { value: 'sent', label: 'Sent' },
                { value: 'scheduled', label: 'Scheduled' },
                { value: 'failed', label: 'Failed' },
                { value: 'partial', label: 'Partial' },
              ]}
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            />
          </div>
        </div>

        {loading ? (
          <Loading text="Loading messages..." />
        ) : messages.length === 0 ? (
          <div className="text-center py-12 text-[var(--color-text-tertiary)]">No messages found</div>
        ) : (
          <>
            <Table columns={columns} data={tableData} keyExtractor={(row: any) => row.id} />
            <div className="mt-4">
              <Pagination
                page={page}
                pages={Math.ceil(total / pageSize)}
                total={total}
                size={pageSize}
                onPageChange={setPage}
              />
            </div>
          </>
        )}
      </Card>

      <Modal
        open={detailOpen}
        onClose={() => { setDetailOpen(false); setSelectedMessage(null) }}
        title="Message Detail"
        size="lg"
      >
        {selectedMessage && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-[var(--color-text-tertiary)]">Status:</span> <Badge variant={statusColor(selectedMessage.status) as any}>{selectedMessage.status}</Badge></div>
              <div><span className="text-[var(--color-text-tertiary)]">Type:</span> <span className="capitalize">{selectedMessage.message_type.replace(/_/g, ' ')}</span></div>
              <div><span className="text-[var(--color-text-tertiary)]">Priority:</span> <span className="capitalize">{selectedMessage.priority}</span></div>
              <div><span className="text-[var(--color-text-tertiary)]">Channels:</span> {selectedMessage.channels.join(', ')}</div>
              <div><span className="text-[var(--color-text-tertiary)]">Sent:</span> {selectedMessage.sent_at ? formatDate(selectedMessage.sent_at) : 'Not yet'}</div>
              <div><span className="text-[var(--color-text-tertiary)]">Recipients:</span> {selectedMessage.recipient_count}</div>
            </div>
            {/* P15 — the message stays linked to its operational context. */}
            {selectedMessage.context_type && selectedMessage.context_id && (
              <div className="rounded-lg border border-[var(--color-brand-accent)]/25 bg-[var(--color-brand-accent)]/5 px-3 py-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand-accent)] mr-2">Context</span>
                <span className="text-[var(--color-text-secondary)] capitalize">{selectedMessage.context_type.replace(/_/g, ' ')} #{selectedMessage.context_id}</span>
                {contextHref(selectedMessage) !== '#' && (
                  <a
                    href={contextHref(selectedMessage)}
                    className="ml-2 text-[var(--color-brand-accent)] text-xs font-medium hover:underline"
                  >
                    View {selectedMessage.context_type} →
                  </a>
                )}
              </div>
            )}
            {selectedMessage.subject && (
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Subject</p>
                <p className="text-sm font-medium text-[var(--color-text-primary)]">{selectedMessage.subject}</p>
              </div>
            )}
            <div>
              <p className="text-sm text-[var(--color-text-tertiary)]">Body</p>
              <p className="text-sm text-[var(--color-text-primary)] whitespace-pre-wrap">{selectedMessage.body}</p>
            </div>
            {selectedMessage.schedule && (
              <div>
                <p className="text-sm text-[var(--color-text-tertiary)]">Schedule</p>
                <p className="text-sm">Scheduled: {formatDate(selectedMessage.schedule.scheduled_at)} ({selectedMessage.schedule.recurrence})</p>
              </div>
            )}
            {selectedMessage.recipients.length > 0 && (
              <div>
                <p className="text-sm font-medium text-[var(--color-text-primary)] mb-2">Recipient Delivery Status</p>
                <div className="max-h-60 overflow-y-auto space-y-1">
                  {selectedMessage.recipients.slice(0, 50).map((r) => (
                    <div key={r.id} className="flex items-center justify-between text-xs p-2 rounded bg-[var(--color-surface-hover)]">
                      <span>#{r.recipient_id} ({r.recipient_type}) — {r.channel}</span>
                      <span className={r.status === 'failed' ? 'text-[var(--color-danger)]' : 'text-[var(--color-success-dark)]'}>
                        {r.status}{r.error_message ? `: ${r.error_message}` : ''}
                      </span>
                    </div>
                  ))}
                  {selectedMessage.recipients.length > 50 && (
                    <p className="text-xs text-center text-[var(--color-text-tertiary)]">
                      ...and {selectedMessage.recipients.length - 50} more
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default SentMessagesPage
