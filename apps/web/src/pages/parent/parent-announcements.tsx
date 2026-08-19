import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { parentApi } from '../../api/parent/parent-api'
import type { ParentAnnouncement } from '../../api/parent/parent-api'
import { Loading, ErrorState, EmptyState, Card } from '../../components/ui'
import { formatDate } from '../../lib/utils'

const PRIORITY_STYLES: Record<string, string> = {
  urgent: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-200 dark:border-rose-800',
  high: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800',
  normal: 'bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] border-[var(--color-border)]',
}

export function ParentAnnouncementsPage() {
  const navigate = useNavigate()
  const [announcements, setAnnouncements] = useState<ParentAnnouncement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    parentApi.getAnnouncements()
      .then((res) => setAnnouncements(res.announcements))
      .catch((err: any) => setError(err?.detail || 'Failed to load announcements'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading text="Loading announcements..." />
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
            <h1 className="text-lg font-bold text-[var(--color-text-primary)]">Announcements</h1>
            <p className="text-xs text-[var(--color-text-tertiary)]">School-wide updates & notices</p>
          </div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-3">
        {announcements.length === 0 ? (
          <Card className="p-8 text-center">
            <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-[var(--color-surface-hover)] mx-auto mb-3">
              <svg className="h-6 w-6 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">No announcements</p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Check back later for updates</p>
          </Card>
        ) : (
          announcements.map((announcement) => (
            <Card key={announcement.id} className={`p-4 border-l-4 ${
              announcement.priority === 'urgent' ? 'border-l-rose-500' :
              announcement.priority === 'high' ? 'border-l-amber-500' :
              'border-l-[var(--color-brand-accent)]'
            }`}>
              {/* Header */}
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
                    {announcement.title || 'Announcement'}
                  </h3>
                </div>
                <span className={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full border ${PRIORITY_STYLES[announcement.priority] || PRIORITY_STYLES.normal}`}>
                  {announcement.priority}
                </span>
              </div>

              {/* Body */}
              <p className="text-sm text-[var(--color-text-secondary)] whitespace-pre-wrap">
                {announcement.body}
              </p>

              {/* Footer */}
              <div className="flex items-center justify-between mt-3 text-xs text-[var(--color-text-tertiary)]">
                <span>{announcement.sender_name || 'School'}</span>
                <span>{formatDate(announcement.created_at)}</span>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

export default ParentAnnouncementsPage
