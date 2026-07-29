import { useState, useEffect, useCallback } from 'react'
import { notificationApi } from '../../api/notifications'
import type { NotificationResponse } from '../../api/notifications'
import { cn } from '../../lib/utils'

export function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const limit = 20

  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const skip = (page - 1) * limit
      const res = await notificationApi.list({
        skip,
        limit,
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

  const totalPages = Math.max(1, Math.ceil(total / limit))

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
          <div className="flex rounded-md border border-gray-300 overflow-hidden">
            <button
              onClick={() => { setFilter('all'); setPage(1) }}
              className={cn(
                'px-3 py-1.5 text-sm font-medium transition-colors',
                filter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              )}
            >
              All
            </button>
            <button
              onClick={() => { setFilter('unread'); setPage(1) }}
              className={cn(
                'px-3 py-1.5 text-sm font-medium transition-colors',
                filter === 'unread'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              )}
            >
              Unread
            </button>
          </div>
          <button
            onClick={handleMarkAllRead}
            className="text-sm text-blue-600 hover:text-blue-800 px-3 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            Mark all read
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading notifications...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={fetchNotifications}
            className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline"
          >
            Try again
          </button>
        </div>
      ) : notifications.length === 0 ? (
        <div className="text-center py-16">
          <svg className="mx-auto h-12 w-12 text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <p className="text-gray-500 font-medium">No notifications</p>
          <p className="text-sm text-gray-400 mt-1">
            {filter === 'unread' ? 'All caught up!' : 'No notifications yet'}
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-1">
            {notifications.map((n) => (
              <div
                key={n.id}
                className={cn(
                  'flex items-start gap-3 p-4 rounded-lg border transition-colors',
                  !n.read_at
                    ? 'bg-blue-50/50 border-blue-100'
                    : 'bg-white border-gray-200 hover:bg-gray-50'
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className={cn(
                      'text-sm',
                      !n.read_at ? 'font-semibold text-gray-900' : 'font-medium text-gray-700'
                    )}>
                      {n.title}
                    </p>
                    <span className={cn(
                      'inline-block h-2 w-2 rounded-full flex-shrink-0 mt-1.5',
                      !n.read_at ? 'bg-blue-500' : 'bg-gray-200'
                    )} />
                  </div>
                  <p className="text-sm text-gray-500 mt-1">{n.message}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-gray-400">{formatDate(n.created_at)}</span>
                    <span className="text-[10px] uppercase tracking-wider text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                      {n.type}
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-1 flex-shrink-0">
                  {!n.read_at && (
                    <button
                      onClick={() => handleMarkRead(n.id)}
                      className="text-xs text-blue-600 hover:text-blue-800 px-2 py-1 rounded hover:bg-blue-50 transition-colors"
                      title="Mark as read"
                    >
                      Read
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(n.id)}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors"
                    title="Delete notification"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
              <p className="text-sm text-gray-500">
                Page {page} of {totalPages} ({total} total)
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
