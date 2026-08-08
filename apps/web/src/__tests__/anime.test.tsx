import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { useScopedAnime, toAnimeEasing, tokenEasingToAnime } from '../lib/motion/anime'
import { MOTION_EASINGS } from '../lib/motion/tokens'

/**
 * P7 — focused tests for the scoped anime.js bridge.
 *
 * `animejs` is mocked so we can assert the *policy* useScopedAnime enforces
 * (tier gating, spatial stripping, duration cap, cleanup) without running a
 * real animation engine in jsdom. The tier is stubbed via matchMedia, the
 * same pattern as the other motion tests.
 */

const animeMocks = vi.hoisted(() => ({
  animateCalls: [] as Array<{ target: unknown; params: Record<string, unknown> }>,
  timelineAddCalls: [] as Array<{ target: unknown; params: Record<string, unknown> }>,
  createTimelineCalls: 0,
  createTimelineParams: [] as Array<Record<string, unknown> | null>,
  reverted: 0,
}))

vi.mock('animejs', () => {
  const makeInstance = () => ({
    add: (target: unknown, params: Record<string, unknown>) => {
      animeMocks.timelineAddCalls.push({ target, params })
    },
    revert: () => {
      animeMocks.reverted++
    },
  })
  return {
    animate: (target: unknown, params: Record<string, unknown>) => {
      animeMocks.animateCalls.push({ target, params })
      return makeInstance()
    },
    createTimeline: (params?: Record<string, unknown>) => {
      animeMocks.createTimelineCalls++
      animeMocks.createTimelineParams.push(params ?? null)
      return makeInstance()
    },
    stagger: (value: unknown) => value,
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

beforeEach(() => {
  animeMocks.animateCalls.length = 0
  animeMocks.timelineAddCalls.length = 0
  animeMocks.createTimelineCalls = 0
  animeMocks.createTimelineParams.length = 0
  animeMocks.reverted = 0
})

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Probe that fires one full choreography on mount. */
function AnimeProbe() {
  const { animate } = useScopedAnime()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    animate(ref.current as HTMLDivElement, {
      translateX: 40,
      opacity: [0, 1],
      duration: 400,
      easing: 'cubicBezier(0.2, 0, 0, 1)',
    })
  }, [animate])
  return <div ref={ref} />
}

describe('toAnimeEasing (P7 — easing bridge)', () => {
  it('converts SDMAS cubic-bezier tokens to anime spelling', () => {
    expect(toAnimeEasing('cubic-bezier(0.2, 0, 0, 1)')).toBe('cubicBezier(0.2, 0, 0, 1)')
    expect(toAnimeEasing('linear')).toBe('linear')
  })

  it('maps named token easings to the anime family', () => {
    expect(tokenEasingToAnime('enter')).toBe('cubicBezier(0.05, 0.7, 0.1, 1)')
    expect(tokenEasingToAnime('spring')).toBe('cubicBezier(0.34, 1.56, 0.64, 1)')
    expect(tokenEasingToAnime('standard')).toBe(toAnimeEasing(MOTION_EASINGS.standard))
  })
})

describe('useScopedAnime (P7 — tier policy)', () => {
  it('runs full choreography in the precise tier', () => {
    stubMotionPrefs(false, false)
    render(<AnimeProbe />)

    expect(animeMocks.animateCalls).toHaveLength(1)
    expect(animeMocks.animateCalls[0].params.translateX).toBe(40)
    expect(animeMocks.animateCalls[0].params.duration).toBe(400)
  })

  it('strips spatial keys and caps duration to 75ms in the efficient tier', () => {
    stubMotionPrefs(true, false)
    render(<AnimeProbe />)

    expect(animeMocks.animateCalls).toHaveLength(1)
    expect(animeMocks.animateCalls[0].params.translateX).toBeUndefined()
    expect(animeMocks.animateCalls[0].params.opacity).toEqual([0, 1])
    expect(animeMocks.animateCalls[0].params.duration).toBe(75)
  })

  it('suppresses animation entirely in the minimal tier', () => {
    stubMotionPrefs(true, true)
    render(<AnimeProbe />)

    expect(animeMocks.animateCalls).toHaveLength(0)
  })

  it('reverts tracked animations on unmount', () => {
    stubMotionPrefs(false, false)
    const { unmount } = render(<AnimeProbe />)

    expect(animeMocks.reverted).toBe(0)
    unmount()
    expect(animeMocks.reverted).toBe(1)
  })

  it('reverts everything through clear()', () => {
    stubMotionPrefs(false, false)

    function ClearProbe() {
      const { animate, clear } = useScopedAnime()
      const ref = useRef<HTMLDivElement>(null)
      useEffect(() => {
        animate(ref.current as HTMLDivElement, { opacity: [0, 1] })
        animate(ref.current as HTMLDivElement, { scale: 1.05 })
        clear()
      }, [animate, clear])
      return <div ref={ref} />
    }

    render(<ClearProbe />)
    expect(animeMocks.reverted).toBe(2)
  })

  it('creates a tracked timeline in the precise tier', () => {
    stubMotionPrefs(false, false)

    function TimelineProbe() {
      const { timeline } = useScopedAnime()
      const ref = useRef<HTMLDivElement>(null)
      useEffect(() => {
        const tl = timeline()
        if (tl) tl.add(ref.current as HTMLDivElement, { opacity: [0, 1] })
      }, [timeline])
      return <div ref={ref} />
    }

    render(<TimelineProbe />)
    expect(animeMocks.createTimelineCalls).toBe(1)
    expect(animeMocks.timelineAddCalls).toHaveLength(1)
  })

  it('polices per-segment timeline adds under the efficient tier', () => {
    stubMotionPrefs(true, false)

    function TimelineProbe() {
      const { timeline } = useScopedAnime()
      const ref = useRef<HTMLDivElement>(null)
      useEffect(() => {
        const tl = timeline()
        if (tl) tl.add(ref.current as HTMLDivElement, { translateX: 40, opacity: [0, 1], duration: 400 })
      }, [timeline])
      return <div ref={ref} />
    }

    render(<TimelineProbe />)
    expect(animeMocks.timelineAddCalls).toHaveLength(1)
    expect(animeMocks.timelineAddCalls[0].params.translateX).toBeUndefined()
    expect(animeMocks.timelineAddCalls[0].params.opacity).toEqual([0, 1])
    expect(animeMocks.timelineAddCalls[0].params.duration).toBe(75)
  })

  it('caps timeline-default durations under the efficient tier', () => {
    stubMotionPrefs(true, false)

    // DefaultsParams is timing-only by type, so the realistic policy
    // violation is the duration cap (e.g. a slow 400ms default segment).
    function DefaultsProbe() {
      const { timeline } = useScopedAnime()
      const ref = useRef<HTMLDivElement>(null)
      useEffect(() => {
        const tl = timeline({ defaults: { duration: 400 } })
        if (tl) tl.add(ref.current as HTMLDivElement, { opacity: [0, 1] })
      }, [timeline])
      return <div ref={ref} />
    }

    render(<DefaultsProbe />)
    expect(animeMocks.createTimelineParams[0]).toEqual({ defaults: { duration: 75 } })
  })
})
