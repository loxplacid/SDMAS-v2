import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CommandPalette } from '../components/ui/command-palette'

/**
 * CommandPalette choreography (spec §6.10 / §11.3).
 *
 * The test environment resolves the `minimal` motion tier (matchMedia stub
 * matches every query), so `useMove` applies states instantly and closes are
 * synchronous — these tests lock in the *behavioral* contract: the palette
 * mounts when open, closes exactly once per Escape, and runs the selected
 * action before closing.
 */
const groups = [
  {
    label: 'Pages',
    items: [
      { id: 'alpha', label: 'Alpha', description: 'First page', action: vi.fn() },
      { id: 'beta', label: 'Beta', action: vi.fn() },
    ],
  },
]

describe('CommandPalette choreography', () => {
  it('renders the dialog with its results when open', () => {
    render(
      <MemoryRouter>
        <CommandPalette open groups={groups} onClose={vi.fn()} />
      </MemoryRouter>
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
  })

  it('renders nothing when closed', () => {
    render(
      <MemoryRouter>
        <CommandPalette open={false} groups={groups} onClose={vi.fn()} />
      </MemoryRouter>
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes through the exit choreography on Escape', () => {
    const onClose = vi.fn()
    render(
      <MemoryRouter>
        <CommandPalette open groups={groups} onClose={onClose} />
      </MemoryRouter>
    )
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('runs the selected action then closes on Enter', () => {
    const action = vi.fn()
    const onClose = vi.fn()
    render(
      <MemoryRouter>
        <CommandPalette
          open
          groups={[{ label: 'Pages', items: [{ id: 'alpha', label: 'Alpha', action }] }]}
          onClose={onClose}
        />
      </MemoryRouter>
    )
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    expect(action).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('selects and activates a result via mouse', () => {
    const action = vi.fn()
    const onClose = vi.fn()
    render(
      <MemoryRouter>
        <CommandPalette
          open
          groups={[{ label: 'Pages', items: [{ id: 'alpha', label: 'Alpha', action }] }]}
          onClose={onClose}
        />
      </MemoryRouter>
    )
    fireEvent.click(screen.getByText('Alpha'))
    expect(action).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('filters results as the query changes', () => {
    render(
      <MemoryRouter>
        <CommandPalette open groups={groups} onClose={vi.fn()} />
      </MemoryRouter>
    )
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'beta' } })
    expect(screen.queryByText('Alpha')).not.toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
  })
})
