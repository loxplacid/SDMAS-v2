import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import {
  applyFilters,
  DataTable,
  emptyFilterState,
  facetCounts,
  filtersEqual,
  filtersFromQueryString,
  filtersToQueryString,
  parseQuery,
  rangeChipLabel,
  withFacet,
  withRange,
  type Column,
} from '../components/ui/table'

interface FeeRow {
  id: number
  student: string
  amount: number
  due: string
  status: string
}

const rows: FeeRow[] = [
  { id: 1, student: 'Amina Kante', amount: 12000, due: '2026-01-15', status: 'Overdue' },
  { id: 2, student: 'Bello Musa', amount: 5000, due: '2026-02-01', status: 'Paid' },
  { id: 3, student: 'Chidi Okafor', amount: 8000, due: '2026-03-10', status: 'Due' },
  { id: 4, student: 'Damilola Ade', amount: 2500, due: '2026-01-05', status: 'Paid' },
]

const columns: Column<FeeRow>[] = [
  { key: 'student', header: 'Student', type: 'person' },
  { key: 'amount', header: 'Amount', type: 'amount' },
  { key: 'due', header: 'Due', type: 'date' },
  {
    key: 'status',
    header: 'Status',
    type: 'status',
    statusVariants: { Paid: 'success', Due: 'warning', Overdue: 'danger' },
  },
]

const ids = (result: FeeRow[]) => result.map((r) => r.id)

beforeEach(() => {
  localStorage.clear()
})

afterEach(async () => {
  // the shared tier MutationObserver fires on this change — flush it inside
  // act so its setTier re-render is wrapped (and clean URL pollution)
  await act(async () => {
    delete document.documentElement.dataset.motionTier
  })
  window.history.replaceState(null, '', '/')
})

// ---------------------------------------------------------------------------
// the engine (§6.1–§6.4)
// ---------------------------------------------------------------------------

describe('filter model — search', () => {
  it('matches searchable columns only (T27: status/amount are never searched)', () => {
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'amina' }, columns))).toEqual([1])
    // partial substring of a status value that is NOT a facet word finds nothing
    expect(applyFilters(rows, { ...emptyFilterState(), query: 'erdu' }, columns)).toHaveLength(0)
    // amount values are range-filtered, not searched
    expect(applyFilters(rows, { ...emptyFilterState(), query: '12000' }, columns)).toHaveLength(0)
  })

  it('searches person objects by name', () => {
    const objRows = [{ id: 1, person: { name: 'Zainab Ali' } }]
    const cols: Column<(typeof objRows)[number]>[] = [
      { key: 'person', header: 'Person', type: 'person' },
    ]
    const result = applyFilters(objRows, { ...emptyFilterState(), query: 'zainab' }, cols)
    expect(result.map((r) => r.id)).toEqual([1])
  })
})

describe('filter model — facets & ranges', () => {
  it('filters by exact facet values, add and remove', () => {
    let s = emptyFilterState()
    s = withFacet(s, 'status', 'Paid', true)
    expect(ids(applyFilters(rows, s, columns))).toEqual([2, 4])
    // T29: multiple values in ONE facet column OR within the column
    s = withFacet(s, 'status', 'Overdue', true)
    expect(ids(applyFilters(rows, s, columns))).toEqual([1, 2, 4])
    s = withFacet(s, 'status', 'Overdue', false)
    expect(ids(applyFilters(rows, s, columns))).toEqual([2, 4])
  })

  it('filters numeric and date ranges with inclusive boundaries', () => {
    let s = withRange(emptyFilterState(), 'amount', { min: 6000 })
    expect(ids(applyFilters(rows, s, columns))).toEqual([1, 3])
    s = withRange(emptyFilterState(), 'amount', { min: 6000, max: 10000 })
    expect(ids(applyFilters(rows, s, columns))).toEqual([3])
    s = withRange(emptyFilterState(), 'due', { min: '2026-02-01' })
    expect(ids(applyFilters(rows, s, columns))).toEqual([2, 3])
    s = withRange(emptyFilterState(), 'due', { min: '2026-02-01', max: '2026-03-10' })
    expect(ids(applyFilters(rows, s, columns))).toEqual([2, 3])
  })

  it('computes facet counts ordered by count then alpha (T29)', () => {
    const statusCol = columns.find((c) => c.key === 'status')!
    expect(facetCounts(rows, statusCol)).toEqual([
      { value: 'Paid', count: 2 },
      { value: 'Due', count: 1 },
      { value: 'Overdue', count: 1 },
    ])
  })

  it('labels range chips for the rail (T30)', () => {
    const amountCol = columns.find((c) => c.key === 'amount')!
    expect(rangeChipLabel(amountCol, { min: 5000 })).toBe('AMOUNT ≥ ₦5,000')
    const dueCol = columns.find((c) => c.key === 'due')!
    expect(rangeChipLabel(dueCol, { max: '2026-02-01' })).toContain('≤')
  })
})

