import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from '../components/layout/sidebar'

/**
 * P8 — premium navigation. `motion/react` is mocked to a plain div that
 * records `layoutId`, so the shared-layout active indicator contract is
 * asserted without Motion's internal projection machinery (jsdom has no
 * layout to measure). The auth/campus hooks are stubbed; the default test
 * tier (minimal) makes the sidebar's own choreography instant.
 */
const authMock = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
}))

vi.mock('motion/react', async () => {
  const { createElement, Fragment } = await import('react')
  const MockMotion = (props: Record<string, any>) => {
    const { layoutId, children, ...rest } = props
    const meta = layoutId ? JSON.stringify({ layoutId }) : ''
    return createElement('div', { 'data-motion-meta': meta, ...rest }, children)
  }
  return {
    motion: new Proxy({}, { get: () => MockMotion }),
    MotionConfig: ({ children }: Record<string, any>) => createElement(Fragment, null, children),
    AnimatePresence: ({ children }: Record<string, any>) => createElement(Fragment, null, children),
    useReducedMotion: () => true,
  }
})

vi.mock('../api/auth/auth-context', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({ user: authMock.user, logout: vi.fn() }),
}))

vi.mock('../hooks/use-campus', () => ({
  useCampus: () => ({ campusName: 'Test Campus', isLoading: false }),
}))

beforeEach(() => {
  authMock.user = {
    id: 1,
    role: 'admin',
    roles: ['admin'],
    display_name: 'Ada Admin',
    username: 'ada',
    email: 'ada@school.edu',
    campus_id: 1,
  }
})

function renderSidebar(initialEntries: string[] = ['/dashboard'], collapsed?: boolean) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Sidebar collapsed={collapsed} />
    </MemoryRouter>
  )
}

function indicatorIn(link: HTMLElement): HTMLElement | null {
  return link.querySelector('[data-sidebar-indicator]')
}

describe('Sidebar — role navigation (P8 §3)', () => {
  it('renders the nav sections for the user role', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: 'Students' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Attendance' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Command Center' })).toBeInTheDocument()
  })

  it('shows the user identity in the expanded rail', () => {
    renderSidebar(['/dashboard'], false)
    expect(screen.getByText('Ada Admin')).toBeInTheDocument()
    expect(screen.getByText('Test Campus')).toBeInTheDocument()
  })
})

describe('Sidebar — traveling active indicator (P8 §4, §12)', () => {
  it('renders the shared-layout indicator on the current route', () => {
    renderSidebar(['/students'])
    const students = screen.getByRole('link', { name: 'Students' })
    expect(students).toHaveAttribute('aria-current', 'page')
    expect(indicatorIn(students)).not.toBeNull()
    // The indicator carries the shared layout identity (one id for the whole rail).
    expect(indicatorIn(students)!.getAttribute('data-motion-meta')).toContain('sidebar-active-indicator')
  })

  it('moves the indicator when navigating to another route', () => {
    renderSidebar(['/students'])

    const students = screen.getByRole('link', { name: 'Students' })
    expect(indicatorIn(students)).not.toBeNull()

    fireEvent.click(screen.getByRole('link', { name: 'Attendance' }))

    const attendance = screen.getByRole('link', { name: 'Attendance' })
    expect(attendance).toHaveAttribute('aria-current', 'page')
    expect(indicatorIn(attendance)).not.toBeNull()
    expect(indicatorIn(students)).toBeNull()
  })

  it('keeps exactly one indicator in the rail at any time', () => {
    renderSidebar(['/students'])
    const links = screen.getAllByRole('link')
    const count = links.filter((link) => indicatorIn(link) !== null).length
    expect(count).toBe(1)
  })

  it('shows the indicator in the collapsed rail too', () => {
    renderSidebar(['/attendance'], true)
    const attendance = screen.getByRole('link', { name: 'Attendance' })
    expect(indicatorIn(attendance)).not.toBeNull()
  })
})

describe('Sidebar — collapsed rail (P8 §3)', () => {
  it('hides labels in collapsed mode', () => {
    renderSidebar(['/dashboard'], true)
    // Labels are unmounted (aria-label on the link remains for a11y).
    expect(screen.queryByText('Students')).not.toBeInTheDocument()
  })

  it('offers tooltips for icon-only items in the collapsed rail', async () => {
    renderSidebar(['/dashboard'], true)

    const students = screen.getByRole('link', { name: 'Students' })
    const icon = students.querySelector('svg')
    fireEvent.mouseEnter(icon!)

    await waitFor(
      () => expect(screen.getByRole('tooltip')).toHaveTextContent('Students'),
      { timeout: 1500 }
    )
  })

  it('gives nav items an immediate press response (P7 §3.3)', () => {
    renderSidebar(['/dashboard'], false)
    const link = screen.getByRole('link', { name: 'Students' })
    // Tactile press on the fast clock, gated by motion-safe.
    expect(link.className).toContain('motion-safe:active:scale-[0.98]')
  })

  it('keeps a persisted collapse reversible from the rail itself (P8 §6)', () => {
    const onToggle = vi.fn()
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Sidebar collapsed onToggle={onToggle} />
      </MemoryRouter>
    )

    const expand = screen.getByRole('button', { name: 'Expand sidebar' })
    fireEvent.click(expand)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('labels the collapsed expand control with a tooltip', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Sidebar collapsed onToggle={vi.fn()} />
      </MemoryRouter>
    )

    const expand = screen.getByRole('button', { name: 'Expand sidebar' })
    fireEvent.mouseEnter(expand)

    await waitFor(
      () => expect(screen.getByRole('tooltip')).toHaveTextContent('Expand sidebar'),
      { timeout: 1500 }
    )
  })
})
