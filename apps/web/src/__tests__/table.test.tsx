import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DataTable, Table } from '../components/ui/table'
import type { Column } from '../components/ui/table'

interface Row {
  id: number
  name: string
  amount: number
  date: string
  status: string
  progress: number
  note?: string
}

const rows: Row[] = [
  { id: 1, name: 'Amina Kante', amount: 12400, date: '2026-01-15', status: 'paid', progress: 80, note: 'term one' },
  { id: 2, name: 'Bello Musa', amount: 0, date: '2026-02-03', status: 'due', progress: 35 },
]

const columns: Column<Row>[] = [
  { key: 'name', header: 'Student', type: 'person' },
  { key: 'amount', header: 'Balance', type: 'amount' },
  { key: 'date', header: 'Due', type: 'date' },
  { key: 'status', header: 'Status', type: 'status', statusVariants: { paid: 'success', due: 'warning' } },
  { key: 'progress', header: 'Attendance', type: 'progress' },
]

const legacyColumns: Column<Row>[] = [
  { key: 'name', header: 'Student' },
  { key: 'amount', header: 'Balance' },
]

describe('DataTable — legacy byte-parity', () => {
  it('renders byte-identical markup to legacy Table for untyped columns', () => {
    const { container: legacy } = render(<Table columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} />)
    const { container: frame } = render(
      <DataTable columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} />
    )
    expect(frame.innerHTML).toBe(legacy.innerHTML)
  })

  it('renders byte-identical empty states', () => {
    const { container: legacy } = render(
      <Table columns={legacyColumns} data={[]} keyExtractor={(r) => r.id} emptyMessage="No students" />
    )
    const { container: frame } = render(
      <DataTable columns={legacyColumns} data={[]} keyExtractor={(r) => r.id} emptyMessage="No students" />
    )
    expect(frame.innerHTML).toBe(legacy.innerHTML)
    expect(screen.getAllByText('No students')).toHaveLength(2)
  })

  it('renders byte-identical loading skeletons', () => {
    const { container: legacy } = render(
      <Table columns={legacyColumns} data={[]} keyExtractor={(r) => r.id} loading />
    )
    const { container: frame } = render(
      <DataTable columns={legacyColumns} data={[]} keyExtractor={(r) => r.id} loading />
    )
    expect(frame.innerHTML).toBe(legacy.innerHTML)
  })

  it('preserves zebra striping, stagger, and hover affordance classes', () => {
    const { container } = render(
      <DataTable columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} onRowClick={() => {}} />
    )
    const rowsEl = container.querySelectorAll('tbody tr')
    expect(rowsEl).toHaveLength(2)
    // zebra on the second row
    expect(rowsEl[1].className).toContain('bg-[var(--color-bg)]/40')
    // stagger delay present
    expect((rowsEl[0] as HTMLElement).style.animationDelay).toBe('0ms')
    expect((rowsEl[1] as HTMLElement).style.animationDelay).toBe('20ms')
    // hover affordance when clickable
    expect(rowsEl[0].className).toContain('cursor-pointer')
  })

  it('honors hideOnMobile and custom className passthrough', () => {
    const { container } = render(
      <DataTable
        columns={[
          { key: 'name', header: 'Student' },
          { key: 'note', header: 'Note', hideOnMobile: true, className: 'max-w-[200px]' },
        ]}
        data={rows}
        keyExtractor={(r) => r.id}
      />
    )
    const hiddenTh = container.querySelector('th.hidden')
    expect(hiddenTh?.textContent).toBe('Note')
    expect(container.querySelector('td.max-w-\\[200px\\]')).not.toBeNull()
  })
})

