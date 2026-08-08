import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { BreadcrumbBar } from '../components/ui/breadcrumb-bar'

/**
 * BreadcrumbBar — the single breadcrumb surface for the shell. Both the app
 * header and pages render through it; the trail derives from the same
 * `getPageHierarchy` registry unless a page overrides it.
 */
function renderBar(
  path: string,
  props?: Partial<React.ComponentProps<typeof BreadcrumbBar>>
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <BreadcrumbBar {...props} />
    </MemoryRouter>
  )
}

describe('BreadcrumbBar — derived hierarchy (P8 §7)', () => {
  it('derives section + page from the route', () => {
    renderBar('/students')
    expect(screen.getByText('Records')).toBeInTheDocument()
    // The section crumb links to its prefix.
    expect(screen.getByRole('link', { name: 'Records' })).toHaveAttribute('href', '/students')
    // The page crumb is the current location.
    expect(screen.getByText('Students')).toHaveAttribute('aria-current', 'page')
  })

  it('overrides the page label for detail pages', () => {
    renderBar('/students/42', { pageLabel: 'Ada Lovelace' })
    expect(screen.getByText('Records')).toBeInTheDocument()
    expect(screen.getByText('Ada Lovelace')).toHaveAttribute('aria-current', 'page')
    // The generic derived label is replaced.
    expect(screen.queryByText('Students')).not.toBeInTheDocument()
  })

  it('renders a custom items trail exactly', () => {
    renderBar('/teachers/5', {
      items: [
        { label: 'Teachers', href: '/teachers' },
        { label: 'Ada Lovelace', href: '/teachers/5' },
        { label: '360 View' },
      ],
    })
    expect(screen.getByRole('link', { name: 'Teachers' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ada Lovelace' })).toHaveAttribute('href', '/teachers/5')
    expect(screen.getByText('360 View')).toHaveAttribute('aria-current', 'page')
  })

  it('appends extra crumbs after the derived trail', () => {
    renderBar('/academic/classes', { append: [{ label: 'Classes List' }] })
    expect(screen.getByText('Records')).toBeInTheDocument()
    expect(screen.getByText('Classes List')).toHaveAttribute('aria-current', 'page')
  })
})

describe('BreadcrumbBar — variants', () => {
  it('renders the compact header variant without page margins', () => {
    const { container } = renderBar('/fees', { variant: 'header' })
    const nav = container.querySelector('nav')
    expect(nav).not.toHaveClass('mb-4')
    expect(screen.getByText('Finance')).toBeInTheDocument()
  })

  it('renders the page variant with its margin by default', () => {
    const { container } = renderBar('/fees')
    expect(container.querySelector('nav')).toHaveClass('mb-4')
  })
})
