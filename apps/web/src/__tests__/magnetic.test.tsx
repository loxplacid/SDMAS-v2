import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { MAGNET_MAX_PX } from '../lib/motion/magnetic'


/**
 * Magnetic hover-pull (Glint §2.1). The setup.ts matchMedia polyfill forces
 * reduced motion → tier `efficient`, which must make the pull inert; the
 * precise tier is stubbed here to verify the pull itself: a pointer inside
 * the control translates the content toward the cursor (clamped ±3px), and
 * leaving resets it. Transform is applied to the *content* wrapper, never
 * the button/card frame, so it can't fight their own hover CSS.
 */
function stubMotionPrefs(prefersReducedMotion: boolean, prefersReducedTransparency = false) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches:
          query === '(prefers-reduced-motion: reduce)'
            ? prefersReducedMotion
            : query === '(prefers-reduced-transparency: reduce)'
              ? prefersReducedTransparency
              : false,
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

/** Pointer event with client coords; jsdom rects are all zeros, so the
 *  element center is (0,0) and a +x/+y client lands to its south-east.
 *  jsdom has no global PointerEvent, so build a MouseEvent and stamp the
 *  pointerType the hook reads. */
function pointerEvent(type: string, x: number, y: number) {
  const event = new MouseEvent(type, {
    clientX: x,
    clientY: y,
    bubbles: true,
  })
  Object.defineProperty(event, 'pointerType', { value: 'mouse' })
  return event
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Button magnetic pull (Glint §2.1)', () => {
  it('pulls the content toward the cursor and resets on leave', () => {
    stubMotionPrefs(false, false) // precise tier
    render(<Button>Save</Button>)

    const button = screen.getByRole('button')
    const content = button.firstElementChild as HTMLElement

    fireEvent(content, pointerEvent('pointermove', 50, 30))
    // Clamped to the ±3px magnet radius; direction follows the cursor
    // (center at 0,0 → positive offset = south-east).
    expect(content.style.transform).toBe(`translate(${MAGNET_MAX_PX}px, ${MAGNET_MAX_PX}px)`)

    // Element-level pointerleave — the actual reset path (moving the cursor
    // off the button to anywhere else in the page).
    fireEvent(content, pointerEvent('pointerleave', 50, 30))
    expect(content.style.transform).toBe('none')
  })

  it('is inert under reduced motion (efficient tier)', () => {
    stubMotionPrefs(true, false) // efficient tier
    render(<Button>Save</Button>)

    const button = screen.getByRole('button')
    const content = button.firstElementChild as HTMLElement

    fireEvent(content, pointerEvent('pointermove', 50, 30))
    expect(content.style.transform).toBe('')
  })

  it('is disabled for non-primary variants by default', () => {
    stubMotionPrefs(false, false) // precise tier
    render(<Button variant="secondary">Cancel</Button>)

    const button = screen.getByRole('button')
    const content = button.firstElementChild as HTMLElement

    fireEvent(content, pointerEvent('pointermove', 50, 30))
    expect(content.style.transform).toBe('')
  })
})

describe('Card magnetic pull (Glint §2.1)', () => {
  it('pulls the content region on clickable cards in the precise tier', () => {
    stubMotionPrefs(false, false) // precise tier
    render(
      <Card title="Students" onClick={() => {}}>
        <p>Content</p>
      </Card>
    )

    const card = screen.getByText('Students').closest('.rounded-2xl') as HTMLElement
    // The magnetic wrapper is the first child of the card frame.
    const content = card.firstElementChild as HTMLElement

    fireEvent(content, pointerEvent('pointermove', 40, 40))
    expect(content.style.transform).toBe(`translate(${MAGNET_MAX_PX}px, ${MAGNET_MAX_PX}px)`)
  })

  it('lifts to d2 depth on clickable primary cards (Glint §2.2)', () => {
    stubMotionPrefs(false, false) // precise tier
    render(
      <Card title="Primary" onClick={() => {}} depth="d2">
        <p>Content</p>
      </Card>
    )

    const card = screen.getByText('Primary').closest('.rounded-2xl') as HTMLElement
    expect(card.className).toContain('hover:shadow-md')
    expect(card.className).toContain('hover:-translate-y-0.5')
  })

  it('defaults to the quiet d1 treatment for clickable cards', () => {
    stubMotionPrefs(false, false) // precise tier
    render(
      <Card title="Default" onClick={() => {}}>
        <p>Content</p>
      </Card>
    )

    const card = screen.getByText('Default').closest('.rounded-2xl') as HTMLElement
    expect(card.className).toContain('hover:shadow-sm')
    expect(card.className).toContain('hover:-translate-y-px')
  })

  it('keeps d1 depth (shadow-sm + 1px) for secondary clickable cards', () => {
    stubMotionPrefs(false, false) // precise tier
    render(
      <Card title="Secondary" onClick={() => {}}>
        <p>Content</p>
      </Card>
    )

    const card = screen.getByText('Secondary').closest('.rounded-2xl') as HTMLElement
    expect(card.className).toContain('hover:shadow-sm')
    expect(card.className).toContain('hover:-translate-y-px')
  })

  it('does not pull on non-clickable cards', () => {
    stubMotionPrefs(false, false) // precise tier
    render(
      <Card title="Static">
        <p>Content</p>
      </Card>
    )

    const title = screen.getByText('Static')
    const card = title.closest('.rounded-2xl') as HTMLElement
    const content = card.querySelector('span') as HTMLElement
    // `disabled={!onClick}` means no magnetic style is wired at all — no
    // transition, no willChange, no listeners to receive events.
    expect(content.style.transition).toBe('')
    expect(content.style.willChange).toBe('')
  })
})
