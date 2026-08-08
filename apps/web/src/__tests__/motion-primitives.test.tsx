import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionReveal } from '../lib/motion/reveal'
import { MotionPresence } from '../lib/motion/presence'
import { MotionLayout } from '../lib/motion/layout'
import { SharedElement } from '../lib/motion/shared-element'
import { MotionProvider } from '../lib/motion/motion-config'
import { useReduceMotion } from '../lib/motion/reduced-motion'
import { MOTION_DURATIONS, resolveMove } from '../lib/motion/tokens'

/**
 * P7 — focused tests for the new Motion primitives.
 *
 * `motion/react` is mocked to a plain div that records the `initial` /
 * `animate` / `exit` / `transition` / `layout` / `layoutId` props it
 * receives, so we assert the *token policy* each primitive resolves — not
 * Motion's own internals. The tier is stubbed via matchMedia, exactly like
 * use-move.test.tsx / magnetic.test.tsx.
 */

const motionMocks = vi.hoisted(() => ({
  configProps: null as Record<string, unknown> | null,
  presenceProps: [] as Array<Record<string, unknown>>,
}))

vi.mock('motion/react', async () => {
  const { createElement, Fragment, forwardRef } = await import('react')

  const MockMotion = forwardRef(function MockMotion(props: Record<string, any>, ref: unknown) {
    const {
      initial,
      animate,
      exit,
      transition,
      layout,
      layoutId,
      children,
      ...rest
    } = props
    const meta = JSON.stringify({ initial, animate, exit, transition, layout, layoutId })
    return createElement('div', { ref, 'data-motion-meta': meta, ...rest }, children)
  })

  const MockMotionConfig = (props: Record<string, any>) => {
    motionMocks.configProps = props
    return createElement(Fragment, null, props.children)
  }

  const MockAnimatePresence = (props: Record<string, any>) => {
    motionMocks.presenceProps.push(props)
    return createElement(Fragment, null, props.children)
  }

  return {
    motion: new Proxy({}, { get: () => MockMotion }),
    MotionConfig: MockMotionConfig,
    AnimatePresence: MockAnimatePresence,
    useReducedMotion: () => false,
  }
})

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

afterEach(() => {
  vi.unstubAllGlobals()
  motionMocks.configProps = null
  motionMocks.presenceProps = []
})

function readMeta(el: Element): Record<string, unknown> {
  return JSON.parse(el.getAttribute('data-motion-meta') ?? '{}') as Record<string, unknown>
}

function metaTransition(el: Element): Record<string, any> {
  return readMeta(el).transition as Record<string, any>
}

describe('MotionReveal (P7 — entrance primitive)', () => {
  it('resolves a pure fade with no spatial shift in the precise tier', () => {
    stubMotionPrefs(false, false)
    const { container } = render(<MotionReveal>Hello</MotionReveal>)

    expect(screen.getByText('Hello')).toBeInTheDocument()
    const meta = readMeta(container.firstElementChild as Element)
    const expected = resolveMove({ verb: 'fade' }, 'precise')

    expect(meta.initial).toMatchObject({ opacity: 0 })
    expect((meta.initial as Record<string, unknown>).x).toBeUndefined()
    expect((meta.initial as Record<string, unknown>).y).toBeUndefined()
    expect(meta.animate).toEqual({ opacity: 1 })
    // Enter rides the token clock (fade D2 I2 → 150ms).
    expect(metaTransition(container.firstElementChild as Element).animate.duration).toBeCloseTo(
      expected.duration / 1000,
      5
    )
  })

  it('applies a directional slide with distance-class travel', () => {
    stubMotionPrefs(false, false)
    const { container } = render(
      <MotionReveal spec={{ verb: 'slide', direction: 'E', distance: 'D2' }}>S</MotionReveal>
    )

    const initial = readMeta(container.firstElementChild as Element).initial as Record<string, number>
    // D2 → 4px travel, E → +x, no y.
    expect(initial.x).toBe(4)
    expect(initial.y).toBe(0)
  })

  it('drops spatial travel and caps to 75ms under the efficient tier', () => {
    stubMotionPrefs(true, false) // reduced-motion → efficient
    const { container } = render(
      <MotionReveal spec={{ verb: 'slide', direction: 'E', distance: 'D3' }}>S</MotionReveal>
    )

    const meta = readMeta(container.firstElementChild as Element)
    expect((meta.initial as Record<string, unknown>).x).toBeUndefined()
    expect((meta.initial as Record<string, unknown>).y).toBeUndefined()
    expect(metaTransition(container.firstElementChild as Element).animate.duration).toBeLessThanOrEqual(
      0.075
    )
  })

  it('resolves to an instant duration under the minimal tier', () => {
    stubMotionPrefs(true, true) // reduced-motion + reduced-transparency → minimal
    const { container } = render(<MotionReveal>M</MotionReveal>)

    expect(metaTransition(container.firstElementChild as Element).animate.duration).toBe(0)
  })

  it('applies the 20ms stagger quantum from a sibling index', () => {
    stubMotionPrefs(false, false)
    const { container } = render(<MotionReveal staggerIndex={2}>S</MotionReveal>)

    // 2 × 20ms quantum, capped at 150ms (§4.3).
    expect(metaTransition(container.firstElementChild as Element).animate.delay).toBeCloseTo(0.04, 5)
  })

  it('honors the token exit clock (0.7× enter)', () => {
    stubMotionPrefs(false, false)
    const { container } = render(<MotionReveal>E</MotionReveal>)

    const expected = resolveMove({ verb: 'fade' }, 'precise')
    expect(metaTransition(container.firstElementChild as Element).exit.duration).toBeCloseTo(
      expected.exitDuration / 1000,
      5
    )
  })
})

