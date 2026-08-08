import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const listMock = vi.fn()
const markReadMock = vi.fn()
const markAllReadMock = vi.fn()
const deleteMock = vi.fn()

vi.mock('../api/notifications', () => ({
  notificationApi: {
    list: (...args: unknown[]) => listMock(...args),
    markRead: (...args: unknown[]) => markReadMock(...args),
    markAllRead: (...args: unknown[]) => markAllReadMock(...args),
    delete: (...args: unknown[]) => deleteMock(...args),
  },
}))

const { NotificationsPage } = await import('../pages/notifications/notifications-page')

function isoDaysAgo(days: number, hour = 9) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(hour, 0, 0, 0)
  return d.toISOString()
}

const notifications = [
  { id: 1, title: 'Payment received', message: 'INV-1 settled', type: 'payment_received', read_at: null, created_at: isoDaysAgo(0), data: null },
  { id: 2, title: 'Attendance anomaly', message: '3 consecutive absences', type: 'attendance_anomaly', read_at: '2026-01-01T00:00:00Z', created_at: isoDaysAgo(1), data: null },
  { id: 3, title: 'Approval needed', message: 'Leave request pending', type: 'approval_needed', read_at: null, created_at: isoDaysAgo(4), data: null },
]

function renderPage() {
  return render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  listMock.mockResolvedValue({ items: notifications, total: notifications.length })
  markAllReadMock.mockResolvedValue({ count: 0 })
  deleteMock.mockResolvedValue(undefined)
  markReadMock.mockResolvedValue({})
})

describe('Notifications page — polish (skeletons, grouping, semantics)', () => {
  it('renders the list grouped by day', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Payment received')).toBeInTheDocument())
    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Yesterday')).toBeInTheDocument()
    expect(screen.getByText('Approval needed')).toBeInTheDocument()
  })

  it('shows a skeleton while loading', async () => {
    let resolveFn!: (v: { items: typeof notifications; total: number }) => void
    listMock.mockReturnValueOnce(new Promise((res) => { resolveFn = res }))
    renderPage()
    expect(screen.getByLabelText('Loading notifications')).toBeInTheDocument()
    resolveFn({ items: notifications, total: notifications.length })
    await waitFor(() => expect(screen.getByText('Payment received')).toBeInTheDocument())
    expect(screen.queryByLabelText('Loading notifications')).not.toBeInTheDocument()
  })

  it('marks all notifications read — every row flips to the read state', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Payment received')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Mark all read' }))
    expect(markAllReadMock).toHaveBeenCalledTimes(1)
    // unread rows carry the accent-subtle tint — it must clear on every row
    await waitFor(() => {
      const row = screen.getByText('Payment received').closest('button')
      expect(row?.className).not.toContain('brand-accent-subtle')
    })
  })

  it('deletes a notification — the row leaves the list', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Payment received')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete' })[0])
    expect(deleteMock).toHaveBeenCalledWith(1)
    await waitFor(() => expect(screen.queryByText('Payment received')).not.toBeInTheDocument())
    expect(screen.getByText('Attendance anomaly')).toBeInTheDocument()
  })

  it('filters to unread through the tab group', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Payment received')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('tab', { name: 'Unread' }))
    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith({ skip: 0, limit: 20, unread_only: true })
    )
  })
})
