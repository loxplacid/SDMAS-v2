import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { parentApi } from '../../api/parent/parent-api'
import type { ParentCommunication } from '../../api/parent/parent-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { formatDate } from '../../lib/utils'

export function ParentCommunicationPage() {
  const navigate = useNavigate()
  const [communications, setCommunications] = useState<ParentCommunication[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    parentApi.getCommunications()
      .then((res) => setCommunications(res.communications))
      .catch((err: any) => setError(err?.detail || 'Failed to load messages'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading messages..." />
  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-24">
      {/* Mobile header */}
      <div className="sticky top-0 z-10 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/parent')} className="flex items-center justify-center h-9 w-9 rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Messages</h1>
            <p className="text-xs text-[var(--color-text-tertiary)]">School communication & updates</p>
          </div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-3">
        {communications.length === 0 ? (
          <Card className="p-8 text-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-2xl bg-[var(--color-surface-hover)] mx-auto mb-3">
              <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">No messages yet</p>
            <p className="text-xs text-[var(--color-text-tertiary)]">School communications will appear here</p>
          </Card>
        ) : (
          communications.map((msg) => (
            <Card key={msg.id} className="p-4">
              <button
                onClick={() => setExpandedId(expandedId === msg.id ? null : msg.id)}
                className="w-full text-left"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
                      {msg.subject || '(No subject)'}
                    </h3>
                    <div className="flex items-center gap-2 text-xs text-[var(--color-text-tertiary)] mt-0.5">
                      <span>{msg.sender_name || 'School'}</span>
                      <span>&middot;</span>
                      <span>{formatDate(msg.created_at)}</span>
                      <span>&middot;</span>
                      <span className={`capitalize ${
                        msg.message_type === 'announcement' ? 'text-[var(--color-brand-accent)]' :
                        msg.message_type === 'parent' ? 'text-amber-500' : ''
                      }`}>
                        {msg.message_type}
                      </span>
                    </div>
                  </div>
                  <svg className={`h-4 w-4 text-[var(--color-text-tertiary)] shrink-0 mt-1 transition-transform ${expandedId === msg.id ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>

                {/* Expanded body */}
                {expandedId === msg.id && (
                  <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                    <p className="text-sm text-[var(--color-text-secondary)] whitespace-pre-wrap">
                      {msg.body}
                    </p>
                    <div className="flex items-center gap-2 mt-3">
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                        msg.status === 'sent' ? 'bg-emerald-500/10 text-emerald-600' :
                        msg.status === 'read' ? 'bg-blue-500/10 text-blue-600' :
                        'bg-[var(--color-surface-hover)] text-[var(--color-text-tertiary)]'
                      }`}>
                        {msg.status}
                      </span>
                    </div>
                  </div>
                )}
              </button>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

export default ParentCommunicationPage