describe('MotionPresence (P7 — AnimatePresence wrapper)', () => {
  it('renders children and defaults to wait mode', () => {
    render(
      <MotionPresence>
        <div>A</div>
      </MotionPresence>
    )

    expect(screen.getByText('A')).toBeInTheDocument()
    const last = motionMocks.presenceProps[motionMocks.presenceProps.length - 1]
    expect(last?.mode).toBe('wait')
  })

  it('forwards an explicit mode', () => {
    render(
      <MotionPresence mode="popLayout">
        <div>B</div>
      </MotionPresence>
    )

    const last = motionMocks.presenceProps[motionMocks.presenceProps.length - 1]
    expect(last?.mode).toBe('popLayout')
  })
})

describe('MotionLayout (P7 — layout-animation primitive)', () => {
  it('enables layout animation on the token slow clock', () => {
    const { container } = render(
      <MotionLayout className="row">
        <p>C</p>
      </MotionLayout>
    )

    const el = container.firstElementChild as Element
    expect(el.className).toContain('row')
    const meta = readMeta(el)
    expect(meta.layout).toBe(true)
    expect(metaTransition(el).duration).toBeCloseTo(MOTION_DURATIONS.slow / 1000, 5)
  })
})

describe('SharedElement (P7 — layoutId abstraction)', () => {
  it('binds a layoutId for cross-mount FLIP', () => {
    const { container } = render(
      <SharedElement layoutId="student-card-42">
        <p>C</p>
      </SharedElement>
    )

    const el = container.firstElementChild as Element
    const meta = readMeta(el)
    expect(meta.layoutId).toBe('student-card-42')
    expect(metaTransition(el).duration).toBeCloseTo(MOTION_DURATIONS.slow / 1000, 5)
  })
})

describe('MotionProvider (P7 — single shared configuration)', () => {
  it('configures Motion with the token default transition and user reduced-motion', () => {
    render(
      <MotionProvider>
        <div>inside</div>
      </MotionProvider>
    )

    expect(screen.getByText('inside')).toBeInTheDocument()
    expect(motionMocks.configProps?.reducedMotion).toBe('user')
    expect((motionMocks.configProps?.transition as { duration?: number }).duration).toBeCloseTo(
      MOTION_DURATIONS.base / 1000,
      5
    )
  })
})

function TierProbe() {
  const reduced = useReduceMotion()
  return <span>{reduced ? 'reduced' : 'precise'}</span>
}

describe('useReduceMotion (P7 — reduced-motion bridge)', () => {
  it('reports the precise tier as not-reduced', () => {
    stubMotionPrefs(false, false)
    render(<TierProbe />)
    expect(screen.getByText('precise')).toBeInTheDocument()
  })

  it('reports the efficient tier as reduced', () => {
    stubMotionPrefs(true, false)
    render(<TierProbe />)
    expect(screen.getByText('reduced')).toBeInTheDocument()
  })

  it('reports the minimal tier as reduced', () => {
    stubMotionPrefs(true, true)
    render(<TierProbe />)
    expect(screen.getByText('reduced')).toBeInTheDocument()
  })
})
