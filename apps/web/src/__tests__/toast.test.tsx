import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { ToastProvider, useToast } from '../components/ui/toast'

/**
 * Toast choreography (spec §6.9). The test environment resolves the `minimal`
 * motion tier, so `useMove` applies states instantly and the exit choreography
 * completes synchronously — these tests lock in the behavioral contract:
 * toasts appear on demand, dismiss through the exit choreography, and the
 * auto-dismiss timer removes them.
 */
function Trigger({ message = 'Saved', type = 'success' }: { message?: string; type?: 'success' | 'error' | 'info' | 'warning' }) {
  const { showToast } = useToast()
  return <button onClick={() => showToast(message, type)}>Show</button>
}

function renderProvider(ui: React.ReactNode) {
  return render(<ToastProvider>{ui}</ToastProvider>)
}

describe('ToastProvider choreography', () => {
  it('renders a toast when showToast is called', () => {
    renderProvider(<Trigger />)
    fireEvent.click(screen.getByText('Show'))
    expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('dismisses a toast through the exit choreography', async () => {
    renderProvider(<Trigger />)
    fireEvent.click(screen.getByText('Show'))
    expect(screen.getByText('Saved')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(screen.queryByText('Saved')).not.toBeInTheDocument())
  })

  it('auto-dismisses after the display window', () => {
    vi.useFakeTimers()
    try {
      renderProvider(<Trigger />)
      fireEvent.click(screen.getByText('Show'))
      expect(screen.getByText('Saved')).toBeInTheDocument()

      // Advance past the 4s display window: the timer fires removeWithAnim,
      // and the exit choreography (instant in the minimal tier) completes
      // inside the same act flush. waitFor is avoided here — RTL cannot
      // detect vitest's sinon-based fake timers, so its polling would hang.
      act(() => {
        vi.advanceTimersByTime(4000)
      })
      expect(screen.queryByText('Saved')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('stacks multiple toasts', () => {
    renderProvider(
      <>
        <Trigger message="One" />
        <Trigger message="Two" />
      </>
    )
    fireEvent.click(screen.getAllByText('Show')[0])
    fireEvent.click(screen.getAllByText('Show')[1])

    expect(screen.getByText('One')).toBeInTheDocument()
    expect(screen.getByText('Two')).toBeInTheDocument()
  })

  it('draws a checkmark on success toasts (Glint §3.1)', () => {
    renderProvider(<Trigger message="Saved" type="success" />)
    fireEvent.click(screen.getByText('Show'))

    const toast = screen.getByRole('alert')
    const check = toast.querySelector('svg path.animate-draw-check')
    expect(check).toBeInTheDocument()
    // The stroke draws from its full length to zero (drawn, not popped).
    expect(check!.getAttribute('stroke-dasharray')).toBe('24')
  })

  it('keeps the dot for non-success toasts', () => {
    renderProvider(<Trigger message="Failed" type="error" />)
    fireEvent.click(screen.getByText('Show'))

    const toast = screen.getByRole('alert')
    expect(toast.querySelector('svg path.animate-draw-check')).not.toBeInTheDocument()
  })
})