describe('DataTable — type system', () => {
  it('renders person columns with initials avatars', () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Amina Kante')).toBeInTheDocument()
    expect(screen.getByText('AK')).toBeInTheDocument()
    expect(screen.getByText('BM')).toBeInTheDocument()
  })

  it('renders amounts with NGN currency and dash for zero', () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('₦12,400')).toBeInTheDocument()
    expect(screen.getByText('-')).toBeInTheDocument()
  })

  it('renders person objects with avatar image and name', () => {
    const cols: Column<Row>[] = [
      { key: 'name', header: 'Student', type: 'person', accessor: () => ({ name: 'Chidi Okafor', avatar: 'https://example.com/a.png' }) },
    ]
    const { container } = render(<DataTable columns={cols} data={[rows[0]]} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Chidi Okafor')).toBeInTheDocument()
    expect(container.querySelector('tbody img')).toHaveAttribute('src', 'https://example.com/a.png')
  })

  it('renders dates in d MMM yyyy form', () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('15 Jan 2026')).toBeInTheDocument()
    expect(screen.getByText('3 Feb 2026')).toBeInTheDocument()
  })

  it('renders status pills via the variant map', () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} />)
    const paid = screen.getByText('paid')
    expect(paid.className).toContain('bg-[var(--color-success-light)]')
    expect(screen.getByText('due').className).toContain('bg-[var(--color-warning-light)]')
  })

  it('renders progress bars with the percentage', () => {
    render(<DataTable columns={columns} data={rows} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('35%')).toBeInTheDocument()
  })

  it('lets a custom render override the type renderer', () => {
    const cols: Column<Row>[] = [
      { key: 'name', header: 'Student', type: 'person', render: (r) => <strong>{r.name}</strong> },
    ]
    render(<DataTable columns={cols} data={rows} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Amina Kante').tagName).toBe('STRONG')
  })

  it('supports explicit accessors', () => {
    const cols: Column<Row>[] = [
      { key: 'full', header: 'Full', accessor: (r) => `${r.name} (${r.id})` },
    ]
    render(<DataTable columns={cols} data={rows} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Amina Kante (1)')).toBeInTheDocument()
  })

  it('applies numeric right-alignment only to typed columns', () => {
    const { container } = render(
      <DataTable
        columns={[
          { key: 'name', header: 'Student' },
          { key: 'amount', header: 'Balance', type: 'amount' },
        ]}
        data={rows}
        keyExtractor={(r) => r.id}
      />
    )
    const tds = container.querySelectorAll('tbody td')
    // name td: no alignment class; amount td: text-right
    expect(tds[0].className).not.toContain('text-right')
    expect(tds[1].className).toContain('text-right')
    expect(container.querySelectorAll('th')[1].className).toContain('text-right')
  })
})

describe('DataTable — density & instrument class', () => {
  it('defaults ledger class to compact density', () => {
    const { container } = render(
      <DataTable class="ledger" columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} />
    )
    expect(container.querySelector('tbody td')?.className).toContain('py-2.5')
  })

  it('defaults registry class to comfortable density', () => {
    const { container } = render(
      <DataTable class="registry" columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} />
    )
    expect(container.querySelector('tbody td')?.className).toContain('py-3.5')
  })

  it('lets an explicit compact prop win over the class default', () => {
    const { container } = render(
      <DataTable
        class="registry"
        compact
        columns={legacyColumns}
        data={rows}
        keyExtractor={(r) => r.id}
      />
    )
    expect(container.querySelector('tbody td')?.className).toContain('py-2.5')
  })

  it('keeps legacy default density (comfortable) when no class is passed', () => {
    const { container } = render(
      <DataTable columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} />
    )
    expect(container.querySelector('tbody td')?.className).toContain('py-3.5')
  })
})

describe('DataTable — interactions', () => {
  it('fires onRowClick with the row item', async () => {
    const onRowClick = vi.fn()
    const user = userEvent.setup()
    render(<DataTable columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} onRowClick={onRowClick} />)
    await user.click(screen.getByText('Amina Kante'))
    expect(onRowClick).toHaveBeenCalledWith(rows[0])
  })

  it('applies sticky header classes by default', () => {
    const { container } = render(<DataTable columns={legacyColumns} data={rows} keyExtractor={(r) => r.id} />)
    expect(container.querySelector('thead tr')?.className).toContain('sticky')
  })
})

describe('DataTable — column width/minWidth', () => {
  it('applies width and minWidth as inline header styles', () => {
    const cols: Column<Row>[] = [
      { key: 'name', header: 'Student', width: 240, minWidth: 160 },
    ]
    const { container } = render(<DataTable columns={cols} data={rows} keyExtractor={(r) => r.id} />)
    const th = container.querySelector('th') as HTMLElement
    expect(th.style.width).toBe('240px')
    expect(th.style.minWidth).toBe('160px')
  })
})
