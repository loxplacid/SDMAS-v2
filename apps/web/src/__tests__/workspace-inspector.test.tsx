import { useState } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { WorkspaceInspector } from '../components/data-workspace'

/**
 * P9 — WorkspaceInspector primitive tests.
 *
 * The default setup.ts matchMedia polyfill reports `matches: true` for every
 * query → reduced-motion + reduced-transparency → the `minimal` motion tier
 * (instant, no spatial slide). Tests that need the real choreography (the
 * mobile sheet) stub matchMedia explicitly.
 */

function stubMatchMedia(queries: Record<string, boolean>) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: queries[query] ?? false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.style.overflow = ''
})

const base = {
  onClose: vi.fn(),
  title: 'Student preview',
  children: <p>Inspector body</p>,
}

describe('WorkspaceInspector — desktop side panel', () => {
  it('renders nothing when closed', () => {
    render(<WorkspaceInspector {...base} open={false} />)
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
    expect(screen.queryByText('Inspector body')).not.toBeInTheDocument()
  })

  it('renders header, body, footer and close button when open', () => {
    render(
      <WorkspaceInspector
        {...base}
        open
        header={<h2>Rahul Sharma</h2>}
        footer={<button type="button">Open 360</button>}
      />
    )
    const panel = screen.getByRole('complementary')
    expect(panel).toHaveAttribute('aria-label', 'Student preview')
    expect(screen.getByText('Rahul Sharma')).toBeInTheDocument()
    expect(screen.getByText('Inspector body')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open 360' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close inspector' })).toBeInTheDocument()
  })

  it('is not an ordinary modal on desktop — no backdrop, no scroll lock', () => {
    render(<WorkspaceInspector {...base} open />)
    expect(document.querySelector('[data-workspace-inspector-backdrop]')).not.toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')
  })

  it('shows the loading skeleton and hides content while loading', () => {
    render(<WorkspaceInspector {...base} open loading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText('Inspector body')).not.toBeInTheDocument()
  })

  it('shows an actionable error state with retry', () => {
    const onRetry = vi.fn()
    render(<WorkspaceInspector {...base} open error="Unable to load student" onRetry={onRetry} />)
    expect(screen.getByText('Unable to load student')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Try Again/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows the empty message when open with no content', () => {
    render(
      <WorkspaceInspector
        open
        onClose={vi.fn()}
        title="Preview"
        emptyMessage="Select a student to preview their record."
      />
    )
    expect(screen.getByText('Select a student to preview their record.')).toBeInTheDocument()
  })

  it('closes on Escape', () => {
    render(<WorkspaceInspector {...base} open />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(base.onClose).toHaveBeenCalledTimes(1)
  })

  it('respects reduced motion — panel is at rest with no transition', () => {
    // setup.ts polyfill → minimal tier → no spatial slide is ever scheduled.
    render(<WorkspaceInspector {...base} open />)
    const panel = screen.getByRole('complementary')
    expect(panel.style.transition).toBe('none')
    expect(panel.style.transform).toBe('translateX(0)')
  })

  it('closes via the close button', () => {
    render(<WorkspaceInspector {...base} open />)
    fireEvent.click(screen.getByRole('button', { name: 'Close inspector' }))
    expect(base.onClose).toHaveBeenCalledTimes(1)
  })
})

describe('WorkspaceInspector — mobile sheet', () => {
  it('renders as a full-screen dialog with backdrop and locks body scroll', () => {
    stubMatchMedia({
      '(min-width: 1024px)': false,
      '(prefers-reduced-motion: reduce)': false,
      '(prefers-reduced-transparency: reduce)': false,
    })
    render(<WorkspaceInspector {...base} open />)
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    expect(document.querySelector('[data-workspace-inspector-backdrop]')).toBeInTheDocument()
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('Escape closes the sheet and restores body scroll', async () => {
    stubMatchMedia({
      '(min-width: 1024px)': false,
      '(prefers-reduced-motion: reduce)': false,
      '(prefers-reduced-transparency: reduce)': false,
    })
    // A controlled parent: `onClose` flips `open` off, which is what the URL
    // router does in the real workspace (cleanup then restores the scroll).
    const onClose = vi.fn()
    function Controlled() {
      const [open, setOpen] = useState(true)
      return (
        <WorkspaceInspector
          {...base}
          open={open}
          onClose={() => {
            onClose()
            setOpen(false)
          }}
        />
      )
    }
    render(<Controlled />)
    expect(document.body.style.overflow).toBe('hidden')
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(document.body.style.overflow).toBe(''))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
