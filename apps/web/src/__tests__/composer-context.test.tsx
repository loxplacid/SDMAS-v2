import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '../components/ui/toast'

const templateListMock = vi.fn()
const metaTypesMock = vi.fn()
const metaChannelsMock = vi.fn()
const contextGetMock = vi.fn()
const renderWithContextMock = vi.fn()
const recipientResolveMock = vi.fn()
const messageSendMock = vi.fn()

vi.mock('../api/communications/communications-api', () => ({
  templateApi: {
    list: (...args: unknown[]) => templateListMock(...args),
    renderWithContext: (...args: unknown[]) => renderWithContextMock(...args),
  },
  messageApi: { send: (...args: unknown[]) => messageSendMock(...args) },
  metaApi: {
    messageTypes: (...args: unknown[]) => metaTypesMock(...args),
    channels: (...args: unknown[]) => metaChannelsMock(...args),
  },
  recipientApi: { resolve: (...args: unknown[]) => recipientResolveMock(...args) },
  contextApi: { get: (...args: unknown[]) => contextGetMock(...args) },
}))

const { ComposerPage } = await import('../pages/communications/composer')

function makeTemplate(id: number, body = 'Dear {student.name}, your balance is {fee.balance}') {
  return {
    id,
    code: `tpl-${id}`,
    name: `Template ${id}`,
    subject: `Reminder for {student.name}`,
    body,
    message_type: 'targeted',
    channels: ['in_app', 'email'],
    variables: null,
    is_active: true,
    campus_id: 1,
    created_by: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function renderPage(route = '/communications/compose') {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/communications/compose" element={<ComposerPage />} />
          <Route path="/communications/sent" element={<div>Sent Messages</div>} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
  templateListMock.mockResolvedValue([makeTemplate(1), makeTemplate(2)])
  metaTypesMock.mockResolvedValue(['targeted', 'announcement', 'class', 'parent'])
  metaChannelsMock.mockResolvedValue(['in_app', 'email', 'sms'])
})

describe('Composer — contextual communications (P15)', () => {
  it('loads the context badge and pre-fills guardian recipients from the URL', async () => {
    contextGetMock.mockResolvedValue({
      context_type: 'student',
      context_id: 101,
      label: 'Rahul Sharma',
      detail: '#A001 · 10A',
      variables: { student: { name: 'Rahul Sharma', number: 'A001', class: '10A' } },
      guardian_ids: [42],
    })

    renderPage('/communications/compose?context_type=student&context_id=101')

    await waitFor(() => {
      expect(contextGetMock).toHaveBeenCalledWith('student', 101)
      // context badge
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
      expect(screen.getByText('#A001 · 10A')).toBeInTheDocument()
      // guardian pre-fill
      expect(screen.getByText('Parents')).toBeInTheDocument()
      const recipientInput = screen.getByPlaceholderText('e.g. 1, 2, 3')
      expect((recipientInput as HTMLInputElement).value).toBe('42')
    })
  })

  it('renders a template preview with the live context variables', async () => {
    contextGetMock.mockResolvedValue({
      context_type: 'fee_due',
      context_id: 9,
      label: 'Fee #9',
      detail: 'partially_paid',
      variables: { student: { name: 'Rahul Sharma' }, fee: { balance: 30000 } },
      guardian_ids: [],
    })
    renderWithContextMock.mockResolvedValue({
      subject: 'Reminder for Rahul Sharma',
      body: 'Dear Rahul Sharma, your balance is 30000',
      context_type: 'fee_due',
      context_id: 9,
      variables: {},
    })

    renderPage('/communications/compose?context_type=fee_due&context_id=9')

    await waitFor(() => expect(screen.getByText('Fee #9')).toBeInTheDocument())

    // select the template
    await userEvent.selectOptions(
      screen.getByLabelText('Template (optional)'),
      '1'
    )
    await userEvent.click(screen.getByRole('button', { name: /Preview with context/ }))

    await waitFor(() => {
      expect(renderWithContextMock).toHaveBeenCalledWith(1, 'fee_due', 9)
      expect(screen.getByText(/Dear Rahul Sharma, your balance is 30000/)).toBeInTheDocument()
      expect(screen.getByText('Rendered preview')).toBeInTheDocument()
    })
  })

  it('attaches the context to the send payload', async () => {
    contextGetMock.mockResolvedValue({
      context_type: 'student',
      context_id: 101,
      label: 'Rahul Sharma',
      detail: '#A001',
      variables: { student: { name: 'Rahul Sharma' } },
      guardian_ids: [],
    })
    messageSendMock.mockResolvedValue({ id: 1 })

    renderPage('/communications/compose?context_type=student&context_id=101')

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    const body = screen.getByPlaceholderText(/Write your message here/)
    await userEvent.type(body, 'Hello Rahul')

    // targeted messages require at least one recipient
    const recipientInput = screen.getByPlaceholderText('e.g. 1, 2, 3')
    await userEvent.type(recipientInput, '1')
    await userEvent.selectOptions(screen.getByLabelText('Recipient Type'), 'user')

    await userEvent.click(screen.getByRole('button', { name: /Send Message/ }))

    await waitFor(() => {
      expect(messageSendMock).toHaveBeenCalledWith(
        expect.objectContaining({
          context_type: 'student',
          context_id: 101,
          body: 'Hello Rahul',
          recipients: [{ recipient_type: 'user', recipient_id: 1 }],
        })
      )
    })
  })

  it('shows an error when the context cannot be loaded', async () => {
    contextGetMock.mockRejectedValue({ detail: 'Student not found' })

    renderPage('/communications/compose?context_type=student&context_id=999')

    await waitFor(() => {
      expect(screen.getByText(/Context unavailable: Student not found/)).toBeInTheDocument()
    })
  })
})
