import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import { MOTION_EASINGS, type MoveSpec } from '../lib/motion/tokens'
import { useMove, type UseMoveResult } from '../lib/motion/use-move'
import { useMotionTier } from '../lib/motion/use-motion-tier'

/**
 * Control the motion tier precisely. The setup.ts matchMedia polyfill
 * reports `matches: true` for every query, which would make the default
 * tier *minimal* (reduced-motion + reduced-transparency) — explicit stubs
 * avoid depending on that.
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

/**
 * jsdom has no Element.animate — stub it to record the keyframes/options
 * and return a playable Animation-like object so we can drive onfinish.
 */
const animateMock = vi.fn(function (
  this: HTMLElement,
  keyframes: Keyframe[],
  options?: KeyframeAnimationOptions
) {
  return {
    onfinish: null,
    finished: Promise.resolve(),
    cancel: () => {},
    play: () => {},
    pause: () => {},
  } as unknown as Animation
})

beforeEach(() => {
  ;(HTMLElement.prototype as unknown as { animate: typeof animateMock }).animate = animateMock
  animateMock.mockClear()
})

afterEach(async () => {
  // Deleting the attribute is itself a mutation the (still-mounted) tier
  // observer reacts to — do it inside act so the resulting update isn't
  // flagged. (Vitest runs this afterEach before testing-library's unmount
  // cleanup, which registers earlier and therefore runs later.)
  await act(async () => {
    delete document.documentElement.dataset.motionTier
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
  vi.unstubAllGlobals()
})

let captured: UseMoveResult | null = null

function Probe({ spec, options }: { spec: MoveSpec; options?: { animateOnMount?: boolean; staggerIndex?: number } }) {
  const move = useMove(spec, options)
  captured = move
  return <div data-testid="probe" ref={move.ref} style={move.style} />
}

function TierProbe() {
  const tier = useMotionTier()
  return <div data-testid="tier">{tier}</div>
}

describe('useMove — mount enter (spec §3.3)', () => {
  it('renders the start frame, then settles into the rest frame', async () => {
    stubMotionPrefs(true, false) // reduced-motion only → efficient tier
    render(<Probe spec={{ verb: 'slide', direction: 'E', distance: 'D3' }} options={{ animateOnMount: true }} />)
    const el = screen.getByTestId('probe') as HTMLElement

    // Efficient tier is active in tests (setup polyfill reports reduced
    // motion) → fade-only: start frame is opacity 0, no transform.
    expect(el.style.opacity).toBe('0')
    expect(el.style.transform).toBe('none')

    await waitFor(() => expect(el.style.opacity).toBe('1'))
    expect(el.style.transition).toContain('75ms')
  })

  it('without animateOnMount the element renders at rest', () => {
    render(<Probe spec={{ verb: 'slide', direction: 'E', distance: 'D3' }} />)
    const el = screen.getByTestId('probe') as HTMLElement
    expect(el.style.opacity).toBe('1')
  })
})

describe('useMove — imperative play (spec §2.4, §4.1)', () => {
  it('plays an enter with resolved keyframes and fires onfinish', () => {
    stubMotionPrefs(false, false) // precise tier
    render(<Probe spec={{ verb: 'slide', direction: 'E', distance: 'D3' }} />)
    const el = screen.getByTestId('probe') as HTMLElement
    const onfinish = vi.fn()

    act(() => captured!.play(el, 'enter', { onfinish }))

    expect(animateMock).toHaveBeenCalledTimes(1)
    const [keyframes, options] = animateMock.mock.calls[0] as [Keyframe[], KeyframeAnimationOptions]
    expect(keyframes[0]).toMatchObject({ opacity: 0, transform: 'translate(16px, 0px)' })
    expect(keyframes[1]).toMatchObject({ opacity: 1, transform: 'none' })
    expect(options.duration).toBe(220) // D3 · I2
    expect(options.easing).toBe(MOTION_EASINGS.enter)

    const animation = animateMock.mock.results[0].value as Animation
    act(() => animation.onfinish?.(new Event('finish') as AnimationPlaybackEvent))
    expect(onfinish).toHaveBeenCalledTimes(1)
  })

  it('exits with the reversed transform and exit easing', () => {
    stubMotionPrefs(false, false) // precise tier
    render(<Probe spec={{ verb: 'slide', direction: 'E', distance: 'D3' }} />)
    const el = screen.getByTestId('probe') as HTMLElement

    act(() => captured!.play(el, 'exit'))

    const [keyframes, options] = animateMock.mock.calls[0] as [Keyframe[], KeyframeAnimationOptions]
    expect(keyframes[0]).toMatchObject({ opacity: 1, transform: 'none' })
    expect(keyframes[1]).toMatchObject({ opacity: 0, transform: 'translate(-16px, 0px)' })
    expect(options.easing).toBe(MOTION_EASINGS.exit)
    expect(options.duration).toBe(captured!.move.exitDuration)
  })

  it('applies the minimal tier instantly without calling WAAPI', () => {
    stubMotionPrefs(true, true) // reduced-motion + reduced-transparency → minimal
    render(<Probe spec={{ verb: 'slide', direction: 'E', distance: 'D3' }} />)
    const el = screen.getByTestId('probe') as HTMLElement
    const onfinish = vi.fn()

    act(() => captured!.play(el, 'exit', { onfinish }))

    expect(animateMock).not.toHaveBeenCalled()
    expect(el.style.transition).toBe('none')
    expect(el.style.opacity).toBe('0')
    expect(onfinish).toHaveBeenCalledTimes(1)
  })
})

describe('useMove — pulse (spec §7)', () => {
  it('is legal in the precise tier: one 300ms scale bounce', () => {
    stubMotionPrefs(false, false) // precise tier
    render(<Probe spec={{ verb: 'pulse' }} />)
    const el = screen.getByTestId('probe') as HTMLElement

    act(() => captured!.pulse(el))

    expect(animateMock).toHaveBeenCalledTimes(1)
    const [keyframes, options] = animateMock.mock.calls[0] as [Keyframe[], KeyframeAnimationOptions]
    expect(keyframes).toHaveLength(3)
    expect(options.duration).toBe(300)
    expect(options.easing).toBe(MOTION_EASINGS.spring)
  })

  it('is suppressed in the efficient tier', () => {
    stubMotionPrefs(true, false) // efficient tier
    render(<Probe spec={{ verb: 'pulse' }} />)
    const el = screen.getByTestId('probe') as HTMLElement

    act(() => captured!.pulse(el))

    expect(animateMock).not.toHaveBeenCalled()
  })
})

describe('useMotionTier — reactivity (spec §8)', () => {
  it('re-renders when the data-motion-tier attribute changes', async () => {
    stubMotionPrefs(true, false) // efficient tier
    render(<TierProbe />)
    expect(screen.getByTestId('tier').textContent).toBe('efficient')

    // jsdom delivers MutationObserver callbacks on a macrotask, so the
    // attribute mutation needs a timer flush *inside* act for the tier
    // update to land within the act scope.
    await act(async () => {
      document.documentElement.dataset.motionTier = 'precise'
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    expect(screen.getByTestId('tier').textContent).toBe('precise')
  })
})
