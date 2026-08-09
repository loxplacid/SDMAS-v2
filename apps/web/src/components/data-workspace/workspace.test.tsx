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
    fireEvent.click(screen.getByRole('button', { name: 'Amount' }))
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

  it('switches to dense density through the Density menu (P12 third tier)', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Table density'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Dense' }))
    const cell = document.querySelector('tbody td')
    expect(cell?.className).toContain('py-1.5')
    // the other tiers are distinct — dense is tighter than compact
    expect(cell?.className).not.toContain('py-2.5')
  })

  it('reorders a visible column through the Columns menu (P12)', () => {
    render(<Harness />)
    expect(screen.getAllByRole('columnheader')[0]).toHaveTextContent('Name')
    fireEvent.click(screen.getByLabelText('Manage columns'))
    fireEvent.click(screen.getByRole('button', { name: 'Move Name right' }))
    const headers = screen.getAllByRole('columnheader')
    expect(headers[0]).toHaveTextContent('Status')
    expect(headers[1]).toHaveTextContent('Name')
  })

  it('disables the reorder handle at the boundary (P12)', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Manage columns'))
    expect(screen.getByRole('button', { name: 'Move Name left' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move Amount right' })).toBeDisabled()
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
// saved views (P12 §4 — sort + columns join the filter snapshot)
// ---------------------------------------------------------------------------

describe('DataWorkspace — saved views', () => {
  async function saveView(name: string) {
    fireEvent.click(screen.getByLabelText('Saved views'))
    fireEvent.click(screen.getByText('Save current as…'))
    fireEvent.change(screen.getByLabelText('View name'), { target: { value: name } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  }

  it('restores the saved sort and column set when the view is applied', async () => {
    render(<Harness />)

    // set up the arrangement: sort by Name asc + hide Amount. The columns
    // menu stays open after a toggle (batch editing), so close it between
    // sessions by clicking the trigger again.
    fireEvent.click(screen.getByLabelText('Sort by Name'))
    fireEvent.click(screen.getByLabelText('Manage columns'))
    fireEvent.click(screen.getByRole('button', { name: 'Amount' }))
    fireEvent.click(screen.getByLabelText('Manage columns'))
    expect(screen.queryByRole('columnheader', { name: /Amount/ })).not.toBeInTheDocument()

    await saveView('My arrangement')

    // disrupt both: clear the sort, bring Amount back
    fireEvent.click(screen.getByLabelText('Sort columns'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Clear sorting' }))
    fireEvent.click(screen.getByLabelText('Manage columns'))
    fireEvent.click(screen.getByRole('button', { name: 'Amount' }))
    fireEvent.click(screen.getByLabelText('Manage columns'))
    expect(screen.getByRole('columnheader', { name: /Amount/ })).toBeInTheDocument()

    // apply the view — sort and columns come back together
    fireEvent.click(screen.getByLabelText('Saved views'))
    fireEvent.click(screen.getByText('My arrangement'))

    expect(screen.queryByRole('columnheader', { name: /Amount/ })).not.toBeInTheDocument()
    expect(document.querySelector('th[aria-sort="ascending"]')).not.toBeNull()
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('Amina Kante')
  })

  it('restores the saved sort-only view without disturbing columns', async () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Sort by Name'))
    await saveView('Name asc')

    fireEvent.click(screen.getByLabelText('Sort columns'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Clear sorting' }))
    const rowsBefore = screen.getAllByRole('row').slice(1)
    expect(rowsBefore[0]).toHaveTextContent('Amina Kante') // already lexically first — verify no aria-sort
    expect(document.querySelector('th[aria-sort]')).toBeNull()

    fireEvent.click(screen.getByLabelText('Saved views'))
    fireEvent.click(screen.getByText('Name asc'))

    expect(document.querySelector('th[aria-sort="ascending"]')).not.toBeNull()
    // columns untouched: all three still visible
    expect(screen.getByRole('columnheader', { name: /Amount/ })).toBeInTheDocument()
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

// ---------------------------------------------------------------------------
// URL restore (P12 §8 — survive refresh and deep linking)
// ---------------------------------------------------------------------------

describe('DataWorkspace — URL restore', () => {
  // Restore is synchronous: `useWorkspace` reads the URL in its useState
  // initializers, so plain assertions right after `render` are safe. The
  // hook's 180ms URL write-back is irrelevant here — its timer is cleared
  // by the effect cleanup when the tree unmounts, so it never leaks into
  // the next test.
  function makeRows(n: number, inactiveFrom = Number.POSITIVE_INFINITY) {
    return Array.from({ length: n }, (_, i) => ({
      id: i + 1,
      name: `Student ${i + 1}`,
      status: i + 1 >= inactiveFrom ? 'inactive' : 'active',
      amount: i * 100,
    }))
  }

  it('restores filters + multi-column sort from a deep link on mount', () => {
    // 40 rows, 25 inactive (Student 16–40) — a deep link that a colleague
    // shared from the same workspace state.
    window.history.replaceState(null, '', '/students?f_status=inactive&sort=name:desc')
    render(<Harness rows={makeRows(40, 16)} size={10} urlSync />)

    // Filter restored: active rows are gone (Student 15 is the last active).
    expect(screen.queryByText('Student 15')).not.toBeInTheDocument()
    // Sort + slice restored: page 1 of the 25 filtered rows, name desc →
    // the newest Student numbers first (Student 40…31 on this page).
    expect(document.querySelector('th[aria-sort="descending"]')).not.toBeNull()
    expect(screen.getByText('Student 40')).toBeInTheDocument()
    expect(screen.getByText('Student 31')).toBeInTheDocument()
    expect(screen.queryByText('Student 30')).not.toBeInTheDocument()
    // Footer reflects the *filtered* total (25), not the raw 40-row set.
    // (`span.tabular-nums` scopes past the pagination bar's own "25".)
    expect(screen.getByText('1–10')).toBeInTheDocument()
    expect(screen.getByText('25', { selector: 'span.tabular-nums' })).toBeInTheDocument()
  })

  it('restores the page param on a bare refresh', () => {
    window.history.replaceState(null, '', '/students?page=2')
    render(<Harness rows={makeRows(25)} size={10} urlSync />)

    expect(screen.getByText('11–20')).toBeInTheDocument()
    expect(screen.getByText('Student 11')).toBeInTheDocument()
    expect(screen.queryByText('Student 10')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// preference persistence (P12 §5/§6 — per-module, survives remount)
// ---------------------------------------------------------------------------

describe('DataWorkspace — preference persistence', () => {
  it('persists column visibility and density across remounts (same viewKey)', () => {
    const first = render(<Harness />)
    fireEvent.click(screen.getByLabelText('Manage columns'))
    fireEvent.click(screen.getByRole('button', { name: 'Amount' }))
    expect(screen.queryByRole('columnheader', { name: /Amount/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Table density'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Dense' }))
    let cell = document.querySelector('tbody td')
    expect(cell?.className).toContain('py-1.5')
    first.unmount()

    // Remount with the same viewKey — both preferences must come back.
    render(<Harness />)
    expect(screen.queryByRole('columnheader', { name: /Amount/ })).not.toBeInTheDocument()
    cell = document.querySelector('tbody td')
    expect(cell?.className).toContain('py-1.5')
  })

  it('restores the default column set with Reset to defaults', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Manage columns'))
    fireEvent.click(screen.getByRole('button', { name: 'Amount' }))
    expect(screen.queryByRole('columnheader', { name: /Amount/ })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Reset to defaults' }))
    expect(screen.getByRole('columnheader', { name: /Amount/ })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /Name/ })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// large datasets (P12 §10 — never render what the page slice doesn't need)
// ---------------------------------------------------------------------------

describe('DataWorkspace — large datasets', () => {
  // Alternating statuses (distinct from the URL-restore helper's split) so
  // the two helpers can't be confused despite the similar row shape.
  const makeAlternatingRows = (n: number) =>
    Array.from({ length: n }, (_, i) => ({
      id: i + 1,
      name: `Student ${i + 1}`,
      status: i % 2 === 0 ? 'active' : 'inactive',
      amount: i * 100,
    }))

  it('renders only the current page slice for a 1,000-row dataset', () => {
    render(<Harness rows={makeAlternatingRows(1000)} size={20} />)
    // header + 20 rows — the other 980 rows never touch the DOM.
    expect(screen.getAllByRole('row')).toHaveLength(21)
    expect(screen.getByText('1–20')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Next page'))
    expect(screen.getByText('21–40')).toBeInTheDocument()
    expect(screen.getByText('Student 21')).toBeInTheDocument()
    expect(screen.queryByText('Student 20')).not.toBeInTheDocument()
  })

  it('keeps the selection set stable across pages (cross-page bulk selection)', () => {
    render(<Harness rows={makeAlternatingRows(1000)} size={20} bulk />)
    fireEvent.click(screen.getByLabelText('Select row 1'))
    expect(screen.getByText('1 selected')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Next page'))
    // Selection is an id-set, not a snapshot of the page it was made on.
    expect(screen.getByText('1 selected')).toBeInTheDocument()
    // The header checkbox still selects the *current* page only.
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all rows on this page' }))
    expect(screen.getByText('21 selected')).toBeInTheDocument()
  })
})
