import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import type { NotificationResponse } from '../api/notifications'
import { getNotificationRoute } from '../api/notifications/deep-link'

// Mock the API client before importing the page
const listMock = vi.fn()
const unreadMock = vi.fn()
const markReadMock = vi.fn()
const markAllReadMock = vi.fn()
const deleteMock = vi.fn()

vi.mock('../api/notifications', () => ({
  notificationApi: {
    list: (...args: unknown[]) => listMock(...args),
    getUnreadCount: (...args: unknown[]) => unreadMock(...args),
    markRead: (...args: unknown[]) => markReadMock(...args),
    markAllRead: (...args: unknown[]) => markAllReadMock(...args),
    delete: (...args: unknown[]) => deleteMock(...args),
  },
}))

const { mockUser } = vi.hoisted(() => ({
  mockUser: { id: 1, username: 'admin', display_name: 'Test Admin', email: 'admin@test.local', role: 'admin' },
}))

vi.mock('../api/auth/auth-context', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  }),
}))

vi.mock('../hooks/use-permission', () => ({
  usePermission: () => ({ can: () => true }),
}))

// Import after mocking
const { NotificationsPage } = await import('../pages/notifications/notifications-page')
const { NotificationBell } = await import('../components/notifications/notification-bell')

function makeNotification(overrides: Partial<NotificationResponse> = {}): NotificationResponse {
  return {
    id: 1,
    user_id: 1,
    type: 'fee',
    title: 'Fee Dues Created',
    message: '2 fee due(s) totalling 1500 have been created',
    data: { route: '/fees', due_ids: [1, 2] },
    read_at: null,
    created_at: '2026-08-02T10:00:00Z',
    ...overrides,
  }
}

beforeEach(() => {
  vi.resetAllMocks()
  listMock.mockResolvedValue({ items: [makeNotification()], total: 1, page: 1, size: 20, pages: 1 })
  unreadMock.mockResolvedValue({ count: 1 })
  markReadMock.mockResolvedValue(makeNotification({ read_at: '2026-08-02T11:00:00Z' }))
  markAllReadMock.mockResolvedValue({ count: 0 })
  deleteMock.mockResolvedValue(undefined)
})

// ── Notifications page ───────────────────────────────────────────────

describe('NotificationsPage', () => {
  function renderPage() {
    return render(
      <MemoryRouter initialEntries={['/notifications']}>
        <Routes>
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/fees" element={<div>Fees Page</div>} />
        </Routes>
      </MemoryRouter>
    )
  }

  it('renders notifications with unread state', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Fee Dues Created')).toBeInTheDocument()
      expect(screen.getByText(/2 fee due\(s\)/)).toBeInTheDocument()
      expect(screen.getByText('fee')).toBeInTheDocument()
    })
  })

  it('marks a notification read', async () => {
    renderPage()

    await waitFor(() => expect(screen.getByText('Fee Dues Created')).toBeInTheDocument())
    // Exact match: the outer row button also contains the word "Read" in its
    // accessible name, so /Read/ would match two buttons.
    await userEvent.click(screen.getByRole('button', { name: /^Read$/ }))

    await waitFor(() => {
      expect(markReadMock).toHaveBeenCalledWith(1)
      // Read button disappears after marking read.
      expect(screen.queryByRole('button', { name: /^Read$/ })).not.toBeInTheDocument()
    })
  })

  it('marks all notifications read', async () => {
    renderPage()

    await waitFor(() => expect(screen.getByText('Fee Dues Created')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: /Mark all read/ }))

    await waitFor(() => expect(markAllReadMock).toHaveBeenCalled())
  })

  it('deletes a notification', async () => {
    renderPage()

    await waitFor(() => expect(screen.getByText('Fee Dues Created')).toBeInTheDocument())
    // Exact match for the same reason as the Read button above.
    await userEvent.click(screen.getByRole('button', { name: /^Delete$/ }))

    await waitFor(() => {
      expect(deleteMock).toHaveBeenCalledWith(1)
      expect(screen.queryByText('Fee Dues Created')).not.toBeInTheDocument()
    })
  })

  it('deep-links to the safe route in notification data', async () => {
    renderPage()

    await waitFor(() => expect(screen.getByText('Fee Dues Created')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Fee Dues Created'))

    await waitFor(() => {
      expect(screen.getByText('Fees Page')).toBeInTheDocument()
    })
    // Opening marks the notification read first.
    expect(markReadMock).toHaveBeenCalledWith(1)
  })

  it('shows an error state when loading fails', async () => {
    listMock.mockRejectedValueOnce(new Error('Network down'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Network down')).toBeInTheDocument()
    })
  })
})

// ── Notification bell ─────────────────────────────────────────────────

describe('NotificationBell', () => {
  function renderBell() {
    return render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<div><NotificationBell /></div>} />
          <Route path="/fees" element={<div>Fees Page</div>} />
          <Route path="/notifications" element={<div>All Notifications</div>} />
        </Routes>
      </MemoryRouter>
    )
  }

  it('shows the unread count badge', async () => {
    renderBell()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Notifications \(1 unread\)/ })).toBeInTheDocument()
    })
  })

  it('lists recent notifications in the dropdown', async () => {
    renderBell()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Notifications \(1 unread\)/ })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /Notifications \(1 unread\)/ }))

    await waitFor(() => {
      expect(screen.getByText('Fee Dues Created')).toBeInTheDocument()
    })
  })

  it('deep-links to the safe route when opening a notification', async () => {
    renderBell()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Notifications \(1 unread\)/ })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /Notifications \(1 unread\)/ }))
    await waitFor(() => expect(screen.getByText('Fee Dues Created')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Fee Dues Created'))

    await waitFor(() => {
      expect(screen.getByText('Fees Page')).toBeInTheDocument()
    })
  })

  it('navigates to the notifications hub from View all', async () => {
    renderBell()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Notifications \(1 unread\)/ })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /Notifications \(1 unread\)/ }))
    await userEvent.click(screen.getByRole('button', { name: /View all notifications/ }))

    await waitFor(() => {
      expect(screen.getByText('All Notifications')).toBeInTheDocument()
    })
  })

  it('marks all read from the dropdown', async () => {
    renderBell()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Notifications \(1 unread\)/ })).toBeInTheDocument()
    )
    await userEvent.click(screen.getByRole('button', { name: /Notifications \(1 unread\)/ }))
    await userEvent.click(screen.getByRole('button', { name: /Mark all read/ }))

    await waitFor(() => expect(markAllReadMock).toHaveBeenCalled())
  })
})

// ── Safe deep-link validation util ───────────────────────────────────

describe('getNotificationRoute', () => {
  it('accepts allowlisted internal routes', () => {
    expect(getNotificationRoute({ route: '/students/42' })).toBe('/students/42')
    expect(getNotificationRoute({ route: '/fees' })).toBe('/fees')
    expect(getNotificationRoute({ route: '/reports' })).toBe('/reports')
  })

  it('rejects unsafe routes', () => {
    expect(getNotificationRoute({ route: 'https://evil.example.com' })).toBeNull()
    expect(getNotificationRoute({ route: '//evil.example.com' })).toBeNull()
    expect(getNotificationRoute({ route: 'javascript:alert(1)' })).toBeNull()
    expect(getNotificationRoute({ route: '/unknown-page' })).toBeNull()
    expect(getNotificationRoute({ route: '/students/1?x=2' })).toBeNull()
  })

  it('returns null without data', () => {
    expect(getNotificationRoute(null)).toBeNull()
    expect(getNotificationRoute(undefined)).toBeNull()
    expect(getNotificationRoute({})).toBeNull()
  })
})
