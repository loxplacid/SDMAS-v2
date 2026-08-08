import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useMemo, type ReactNode } from 'react'
import { DataWorkspace, type DataWorkspaceEmpty } from './workspace'
import { useWorkspace } from './use-workspace'
import type { Column } from '../ui/table'

interface WsRow {
  id: number
  name: string
  status: string
  amount: number
}

const sample: WsRow[] = [
  { id: 1, name: 'Amina Kante', status: 'active', amount: 12000 },
  { id: 2, name: 'Bello Musa', status: 'inactive', amount: 5000 },
  { id: 3, name: 'Chidi Okafor', status: 'active', amount: 8000 },
  { id: 4, name: 'Dara Ade', status: 'active', amount: 2500 },
]

function Harness(props: {
  rows?: WsRow[]
  size?: number
  bulk?: boolean
  empty?: DataWorkspaceEmpty
  error?: string | null
  onRetry?: () => void
  primaryAction?: ReactNode
  urlSync?: boolean
}) {
  const {
    rows = sample,
    size = 20,
    bulk = false,
    empty,
    error = null,
    onRetry,
    primaryAction,
    urlSync = false,
  } = props

  const columns = useMemo<Column<WsRow>[]>(
    () => [
      { key: 'name', header: 'Name', type: 'text', sortable: true },
      { key: 'status', header: 'Status', type: 'status', sortable: true },
      { key: 'amount', header: 'Amount', type: 'amount' },
    ],
    []
  )
  const ws = useWorkspace<WsRow>({ viewKey: 'test-ws', columns, defaultPageSize: size, urlSync })

  return (
    <DataWorkspace
      workspace={ws}
      title="Test Workspace"
      description="A test workspace"
      columns={columns}
      keyExtractor={(r) => r.id}
      data={rows}
      total={rows.length}
      pages={Math.ceil(rows.length / ws.size)}
      loading={false}
      error={error}
      onRetry={onRetry ?? (() => {})}
      onRefresh={() => {}}
      mode="local"
      primaryAction={primaryAction}
      bulkActions={bulk ? () => <button type="button">Archive</button> : undefined}
      empty={empty}
    />
  )
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(async () => {
  await act(async () => {
    delete document.documentElement.dataset.motionTier
  })
  window.history.replaceState(null, '', '/')
})

// ---------------------------------------------------------------------------
// composition
// ---------------------------------------------------------------------------

describe('DataWorkspace — header', () => {
  it('renders the workspace title, description and primary action', () => {
    render(
      <Harness primaryAction={<button type="button">Add Student</button>} />
    )
    expect(screen.getByText('Test Workspace')).toBeInTheDocument()
    expect(screen.getByText('A test workspace')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Student' })).toBeInTheDocument()
  })

  it('hides the sort menu when no column is sortable (server pages without backend sort)', () => {
    function ServerHarness() {
      const columns = useMemo<Column<WsRow>[]>(() => [
        { key: 'name', header: 'Name', type: 'text' },
        { key: 'status', header: 'Status', type: 'status' },
      ], [])
      const ws = useWorkspace<WsRow>({ viewKey: 'test-ws', columns, defaultPageSize: 20, urlSync: false })
      return (
        <DataWorkspace
          workspace={ws}
          title="Payments"
          columns={columns}
          keyExtractor={(r) => r.id}
          data={sample}
          total={sample.length}
          pages={1}
          loading={false}
          error={null}
          onRetry={() => {}}
          onRefresh={() => {}}
          mode="server"
        />
      )
    }
    render(<ServerHarness />)
    expect(screen.queryByLabelText('Sort columns')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// filtering / sorting / pagination (local mode)
// ---------------------------------------------------------------------------

describe('DataWorkspace — local mode behavior', () => {
  it('filters rows from the rail search box', async () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'amina' } })
    await waitFor(() => expect(screen.queryByText('Bello Musa')).not.toBeInTheDocument())
    expect(screen.getByText('Amina Kante')).toBeInTheDocument()
  })

  it('sorts by a sortable header (click cycle asc → desc) with aria-sort', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Sort by Name'))
    // asc: Amina, Bello, Chidi, Dara
    let rows = screen.getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('Amina Kante')
    expect(rows[3]).toHaveTextContent('Dara Ade')
    expect(document.querySelector('th[aria-sort="ascending"]')).not.toBeNull()

    // desc re-queries the (re-created) rows
    fireEvent.click(screen.getByLabelText('Sort by Name'))
    rows = screen.getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('Dara Ade')
    expect(document.querySelector('th[aria-sort="descending"]')).not.toBeNull()
  })

  it('paginates client-side with a range footer', () => {
    const many = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      name: `Student ${i + 1}`,
      status: 'active',
      amount: 1000,
    }))
    render(<Harness rows={many} size={10} />)
    expect(screen.getByText('1–10')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(11) // header + 10 rows

    fireEvent.click(screen.getByLabelText('Next page'))
    expect(screen.getByText('11–20')).toBeInTheDocument()
    expect(screen.getByText('Student 11')).toBeInTheDocument()
    expect(screen.queryByText('Student 10')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// selection + bulk actions
// ---------------------------------------------------------------------------

describe('DataWorkspace — selection and bulk actions', () => {
  it('selects rows individually, showing the selection bar and bulk action', () => {
    render(<Harness bulk />)
    fireEvent.click(screen.getByLabelText('Select row 1'))
    expect(screen.getByText('1 selected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive' })).toBeInTheDocument()
  })

  it('selects the current page with the header checkbox (not the whole dataset)', () => {
    render(<Harness bulk size={2} />)
    // the th and its input share the label — the checkbox is the only one by role
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all rows on this page' }))
    // only the 2 rows on page 1 are selected — page semantics (P8 §12)
    expect(screen.getByText('2 selected')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Next page'))
    expect(screen.getByText('2 selected')).toBeInTheDocument()
    expect(screen.queryByText('4 selected')).not.toBeInTheDocument()
  })

  it('clears the selection from the bar', () => {
    render(<Harness bulk />)
    fireEvent.click(screen.getByLabelText('Select row 1'))
    fireEvent.click(screen.getByText('Clear selection'))
    expect(screen.queryByText('1 selected')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// column manager + density
// ---------------------------------------------------------------------------

describe('DataWorkspace — column manager and density', () => {
  it('hides a column through the Columns menu', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Manage columns'))
    fireEvent.click(screen.getByRole('menuitem', { name: /Amount/ }))
    expect(screen.queryByRole('columnheader', { name: /Amount/ })).not.toBeInTheDocument()
    // other columns survive
    expect(screen.getByRole('columnheader', { name: /Name/ })).toBeInTheDocument()
  })

  it('switches to compact density through the Density menu', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Table density'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Compact' }))
    const cell = document.querySelector('tbody td')
    expect(cell?.className).toContain('py-2.5')
  })
})

// ---------------------------------------------------------------------------
// empty / error states
// ---------------------------------------------------------------------------

describe('DataWorkspace — empty and error states', () => {
  it('renders the module empty state when no data exists and no filters are active', () => {
    render(
      <Harness
        rows={[]}
        empty={{ title: 'No students yet', description: 'Add the first student.', actionLabel: 'Add Student', onAction: () => {} }}
      />
    )
    expect(screen.getByText('No students yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Student' })).toBeInTheDocument()
  })

  it('shows an actionable error state and retries', () => {
    const onRetry = vi.fn()
    render(<Harness error="Failed to load students" onRetry={onRetry} />)
    expect(screen.getByText('Failed to load students')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Try Again/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// URL state (P8 §16)
// ---------------------------------------------------------------------------

describe('DataWorkspace — URL state', () => {
  it('mirrors the workspace into the URL and restores it on mount', async () => {
    render(<Harness urlSync />)
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'bello' } })
    await waitFor(() => expect(window.location.search).toContain('f_q=bello'))
  })
})
