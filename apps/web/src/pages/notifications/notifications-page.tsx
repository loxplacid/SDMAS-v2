import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationApi } from '../../api/notifications'
import type { NotificationResponse } from '../../api/notifications'
import { getNotificationRoute } from '../../api/notifications/deep-link'
import { cn } from '../../lib/utils'
import { TabGroup, Button, Pagination, EmptyState, ErrorState, Badge, PageHeader } from '../../components/ui'
import { useKeyboardShortcut } from '../../hooks/use-keyboard-shortcut'

/**
 * Notification types carry the backend's own vocabulary (payment_received,
 * attendance_anomaly, approval_needed, …). The badge keeps the raw type
 * label and only borrows a semantic color from it — the category is never
 * invented, just tinted.
 */
const typeColor: Array<[RegExp, 'info' | 'success' | 'warning' | 'danger']> = [
  [/risk|critical|suspend|expel|threat/i, 'danger'],
  [/attendance|absent|late|truanc/i, 'warning'],
  // pending items (approval/leave/…) are NOT green — green reads as done
  [/approval|workflow|leave|request|substitut|purchase|job/i, 'info'],
  [/pay|fee|financ|invoice|receipt|collect|refund|overdue/i, 'info'],
]

function badgeVariant(type: string): 'info' | 'success' | 'warning' | 'danger' | 'neutral' {
  for (const [re, variant] of typeColor) {
    if (re.test(type)) return variant
  }
  return 'neutral'
}

/** Group labels keep the list scannable: Today / Yesterday / date. */
function dayGroup(iso: string): string {
  const d = new Date(iso)
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const startOfYesterday = new Date(startOfToday)
  startOfYesterday.setDate(startOfYesterday.getDate() - 1)
  if (d.getTime() >= startOfToday.getTime()) return 'Today'
  if (d.getTime() >= startOfYesterday.getTime()) return 'Yesterday'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function NotificationSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading notifications" aria-busy="true">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-4">
          <div className="h-8 w-8 rounded-full bg-[var(--color-border)] animate-skeleton flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-3/4 bg-[var(--color-border)] animate-skeleton rounded" />
            <div className="h-2.5 w-1/2 bg-[var(--color-border)] animate-skeleton rounded" />
            <div className="h-2 w-1/4 bg-[var(--color-border)] animate-skeleton rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

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

  const header = (
    <PageHeader
      eyebrow="System"
      title="Notifications"
      subtitle={!loading && !error ? `${total} ${total === 1 ? 'notification' : 'notifications'}` : undefined}
      compact
      actions={
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
      }
    />
  )

  return (
    <div className="max-w-3xl mx-auto animate-fade-in-up">
      {header}

      {loading ? (
        <NotificationSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchNotifications} />
      ) : notifications.length === 0 ? (
        <EmptyState
          title="No notifications"
          description={filter === 'unread' ? 'All caught up!' : 'No notifications yet'}
          icon={
            <svg className="h-12 w-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          }
        />
      ) : (
        <>
          {/* Grouped by day for scannability (Phase 14) */}
          {Array.from(
            notifications.reduce((groups, n) => {
              const key = dayGroup(n.created_at)
              const list = groups.get(key) ?? []
              list.push(n)
              groups.set(key, list)
              return groups
            }, new Map<string, NotificationResponse[]>())
          ).map(([groupLabel, group]) => (
            <section key={groupLabel} className="mb-5">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2 px-1">
                {groupLabel}
              </h2>
              <div className="space-y-1">
                {group.map((n) => (
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
                        <Badge variant={badgeVariant(n.type)} size="sm">{n.type}</Badge>
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
            </section>
          ))}

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
        </>
      )}
    </div>
  )
}
