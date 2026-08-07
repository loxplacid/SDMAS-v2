import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationApi } from '../../api/notifications'
import { getNotificationRoute } from '../../api/notifications/deep-link'
import { cn } from '../../lib/utils'
import { useMove, MOTION_EASINGS } from '../../lib/motion'

/**
 * Unread-count dot (spec §6.9): scales in with `spring` (300ms settle — a
 * small object, legal §3.4), then one arrival `Pulse`, then stillness.
 * Remounted per count change (`key={unreadCount}`) so a new arrival replays
 * its choreography. The scale-in is a spatial move — gated to the precise
 * tier (§8); reduced tiers show the count plainly.
 */
function BellDot({ count }: { count: number }) {
  const { pulse, tier } = useMove({ verb: 'scale', distance: 'D1', importance: 'I1' })
  const dotRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (tier !== 'precise') return
    const el = dotRef.current
    if (!el) return
    if (typeof el.animate === 'function') {
      el.animate(
        [
          { transform: 'scale(0)' },
          { transform: 'scale(1.12)', offset: 0.6 },
          { transform: 'scale(1)' },
        ],
        { duration: 300, easing: MOTION_EASINGS.spring, fill: 'both' }
      )
    }
    const t = window.setTimeout(() => pulse(el), 340)
    return () => window.clearTimeout(t)
  }, [tier, pulse])

  return (
    <span
      ref={dotRef}
      className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center h-4 min-w-[1rem] px-1 rounded-full bg-red-500 text-[10px] font-bold text-white leading-none"
    >
      {count > 99 ? '99+' : count}
    </span>
  )
}

export function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const prevUnreadCountRef = useRef(0)
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

  const unreadCountRef = useRef(0)

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await notificationApi.getUnreadCount()
      prevUnreadCountRef.current = unreadCountRef.current
      unreadCountRef.current = res.count
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
    const eventSource = new EventSource('/api/notifications/events', { withCredentials: true })
    eventSource.addEventListener('unread_count', (e) => {
      const count = Number(e.data)
      prevUnreadCountRef.current = unreadCountRef.current
      unreadCountRef.current = count
      setUnreadCount(count)
    })
    return () => eventSource.close()
  }, [fetchUnreadCount])

  const closeMenu = useCallback(() => {
    if (open) {
      setClosing(true)
      setTimeout(() => {
        setClosing(false)
        setOpen(false)
      }, 120)
    }
  }, [open])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        closeMenu()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [closeMenu])

  function handleToggle() {
    if (open) {
      closeMenu()
    } else {
      setOpen(true)
      setClosing(false)
      fetchRecent()
    }
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
    closeMenu()
    // Navigate after animation
    setTimeout(() => navigate('/notifications'), 120)
  }

  async function handleOpenNotification(n: {
    id: number
    title: string
    message: string
    type: string
    read_at: string | null
    created_at: string
    data: Record<string, unknown> | null
  }) {
    closeMenu()
    // Mark as read when the user opens it from the bell.
    if (!n.read_at) {
      try {
        await notificationApi.markRead(n.id)
        setUnreadCount((c) => Math.max(0, c - 1))
      } catch {
        // Non-fatal: navigation still proceeds
      }
    }
    // Deep-link to the referenced page when the payload carries a safe
    // internal route; otherwise fall back to the notifications hub.
    const route = getNotificationRoute(n.data)
    setTimeout(() => navigate(route ?? '/notifications'), 120)
  }

  const hasNewNotifications = unreadCount > prevUnreadCountRef.current && prevUnreadCountRef.current > 0

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

  const showMenu = open

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleToggle}
        className={cn(
          'relative p-2 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-accent)]',
          'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]',
          hasNewNotifications && 'animate-attention-ring'
        )}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <BellDot key={unreadCount} count={unreadCount} />
        )}
      </button>

      {showMenu && (
        <div
          className={cn(
            'absolute right-0 mt-2 w-80 bg-[var(--color-surface)] rounded-2xl shadow-xl border border-[var(--color-border)] z-50 origin-top-right',
            closing ? 'animate-fade-out-scale' : 'animate-fade-in-scale'
          )}
          role="menu"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] focus:outline-none transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-72 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-8 text-center text-sm text-[var(--color-text-tertiary)]">
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-start gap-3 px-4">
                      <div className="h-8 w-8 rounded-full bg-[var(--color-border)] animate-skeleton flex-shrink-0" />
                      <div className="flex-1 space-y-2">
                        <div className="h-3 w-3/4 bg-[var(--color-border)] animate-skeleton rounded" />
                        <div className="h-2 w-1/2 bg-[var(--color-border)] animate-skeleton rounded" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-[var(--color-text-tertiary)]">
                <svg className="mx-auto h-8 w-8 text-[var(--color-text-muted)] mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                <p>No new notifications</p>
              </div>
            ) : (
              notifications.map((n, idx) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleOpenNotification(n)}
                  className={cn(
                    'w-full text-left px-4 py-3 border-b border-[var(--color-border-light)] hover:bg-[var(--color-surface-hover)] transition-colors animate-fade-in',
                    !n.read_at ? 'bg-[var(--color-brand-accent-light)]/50' : ''
                  )}
                  style={{ animationDelay: `${idx * 30}ms`, animationFillMode: 'both' }}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">{n.title}</p>
                      <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5 line-clamp-2">{n.message}</p>
                      <p className="text-[10px] text-[var(--color-text-muted)] mt-1">{formatTime(n.created_at)}</p>
                    </div>
                    <span className={cn(
                      'inline-block h-2 w-2 rounded-full mt-1.5 flex-shrink-0',
                      !n.read_at ? 'bg-[var(--color-brand-accent)]' : 'bg-transparent'
                    )} />
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="px-4 py-2 border-t border-[var(--color-border)]">
            <button
              onClick={handleViewAll}
              className="w-full text-center text-sm font-medium text-[var(--color-brand-accent)] hover:text-[var(--color-brand-accent-hover)] py-1.5 focus:outline-none transition-colors rounded-lg hover:bg-[var(--color-brand-accent-light)]"
            >
              View all notifications
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
