import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { flipDelta, flipElement, withFlip, useFlipList } from '../lib/motion/flip'
import { MOTION_DURATIONS, MOTION_EASINGS } from '../lib/motion/tokens'

function rect(left: number, top: number, width = 80, height = 40): DOMRect {
  return {
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
    toJSON: () => ({}),
  } as DOMRect
}

/** Force the precise tier (the test setup defaults to reduced-motion). */
function stubPreciseTier() {
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

/** jsdom rects are all zeros — stub getBoundingClientRect by data-order. */
function stubRectsByOrder(byOrder: (order: number) => DOMRect) {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    return byOrder(Number((this as HTMLElement).dataset.order ?? 0))
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('flipDelta (spec §9.2)', () => {
  it('computes the inverse translation for a rightward move', () => {
    expect(flipDelta(rect(0, 0), rect(60, 0))).toEqual({ dx: -60, dy: 0, sx: 1, sy: 1 })
  })

  it('computes the inverse scale for a shrink', () => {
    expect(flipDelta(rect(0, 0, 100, 50), rect(0, 0, 50, 25))).toEqual({ dx: 0, dy: 0, sx: 2, sy: 2 })
  })
})

describe('flipElement', () => {
  it('is a no-op when the element did not move', () => {
    const el = document.createElement('div')
    const onComplete = vi.fn()
    flipElement(el, rect(0, 0), rect(0, 0), { onComplete })
    expect(el.style.transition).toBe('')
    expect(onComplete).toHaveBeenCalledTimes(1)
  })

  it('applies the FLIP transform, transitions to identity, then cleans up', () => {
    vi.useFakeTimers()
    const el = document.createElement('div')
    flipElement(el, rect(0, 0), rect(60, 0))

    // After the forced reflow the element is at identity, mid-transition.
    expect(el.style.transformOrigin).toBe('0 0')
    expect(el.style.transform).toBe('none')
    expect(el.style.transition).toBe(
      `transform ${MOTION_DURATIONS.slow}ms ${MOTION_EASINGS.standard}`
    )

    // The completion timeout cleans up after the animation window.
    vi.advanceTimersByTime(MOTION_DURATIONS.slow + 150)
    expect(el.style.transition).toBe('')
  })

  it('restores the previous inline transition and transform-origin after completion', () => {
    vi.useFakeTimers()
    const el = document.createElement('div')
    el.style.transition = 'opacity 120ms linear'
    el.style.transformOrigin = 'center'

    flipElement(el, rect(0, 0), rect(60, 0))
    expect(el.style.transition).toContain(`transform ${MOTION_DURATIONS.slow}ms`)
    expect(el.style.transformOrigin).toBe('0 0')

    vi.advanceTimersByTime(MOTION_DURATIONS.slow + 150)

    // FLIP never stomps styles it doesn't own.
    expect(el.style.transition).toBe('opacity 120ms linear')
    expect(el.style.transformOrigin).toBe('center')
  })
})

describe('withFlip', () => {
  it('flips only [data-flip] children after a layout mutation', () => {
    stubRectsByOrder((order) => rect(order * 100, 0))

    const container = document.createElement('div')
    const a = document.createElement('div')
    const b = document.createElement('div')
    a.setAttribute('data-flip', '')
    b.setAttribute('data-flip', '')
    b.dataset.order = '2' // will move to slot 1 on mutation
    container.append(a, b)

    a.dataset.order = '0'
    withFlip(container, () => {
      b.dataset.order = '1'
    })

    // b moved from slot 2 (left 200) to slot 1 (left 100) → dx = +100.
    expect(b.style.transition).toContain('transform')
    // a stayed at slot 0 → untouched.
    expect(a.style.transition).toBe('')
  })
})

describe('useFlipList', () => {
  it('animates moved items and leaves static items alone (precise tier)', () => {
    stubPreciseTier()
    stubRectsByOrder((order) => rect(order * 100, 0))

    type Row = { id: string }
    function List({ items }: { items: readonly Row[] }) {
      const { containerRef, itemRef } = useFlipList(items, (r) => r.id)
      return (
        <div ref={containerRef}>
          {items.map((row, index) => (
            <div
              key={row.id}
              data-testid={`row-${row.id}`}
              data-order={index}
              ref={itemRef(row.id)}
              style={{ position: 'absolute' }}
            />
          ))}
        </div>
      )
    }

    const first = render(<List items={[{ id: 'a' }, { id: 'b' }, { id: 'c' }]} />)
    act(() => {
      first.rerender(<List items={[{ id: 'a' }, { id: 'c' }, { id: 'b' }]} />)
    })

    const a = screen.getByTestId('row-a') as HTMLElement // slot 0 → slot 0: static
    const c = screen.getByTestId('row-c') as HTMLElement // slot 2 → slot 1: moved
    const b = screen.getByTestId('row-b') as HTMLElement // slot 1 → slot 2: moved

    expect(a.style.transition).not.toContain('transform')
    expect(c.style.transition).toContain(`transform ${MOTION_DURATIONS.slow}ms`)
    expect(b.style.transition).toContain(`transform ${MOTION_DURATIONS.slow}ms`)
  })

  it('skips animation outside the precise tier', () => {
    // Default test tier = efficient (reduced motion): positions snap.
    stubRectsByOrder((order) => rect(order * 100, 0))

    type Row = { id: string }
    function List({ items }: { items: readonly Row[] }) {
      const { containerRef, itemRef } = useFlipList(items, (r) => r.id)
      return (
        <div ref={containerRef}>
          {items.map((row, index) => (
            <div key={row.id} data-testid={`row-${row.id}`} data-order={index} ref={itemRef(row.id)} />
          ))}
        </div>
      )
    }

    const first = render(<List items={[{ id: 'a' }, { id: 'b' }, { id: 'c' }]} />)
    act(() => {
      first.rerender(<List items={[{ id: 'b' }, { id: 'c' }, { id: 'a' }]} />)
    })

    expect((screen.getByTestId('row-b') as HTMLElement).style.transition).toBe('')
  })
})
