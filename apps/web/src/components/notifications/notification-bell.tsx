import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationApi } from '../../api/notifications'
import { cn } from '../../lib/utils'

export function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState<Array<{
    id: number
    title: string
    message: string
    type: string
    read_at: string | null
    created_at: string
    data: Record<string, unknown> | null
  }>>([])
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await notificationApi.getUnreadCount()
      setUnreadCount(res.count)
    } catch {
      // Silently fail — not critical
    }
  }, [])

  const fetchRecent = useCallback(async () => {
    setLoading(true)
    try {
      const res = await notificationApi.list({ limit: 5, unread_only: true })
      setNotifications(res.items)
    } catch {
      // Silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30_000)
    return () => clearInterval(interval)
  }, [fetchUnreadCount])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleToggle() {
    if (!open) {
      fetchRecent()
    }
    setOpen(!open)
  }

  async function handleMarkAllRead() {
    try {
      await notificationApi.markAllRead()
      setUnreadCount(0)
      setNotifications([])
    } catch {
      // Silently fail
    }
  }

  function handleViewAll() {
    setOpen(false)
    navigate('/notifications')
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60_000)

    if (diffMin < 1) return 'Just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 7) return `${diffDay}d ago`
    return d.toLocaleDateString()
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleToggle}
        className="relative p-2 text-gray-500 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center h-4 min-w-[1rem] px-1 rounded-full bg-red-500 text-[10px] font-bold text-white leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 w-80 bg-white rounded-md shadow-lg border border-gray-200 z-50"
          role="menu"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-600 hover:text-blue-800 focus:outline-none"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-72 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                Loading...
              </div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                <svg className="mx-auto h-8 w-8 text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                <p>No new notifications</p>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={cn(
                    'px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors',
                    !n.read_at ? 'bg-blue-50/50' : ''
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{n.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.message}</p>
                      <p className="text-[10px] text-gray-400 mt-1">{formatTime(n.created_at)}</p>
                    </div>
                    <span className={cn(
                      'inline-block h-2 w-2 rounded-full mt-1.5 flex-shrink-0',
                      !n.read_at ? 'bg-blue-500' : 'bg-transparent'
                    )} />
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="px-4 py-2 border-t border-gray-100">
            <button
              onClick={handleViewAll}
              className="w-full text-center text-sm text-blue-600 hover:text-blue-800 py-1 focus:outline-none"
            >
              View all notifications
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
