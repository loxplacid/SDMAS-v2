import { describe, it, expect } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { AnimatedCount } from '../components/ui/animated-count'

/**
 * Counter choreography (Glint §3.3): the roll ends with a one-shot settle
 * pulse on the numeral — and the settle must NOT play on the initial mount
 * (only when a value actually changes). We assert the *contract*: the
 * aria-label always carries the target value, and the settle animation
 * class appears only after a value update, never on first paint.
 */
describe('AnimatedCount', () => {
  it('renders the target value in the accessible label', () => {
    render(<AnimatedCount value={42} />)
    expect(screen.getByLabelText('42')).toBeInTheDocument()
  })

  it('does not settle-pulse on the initial mount', () => {
    render(<AnimatedCount value={10} />)
    const wrapper = screen.getByLabelText('10').firstElementChild as HTMLElement | null
    expect(wrapper).toBeTruthy()
    // settleKey starts at 0 — the settle animation class must be absent.
    expect(wrapper!.className).not.toContain('animate-counter-settle')
  })

  it('settle-pulses when the value changes', () => {
    const { rerender } = render(<AnimatedCount value={10} />)
    rerender(<AnimatedCount value={20} />)
    // After a value update the settle wrapper is re-keyed and carries the
    // settle animation class.
    expect(screen.getByLabelText('20')).toBeInTheDocument()
    const wrapper = screen.getByLabelText('20').firstElementChild as HTMLElement | null
    expect(wrapper).toBeTruthy()
    expect(wrapper!.className).toContain('animate-counter-settle')
  })
})