describe('filter model — the smart query language (T32)', () => {
  it('maps bare facet words to facets with canonical casing', () => {
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'overdue' }, columns))).toEqual([1])
  })

  it('parses range predicates on typed columns', () => {
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'amount>10000' }, columns))).toEqual([1])
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'due>=2026-02-01' }, columns))).toEqual([2, 3])
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'amount=5000' }, columns))).toEqual([2])
  })

  it('parses AND groups, OR groups, and named-column phrases', () => {
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'amount>9000 status:overdue' }, columns))).toEqual([1])
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'paid OR overdue' }, columns))).toEqual([1, 2, 4])
    expect(ids(applyFilters(rows, { ...emptyFilterState(), query: 'student:"Amina Kante"' }, columns))).toEqual([1])
  })

  it('builds OR-groups of AND-terms', () => {
    const and = parseQuery('paid overdue', rows, columns)
    expect(and).toHaveLength(1)
    expect(and[0]).toHaveLength(2)
    const or = parseQuery('paid OR overdue', rows, columns)
    expect(or).toHaveLength(2)
  })
})

describe('filter model — URL serialization (T34)', () => {
  it('round-trips through the query string', () => {
    let s = { ...emptyFilterState(), query: 'overdue' }
    s = withFacet(s, 'status', 'Due', true)
    s = withRange(s, 'amount', { min: 5000 })
    const back = filtersFromQueryString(filtersToQueryString(s), columns)
    expect(filtersEqual(back, s)).toBe(true)
  })

  it('ignores stale or unknown params', () => {
    const s = filtersFromQueryString('f_ghost=1&f_q=paid', columns)
    expect(s.query).toBe('paid')
    expect(s.facets).toEqual({})
  })

  it('merges table filters into the URL without clobbering page params (T34)', async () => {
    window.history.replaceState(null, '', '/fee-due?term=2026&page=2')
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} filterable urlSync />)
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'overdue' } })
    await waitFor(() => expect(window.location.search).toContain('f_q=overdue'))
    expect(window.location.search).toContain('term=2026')
    expect(window.location.search).toContain('page=2')
  })
})

// ---------------------------------------------------------------------------
// the frame + rail integration (§6)
// ---------------------------------------------------------------------------

describe('DataTable filterable — rail', () => {
  it('renders the rail and filters locally with a count footer', async () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} filterable />)
    expect(screen.getByLabelText('Filter table')).toBeInTheDocument()
    expect(screen.getByText(/of 4 rows/)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'amina' } })
    await waitFor(() => expect(screen.getByText('1 of 4 rows')).toBeInTheDocument())
    expect(screen.getByText('Amina Kante')).toBeInTheDocument()
    expect(screen.queryByText('Bello Musa')).not.toBeInTheDocument()
  })

  it('adds and removes facet chips through the filter panel (T29–T30)', async () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} filterable />)
    fireEvent.click(screen.getByLabelText('Add filter'))
    const panel = screen.getByRole('dialog')
    expect(within(panel).getByText('Paid')).toBeInTheDocument()

    fireEvent.click(within(panel).getByRole('checkbox', { name: /Paid/ }))
    // the chip carries a named remove affordance (T30)
    expect(screen.getByLabelText('Remove status: Paid')).toBeInTheDocument()
    expect(screen.getByText('2 of 4 rows')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Amina Kante')).not.toBeInTheDocument())
    expect(screen.getByText('Bello Musa')).toBeInTheDocument()

    fireEvent.click(within(panel).getByRole('checkbox', { name: /Paid/ }))
    expect(screen.queryByLabelText('Remove status: Paid')).not.toBeInTheDocument()
    expect(screen.getByText('Amina Kante')).toBeInTheDocument()
  })

  it('applies range filters from the panel with a chip (T31)', async () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} filterable />)
    fireEvent.click(screen.getByLabelText('Add filter'))
    fireEvent.change(screen.getByLabelText('Amount minimum'), { target: { value: '6000' } })

    expect(screen.getByText(/AMOUNT ≥/)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('Bello Musa')).not.toBeInTheDocument())
    expect(screen.getByText('Amina Kante')).toBeInTheDocument()
    expect(screen.getByText('Chidi Okafor')).toBeInTheDocument()
  })

  it('shows query-language completions (T32)', () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} filterable />)
    const input = screen.getByLabelText('Filter table')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'over' } })
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    expect(within(screen.getByRole('listbox')).getByText('Overdue')).toBeInTheDocument()
  })
})

