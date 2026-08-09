import { describe, it, expect, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import { useWorkspaceSelection } from '../components/data-workspace'
import { DataTable, type Column } from '../components/ui/table'

/**
 * P9 — workspace selection: URL sync (deep link, refresh restore, back /
 * forward) + the DataTable's current-row highlight and keyboard follow.
 */

let currentSearch = ''
let nav!: (delta: number) => void

function UrlProbe() {
  currentSearch = useLocation().search
  return null
}
function NavProbe() {
  nav = useNavigate()
  return null
}

function Harness() {
  const sel = useWorkspaceSelection('student')
  return (
    <div>
      <button type="button" onClick={() => sel.open(7)}>open-7</button>
      <button type="button" onClick={() => sel.open('9')}>open-9</button>
      <button type="button" onClick={sel.close}>close</button>
      <output data-testid="selected">{sel.selectedId ?? 'none'}</output>
    </div>
  )
}

function setup(entry = '/students') {
  currentSearch = ''
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <UrlProbe />
      <NavProbe />
      <Routes>
        <Route path="/students" element={<Harness />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('useWorkspaceSelection — URL-synced selection', () => {
  it('initializes from the URL (refresh preserves the selection)', () => {
    setup('/students?student=42')
    expect(screen.getByTestId('selected').textContent).toBe('42')
  })

  it('rejects a non-numeric param as no selection', () => {
    setup('/students?student=abc')
    expect(screen.getByTestId('selected').textContent).toBe('none')
  })

  it('open pushes the param onto the URL', () => {
    setup('/students')
    fireEvent.click(screen.getByText('open-7'))
    expect(screen.getByTestId('selected').textContent).toBe('7')
    expect(currentSearch).toContain('student=7')
  })

  it('close removes the param and clears the selection', () => {
    setup('/students?student=7')
    fireEvent.click(screen.getByText('close'))
    expect(screen.getByTestId('selected').textContent).toBe('none')
    expect(currentSearch).not.toContain('student=')
  })

  it('browser back walks through selections then to the plain list, forward restores', () => {
    setup('/students')
    fireEvent.click(screen.getByText('open-7'))
    fireEvent.click(screen.getByText('open-9'))
    expect(screen.getByTestId('selected').textContent).toBe('9')

    act(() => nav(-1))
    expect(screen.getByTestId('selected').textContent).toBe('7')

    act(() => nav(-1))
    expect(screen.getByTestId('selected').textContent).toBe('none')

    act(() => nav(1))
    expect(screen.getByTestId('selected').textContent).toBe('7')
  })

  it('re-opening the same row does not stack a redundant history entry', () => {
    setup('/students')
    fireEvent.click(screen.getByText('open-7'))
    fireEvent.click(screen.getByText('open-7'))
    // One push only: a single back step returns straight to the plain list.
    act(() => nav(-1))
    expect(screen.getByTestId('selected').textContent).toBe('none')
  })
})

// ── DataTable current-row highlight + keyboard follow ─────────────────

const cols: Column<{ id: number; name: string }>[] = [
  { key: 'name', header: 'Name', type: 'text' },
]
const items = [
  { id: 1, name: 'Alpha' },
  { id: 2, name: 'Beta' },
]

describe('DataTable — current row (P9)', () => {
  it('marks and highlights the current row via aria-current', () => {
    render(
      <DataTable
        columns={cols}
        data={items}
        keyExtractor={(r) => r.id}
        currentKey={1}
        keyboardNav
      />
    )
    const current = document.querySelector('tr[aria-current="true"]')
    expect(current).not.toBeNull()
    expect(current!.textContent).toContain('Alpha')
    expect(current!.className).toContain('bg-[var(--color-brand-accent-subtle)]')
  })

  it('renders no current row when currentKey is absent', () => {
    render(
      <DataTable columns={cols} data={items} keyExtractor={(r) => r.id} keyboardNav />
    )
    expect(document.querySelector('tr[aria-current="true"]')).toBeNull()
  })

  it('reports the row the keyboard navigation lands on', () => {
    const onActiveRowChange = vi.fn()
    render(
      <DataTable
        columns={cols}
        data={items}
        keyExtractor={(r) => r.id}
        keyboardNav
        onActiveRowChange={onActiveRowChange}
      />
    )
    const row1 = screen.getByText('Alpha').closest('tr')!
    fireEvent.keyDown(row1, { key: 'ArrowDown' })
    expect(onActiveRowChange).toHaveBeenCalledWith({ id: 2, name: 'Beta' })
  })

  it('Enter activates the focused row (row click)', () => {
    const onRowClick = vi.fn()
    render(
      <DataTable
        columns={cols}
        data={items}
        keyExtractor={(r) => r.id}
        keyboardNav
        onRowClick={onRowClick}
      />
    )
    const row1 = screen.getByText('Alpha').closest('tr')!
    fireEvent.keyDown(row1, { key: 'Enter' })
    expect(onRowClick).toHaveBeenCalledWith({ id: 1, name: 'Alpha' })
  })
})
