import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { Drawer } from '../components/ui/drawer'

/** Precise-tier matchMedia stub (no reduced-motion, no reduced-transparency). */
function stubPreciseMotion() {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: false,
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

/**
 * Drawer choreography (spec §6.9: Slide E/W at `slow`). The test environment
 * resolves the `minimal` motion tier, so enter/exit complete synchronously —
 * these tests lock in the behavioral contract: the drawer mounts on open,
 * closes once through the exit choreography, and honors Escape.
 */
function Harness({ side = 'right' }: { side?: 'right' | 'left' }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open</button>
      <Drawer open={open} title="Test drawer" side={side} onClose={() => setOpen(false)}>
        <p>Drawer content</p>
      </Drawer>
    </>
  )
}

describe('Drawer choreography', () => {
  it('opens on demand and renders its content', () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('Open'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Drawer content')).toBeInTheDocument()
  })

  it('closes through the exit choreography on the close button', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('Open'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close drawer' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes on Escape', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('Open'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes on backdrop click', () => {
    render(<Harness side="left" />)
    fireEvent.click(screen.getByText('Open'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // The overlay (dialog wrapper) itself is the backdrop click target.
    fireEvent.click(screen.getByRole('dialog'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the panel in place when the parent re-renders while open (precise tier)', async () => {
    // Regression: unstabilized move specs used to re-run the enter effect on
    // every render, snapping the panel back to its off-canvas start frame.
    function ReRenderHarness() {
      const [open, setOpen] = useState(false)
      const [tick, setTick] = useState(0)
      return (
        <>
          <button onClick={() => setOpen(true)}>Open</button>
          <button onClick={() => setTick((t) => t + 1)}>Tick</button>
          <Drawer open={open} title="Test" onClose={() => setOpen(false)}>
            <p>Drawer content</p>
          </Drawer>
        </>
      )
    }

    stubPreciseMotion()
    try {
      render(<ReRenderHarness />)
      fireEvent.click(screen.getByText('Open'))

      // jsdom runs rAF on real timers — wait through the double-rAF enter
      // choreography so the panel settles at rest.
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 60))
      })
      const panel = () => screen.getByRole('dialog').querySelector<HTMLElement>('[tabindex="-1"]')
      expect(panel()!.style.transform).toBe('translateX(0)')

      // Parent re-render must NOT reset the panel to its off-canvas frame.
      fireEvent.click(screen.getByText('Tick'))
      expect(panel()!.style.transform).toBe('translateX(0)')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('calls onClose exactly once per close', () => {
    const onClose = vi.fn()
    function Controlled() {
      const [open, setOpen] = useState(true)
      return (
        <Drawer
          open={open}
          title="Controlled"
          onClose={() => {
            onClose()
            setOpen(false)
          }}
        >
          <p>Content</p>
        </Drawer>
      )
    }
    render(<Controlled />)
    fireEvent.click(screen.getByRole('button', { name: 'Close drawer' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
