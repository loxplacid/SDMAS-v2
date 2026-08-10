import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const listMock = vi.fn()

vi.mock('../api/migration/migration-api', () => ({
  migrationApi: {
    list: (...args: unknown[]) => listMock(...args),
  },
  MIGRATION_STATUS_LABELS: {
    READY: 'Ready',
    IMPORTING: 'Importing',
    COMPLETED: 'Completed',
    FAILED: 'Failed',
    MAPPING: 'Mapping',
  },
  MIGRATION_STATUS_STYLES: {
    READY: 'border-ready',
    IMPORTING: 'border-importing',
    COMPLETED: 'border-completed',
    FAILED: 'border-failed',
  },
}))

const { MigrationCenterPage } = await import('../pages/migration/migration-center')

function makeProject(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    name: 'PowerSchool 2026 export',
    source_system: 'PowerSchool-style export',
    status: 'READY',
    original_filename: 'students.csv',
    row_count: 12420,
    records_imported: 0,
    records_rejected: 0,
    last_activity_at: '2026-08-10T09:00:00Z',
    created_at: '2026-08-09T09:00:00Z',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/migration']}>
      <Routes>
        <Route path="/migration" element={<MigrationCenterPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Migration Center (D2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page header and a list of migrations', async () => {
    listMock.mockResolvedValue({
      items: [
        makeProject({ id: 1, name: 'Legacy ERP students', status: 'COMPLETED', records_imported: 12000 }),
        makeProject({ id: 2, name: 'PowerSchool export', status: 'FAILED', records_rejected: 31 }),
      ],
      total: 2,
    })

    renderPage()

    await waitFor(() => expect(screen.getByText('Legacy ERP students')).toBeInTheDocument())
    expect(screen.getByText('PowerSchool export')).toBeInTheDocument()
    expect(screen.getByText('Data Migration')).toBeInTheDocument()
    // Status badges rendered from the API response (inside table cells).
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0)
  })

  it('shows summary tiles counting ready / importing / failed / completed', async () => {
    listMock.mockResolvedValue({
      items: [
        makeProject({ id: 1, status: 'READY' }),
        makeProject({ id: 2, status: 'READY' }),
        makeProject({ id: 3, status: 'FAILED' }),
        makeProject({ id: 4, status: 'IMPORTING' }),
      ],
      total: 4,
    })

    renderPage()

    await waitFor(() => expect(screen.getAllByText('2').length).toBeGreaterThan(0))
    // The four summary tiles exist with their labels (tile labels are
    // distinct from the status badge text).
    expect(screen.getByText('Ready to import')).toBeInTheDocument()
    expect(screen.getAllByText('Importing').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0)
  })

  it('renders an empty state with a call to action when no migrations exist', async () => {
    listMock.mockResolvedValue({ items: [], total: 0 })

    renderPage()

    await waitFor(() => expect(screen.getByText('No migrations yet')).toBeInTheDocument())
    expect(screen.getByText('Start a migration')).toBeInTheDocument()
  })

  it('renders an error state with retry when the API fails', async () => {
    listMock.mockRejectedValueOnce({ detail: 'Migrations could not be loaded.' })
    listMock.mockResolvedValueOnce({
      items: [makeProject({ id: 1, name: 'Recovered export' })],
      total: 1,
    })

    renderPage()

    await waitFor(() => expect(screen.getByText('Migrations couldn\'t be loaded')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Retry'))
    await waitFor(() => expect(screen.getByText('Recovered export')).toBeInTheDocument())
  })
})
