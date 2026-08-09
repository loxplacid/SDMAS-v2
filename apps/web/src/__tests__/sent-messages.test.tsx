import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'
import type { Message } from '../api/communications/communications-api'

const listMock = vi.fn()
const contextGetMock = vi.fn()

vi.mock('../api/communications/communications-api', () => ({
  messageApi: {
    list: (...args: unknown[]) => listMock(...args),
    retry: vi.fn(),
    sendNow: vi.fn(),
    get: vi.fn(),
  },
  contextApi: {
    get: (...args: unknown[]) => contextGetMock(...args),
  },
}))

const { SentMessagesPage } = await import('../pages/communications/sent')

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 1,
    template_id: null,
    thread_id: null,
    subject: 'Fee reminder',
    body: 'Dear parent, fees are due',
    message_type: 'targeted',
    priority: 'normal',
    channels: ['in_app'],
    status: 'sent',
    scheduled_for: null,
    sent_at: '2026-08-01T10:00:00Z',
    campus_id: null,
    sender_id: 5,
    context_type: 'student',
    context_id: 101,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    recipients: [],
    attachments: [],
    schedule: null,
    recipient_count: 1,
    delivered_count: 1,
    failed_count: 0,
    read_count: 0,
    ...overrides,
  }
}

function renderPage(route = '/communications/sent') {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/communications/sent" element={<SentMessagesPage />} />
          <Route path="/students/:id" element={<div>Student page</div>} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  listMock.mockResolvedValue({ items: [], total: 0, page: 1, size: 20, pages: 0 })
  contextGetMock.mockRejectedValue({ detail: 'no context' })
})

describe('Sent messages — P15 context filtering', () => {
  it('passes context_type/context_id from the URL to the list call', async () => {
    listMock.mockResolvedValue({
      items: [makeMessage()],
      total: 1, page: 1, size: 20, pages: 1,
    })
    contextGetMock.mockResolvedValue({
      context_type: 'student',
      context_id: 101,
      label: 'Rahul Sharma',
      detail: '#A001 · 10A',
      variables: {},
      guardian_ids: [],
    })

    renderPage('/communications/sent?context_type=student&context_id=101')

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith(expect.objectContaining({
        context_type: 'student',
        context_id: 101,
      }))
    })

    // The resolved context label appears in the header + filter chip.
    await waitFor(() => {
      expect(screen.getAllByText('Rahul Sharma').length).toBeGreaterThan(0)
      expect(screen.getByText('Fee reminder')).toBeInTheDocument()
    })
  })

  it('surfaces the linked context in the message detail', async () => {
    listMock.mockResolvedValue({
      items: [makeMessage()],
      total: 1, page: 1, size: 20, pages: 1,
    })
    contextGetMock.mockResolvedValue({
      context_type: 'student', context_id: 101, label: 'Rahul Sharma',
      detail: '', variables: {}, guardian_ids: [],
    })

    renderPage('/communications/sent?context_type=student&context_id=101')

    await waitFor(() => expect(screen.getByText('Fee reminder')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /View/i }))

    await waitFor(() => {
      // "Context" appears in the filter chip AND the detail modal.
      expect(screen.getAllByText(/Context/).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/student #101/i).length).toBeGreaterThan(0)
      // The message links back to the originating student.
      expect(screen.getByRole('link', { name: /View student/ })).toHaveAttribute(
        'href', '/students/101'
      )
    })
  })

  it('clears the context filter and reloads without it', async () => {
    listMock.mockResolvedValue({ items: [makeMessage()], total: 1, page: 1, size: 20, pages: 1 })
    contextGetMock.mockResolvedValue({
      context_type: 'student', context_id: 101, label: 'Rahul Sharma',
      detail: '', variables: {}, guardian_ids: [],
    })

    renderPage('/communications/sent?context_type=student&context_id=101')

    await waitFor(() => expect(screen.getByText('Fee reminder')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Clear filter/ }))

    await waitFor(() => {
      // Second load has no context params.
      const calls = listMock.mock.calls
      expect(calls.length).toBeGreaterThanOrEqual(2)
      expect(calls[calls.length - 1][0]).not.toHaveProperty('context_type')
    })
  })

  it('renders an empty state when no messages match the context', async () => {
    renderPage('/communications/sent?context_type=student&context_id=999')

    await waitFor(() => {
      expect(screen.getByText('No messages found')).toBeInTheDocument()
    })
  })
})