describe('DataTable filterable — saved views (T35–T37)', () => {
  it('saves, applies, updates, renames and deletes a view', async () => {
    render(
      <DataTable
        columns={columns}
        data={rows}
        keyExtractor={(r) => r.id}
        filterable
        viewKey="fee-due"
      />
    )

    // establish a filter and save it as a view
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'overdue' } })
    await waitFor(() => expect(screen.queryByText('Bello Musa')).not.toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('Saved views'))
    fireEvent.click(screen.getByText('Save current as…'))
    fireEvent.change(screen.getByLabelText('View name'), { target: { value: 'Overdue focus' } })
    fireEvent.click(screen.getByText('Save'))

    // change the filter → dirty; the menu entry becomes Update (T37)
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'paid' } })
    await waitFor(() => expect(screen.getByText('2 of 4 rows')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('Saved views'))
    expect(screen.getByText('Update saved view')).toBeInTheDocument()

    // apply the saved view → filters restore, menu closes
    fireEvent.click(screen.getByText('Overdue focus'))
    await waitFor(() => expect(screen.getByDisplayValue('overdue')).toBeInTheDocument())

    // rename
    fireEvent.click(screen.getByLabelText('Saved views'))
    fireEvent.click(screen.getByLabelText('Rename Overdue focus'))
    fireEvent.change(screen.getByLabelText('Rename view input'), {
      target: { value: 'Overdue principal' },
    })
    fireEvent.keyDown(screen.getByLabelText('Rename view input'), { key: 'Enter' })
    expect(screen.getByText('Overdue principal')).toBeInTheDocument()

    // delete
    fireEvent.click(screen.getByLabelText('Delete Overdue principal'))
    await waitFor(() => expect(screen.queryByText('Overdue principal')).not.toBeInTheDocument())
  })
})

describe('DataTable filterable — exit choreography (T33)', () => {
  it('clears every exiting row when filter batches overlap — no ghost leak', async () => {
    vi.useFakeTimers()
    // precise tier enables the exit choreography (efficient/minimal snap)
    document.documentElement.dataset.motionTier = 'precise'
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} filterable />)

    fireEvent.click(screen.getByLabelText('Add filter'))
    const panel = screen.getByRole('dialog')
    // two immediate facet toggles: Paid then Paid+Overdue. The first batch's
    // exit ghosts (Amina, Chidi) must clear even though a second batch lands
    // while they are still fading.
    fireEvent.click(within(panel).getByRole('checkbox', { name: /Paid/ }))
    fireEvent.click(within(panel).getByRole('checkbox', { name: /Overdue/ }))
    // flush the Rows exit effect (setExiting) inside act — sync act alone
    // leaves the effect-flushed update unwrapped.
    await act(async () => {})

    // Amina re-entered as a real row while her exit ghost still fades
    expect(screen.getAllByText('Amina Kante')).toHaveLength(2)
    // the exit window closes → the ghost is removed, never leaked
    act(() => vi.advanceTimersByTime(300))
    expect(screen.getAllByText('Amina Kante')).toHaveLength(1)
    expect(screen.queryByText('Chidi Okafor')).not.toBeInTheDocument()
    vi.useRealTimers()
  })
})

describe('DataTable filterable — controlled mode', () => {
  it('reports changes without local filtering (server-side pages)', async () => {
    const onFiltersChange = vi.fn()
    render(
      <DataTable
        columns={columns}
        data={rows}
        keyExtractor={(r) => r.id}
        filterable
        filters={emptyFilterState()}
        onFiltersChange={onFiltersChange}
      />
    )
    fireEvent.change(screen.getByLabelText('Filter table'), { target: { value: 'amina' } })
    await waitFor(() => expect(onFiltersChange).toHaveBeenCalled())
    const next = onFiltersChange.mock.calls[0][0] as { query: string }
    expect(next.query).toBe('amina')
    // no local filtering — the frame trusts the page
    expect(screen.getByText('Bello Musa')).toBeInTheDocument()
  })
})
