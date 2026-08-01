import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import type { TimelineItem, TimelineResponse, TimelineParams } from '../api/timeline/timeline-api'

const getTimelineMock = vi.fn()
vi.mock('../api/timeline/timeline-api', () => ({
  timelineApi: { get: (...args: unknown[]) => getTimelineMock(...args) },
}))

// Import after mocking
const { Timeline } = await import('../components/timeline/timeline')

function makeItem(overrides: Partial<TimelineItem> = {}): TimelineItem {
  return {
    id: 'fees:1',
    event_type: 'fees.payment',
    timestamp: '2026-08-01T09:00:00Z',
    actor: 'Ravi Kumar',
    entity: 'Rahul Sharma',
    description: 'Payment of ₹50,000 recorded · cash',
    severity: 'success',
    source: 'fees',
    metadata: { student_id: 101, amount: 5000000, receipt: 'R-001' },
    deep_link: '/students/101/360',
    ...overrides,
  }
}

function makeResponse(
  items: TimelineItem[] = [],
  overrides: Partial<TimelineResponse> = {},
): TimelineResponse {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    sources: [
      { key: 'fees', label: 'Payments', count: 2, available: true },
      { key: 'academic', label: 'Enrollments', count: 1, available: true },
    ],
    degraded: false,
    ...overrides,
  }
}

function renderTimeline(props: Record<string, unknown> = {}) {
  return render(
    <MemoryRouter initialEntries={['/timeline']}>
      <Routes>
        <Route
          path="/timeline"
          element={<Timeline {...(props as any)} />}
        />
        <Route path="/students/:id/360" element={<div>Student 360 Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.resetAllMocks()
})

describe('Timeline component', () => {
  it('shows a loading skeleton, then renders aggregated items', async () => {
    let resolveFn!: (v: TimelineResponse) => void
    getTimelineMock.mockReturnValue(new Promise((res) => { resolveFn = res }))

    renderTimeline()

    expect(screen.getByLabelText('Loading timeline')).toBeInTheDocument()

    resolveFn(makeResponse([makeItem(), makeItem({ id: 'academic:1', event_type: 'academic.enrolled', entity: 'Meera Nair', source: 'academic', severity: 'info', description: 'Enrolled in Grade 10 · active', metadata: { student_id: 102, class_id: 5 } })]))
    await waitFor(() => {
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
      expect(screen.getByText(/Payment of/)).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Loading timeline')).not.toBeInTheDocument()
  })

  it('renders an error state with retry when the API fails', async () => {
    getTimelineMock.mockRejectedValueOnce({ detail: 'Timeline unavailable' })

    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('Timeline unavailable')).toBeInTheDocument()
    })
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('shows a degraded banner when a source is unavailable but still renders items', async () => {
    getTimelineMock.mockResolvedValueOnce(
      makeResponse([makeItem()], { degraded: true })
    )

    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
      expect(screen.getByText(/Some data sources are unavailable/)).toBeInTheDocument()
    })
  })

  it('filters by source and re-fetches with the selected source', async () => {
    getTimelineMock.mockResolvedValueOnce(makeResponse([makeItem()]))
    getTimelineMock.mockResolvedValueOnce(makeResponse([makeItem({ id: 'academic:2', source: 'academic' })]))
    getTimelineMock.mockResolvedValueOnce(makeResponse([makeItem({ id: 'academic:3', source: 'academic' })]))
    getTimelineMock.mockResolvedValueOnce(makeResponse([makeItem({ id: 'academic:4', source: 'academic' })]))

    renderTimeline()

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    await userEvent.selectOptions(screen.getByLabelText('Source'), 'academic')

    await waitFor(() => {
      const lastCall = getTimelineMock.mock.calls[getTimelineMock.mock.calls.length - 1][0] as TimelineParams
      expect(lastCall.source).toBe('academic')
    })
  })

  it('filters by actor text input', async () => {
    // Persistent mock — the debounced filter change triggers a second fetch.
    getTimelineMock.mockResolvedValue(makeResponse([makeItem()]))

    renderTimeline()

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'Ravi' } })

    await waitFor(() => {
      const lastCall = getTimelineMock.mock.calls[getTimelineMock.mock.calls.length - 1][0] as TimelineParams
      expect(lastCall.actor).toBe('Ravi')
    })
  })

  it('navigates to the deep link target', async () => {
    getTimelineMock.mockResolvedValueOnce(makeResponse([makeItem()]))

    renderTimeline()

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /open \/students\/101\/360/i }))
    expect(await screen.findByText('Student 360 Page')).toBeInTheDocument()
  })

  it('expands and collapses metadata details', async () => {
    getTimelineMock.mockResolvedValueOnce(makeResponse([makeItem()]))

    renderTimeline()

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    // Collapsed by default — metadata values hidden
    expect(screen.queryByText('R-001')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Show details' }))
    expect(await screen.findByText('R-001')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Collapse details' }))
    await waitFor(() => {
      expect(screen.queryByText('R-001')).not.toBeInTheDocument()
    })
  })

  it('loads more pages and appends items', async () => {
    getTimelineMock.mockResolvedValueOnce(
      makeResponse([makeItem()], { total: 2 })
    )
    getTimelineMock.mockResolvedValueOnce(
      makeResponse([makeItem({ id: 'risk:1', event_type: 'risk.attendance', source: 'risk', severity: 'warning', description: 'Attendance 68%', metadata: { rule_code: 'x' } })], { total: 2, page: 2 })
    )

    renderTimeline()

    await waitFor(() => expect(screen.getByText('Rahul Sharma')).toBeInTheDocument())

    const loadMore = await screen.findByRole('button', { name: /load more/i })
    await userEvent.click(loadMore)

    await waitFor(() => {
      expect(getTimelineMock).toHaveBeenCalledTimes(2)
      expect(screen.getByText(/Attendance 68%/)).toBeInTheDocument()
    })
  })

  it('renders an empty state when there are no events', async () => {
    getTimelineMock.mockResolvedValueOnce(makeResponse([]))

    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('No activity recorded yet.')).toBeInTheDocument()
    })
  })

  it('caps visible rows and links to the full timeline when maxVisible is set', async () => {
    getTimelineMock.mockResolvedValueOnce(
      makeResponse(
        [1, 2, 3, 4].map((n) => makeItem({ id: `fees:${n}` })),
        { total: 4 }
      )
    )

    renderTimeline({ compact: true, maxVisible: 3, pageSize: 10 })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /view full timeline/i })).toBeInTheDocument()
    })
    expect(screen.getAllByText('Rahul Sharma')).toHaveLength(3)
  })
})
