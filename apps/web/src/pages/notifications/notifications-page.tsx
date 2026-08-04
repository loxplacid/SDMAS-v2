import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationApi } from '../../api/notifications'
import type { NotificationResponse } from '../../api/notifications'
import { getNotificationRoute } from '../../api/notifications/deep-link'
import { cn } from '../../lib/utils'
import { TabGroup, Button, Pagination, EmptyState, ErrorState, Badge } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'

export function NotificationsPage() {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState<NotificationResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const size = 20

  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const skip = (page - 1) * size
      const res = await notificationApi.list({
        skip,
        limit: size,
        unread_only: filter === 'unread',
      })
      setNotifications(res.items)
      setTotal(res.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load notifications')
    } finally {
      setLoading(false)
    }
  }, [page, filter])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  useKeyboardShortcut({
    'r': () => fetchNotifications(),
  }, [fetchNotifications])

  async function handleMarkRead(id: number) {
    try {
      await notificationApi.markRead(id)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
      )
    } catch {
      // Silently fail
    }
  }

  async function handleMarkAllRead() {
    try {
      await notificationApi.markAllRead()
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() }))
      )
    } catch {
      // Silently fail
    }
  }

  async function handleDelete(id: number) {
    try {
      await notificationApi.delete(id)
      setNotifications((prev) => prev.filter((n) => n.id !== id))
      setTotal((prev) => prev - 1)
    } catch {
      // Silently fail
    }
  }

  async function handleOpen(n: NotificationResponse) {
    // Mark as read when opened.
    if (!n.read_at) {
      try {
        await notificationApi.markRead(n.id)
        setNotifications((prev) =>
          prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x))
        )
      } catch {
        // Non-fatal
      }
    }
    // Deep-link to a safe internal route when the payload carries one.
    const route = getNotificationRoute(n.data)
    if (route) navigate(route)
  }

  const totalPages = Math.max(1, Math.ceil(total / size))

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  // ── Loading state ──
  if (loading) {
    return (
      <div className="max-w-3xl mx-auto animate-fade-in-up">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">System</div>
            <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1 tracking-tight">Notifications</h1>
          </div>
        </div>
        <div className="text-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-[var(--color-brand-accent)] border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-[var(--color-text-tertiary)]">Loading notifications...</p>
        </div>
      </div>
    )
  }

  // ── Error state ──
  if (error) {
    return (
      <div className="max-w-3xl mx-auto animate-fade-in-up">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">System</div>
            <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1 tracking-tight">Notifications</h1>
          </div>
        </div>
        <ErrorState message={error} onRetry={fetchNotifications} />
      </div>
    )
  }

  // ── Empty state ──
  if (notifications.length === 0) {
    return (
      <div className="max-w-3xl mx-auto animate-fade-in-up">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">System</div>
            <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1 tracking-tight">Notifications</h1>
            <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{total} {total === 1 ? 'notification' : 'notifications'}</p>
          </div>
          <TabGroup
            tabs={[
              { id: 'all', label: 'All' },
              { id: 'unread', label: 'Unread' },
            ]}
            activeTab={filter}
            onChange={(id) => { setFilter(id as 'all' | 'unread'); setPage(1) }}
            variant="pills"
            size="sm"
          />
        </div>
        <EmptyState
          title="No notifications"
          description={filter === 'unread' ? 'All caught up!' : 'No notifications yet'}
          icon={
            <svg className="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          }
        />
      </div>
    )
  }

  // ── Notification list ──
  return (
    <div className="max-w-3xl mx-auto animate-fade-in-up">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-[var(--color-brand-accent)] text-xs font-semibold uppercase tracking-wider">System</div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)] mt-1 tracking-tight">Notifications</h1>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
            {total} {total === 1 ? 'notification' : 'notifications'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <TabGroup
            tabs={[
              { id: 'all', label: 'All' },
              { id: 'unread', label: 'Unread' },
            ]}
            activeTab={filter}
            onChange={(id) => { setFilter(id as 'all' | 'unread'); setPage(1) }}
            variant="pills"
            size="sm"
          />
          <Button variant="outline" size="sm" onClick={handleMarkAllRead}>
            Mark all read
          </Button>
        </div>
      </div>

      <div className="space-y-1">
        {notifications.map((n) => (
          <button
            key={n.id}
            type="button"
            onClick={() => handleOpen(n)}
            className={cn(
              'w-full text-left flex items-start gap-3 p-4 rounded-xl border motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
              !n.read_at
                ? 'bg-[var(--color-brand-accent-subtle)] border-[var(--color-brand-accent)]/20'
                : 'bg-[var(--color-surface)] border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'
            )}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className={cn(
                  'text-sm',
                  !n.read_at ? 'font-semibold text-[var(--color-text-primary)]' : 'font-medium text-[var(--color-text-secondary)]'
                )}>
                  {n.title}
                </p>
                <span className={cn(
                  'inline-block h-2 w-2 rounded-full flex-shrink-0 mt-1.5',
                  !n.read_at ? 'bg-[var(--color-brand-accent)] animate-badge-pop' : 'bg-[var(--color-text-muted)]'
                )} />
              </div>
              <p className="text-sm text-[var(--color-text-tertiary)] mt-1">{n.message}</p>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-xs text-[var(--color-text-muted)]">{formatDate(n.created_at)}</span>
                <Badge variant="neutral" size="sm">{n.type}</Badge>
              </div>
            </div>
            <div className="flex flex-col gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
              {!n.read_at && (
                <Button variant="ghost" size="xs" onClick={() => handleMarkRead(n.id)}>
                  Read
                </Button>
              )}
              <Button
                variant="ghost"
                size="xs"
                onClick={() => handleDelete(n.id)}
                className="text-[var(--color-danger)] hover:bg-[var(--color-danger-light)]"
              >
                Delete
              </Button>
            </div>
          </button>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="mt-6 pt-4 border-t border-[var(--color-divider)]">
          <Pagination
            page={page}
            size={size}
            total={total}
            pages={totalPages}
            onPageChange={setPage}
          />
        </div>
      )}
    </div>
  )
}
