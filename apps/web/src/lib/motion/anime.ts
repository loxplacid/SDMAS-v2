/**
 * P7 — useScopedAnime: a small, safe React integration for anime.js.
 *
 * The only sanctioned way to reach anime.js from React components:
 *  - elements are passed directly (refs) — no global selectors
 *  - every created animation is tracked and reverted on unmount / `clear()`
 *  - the SDMAS tier policy is enforced (tokens.ts §8):
 *      minimal   → nothing runs (returns null)
 *      efficient → spatial (transform-family) keys stripped, duration
 *                  capped at 75ms; a choreography that is transform-only
 *                  is suppressed entirely
 *      precise   → full parameters
 *  - easing tokens are bridged to anime's spelling, never re-tuned
 *
 * Reserved for choreography that genuinely benefits from timelines, SVG
 * drawing, counters and deliberate staggers — plain CSS transitions /
 * Motion remain the default for everyday UI motion.
 */

import { useCallback, useEffect, useRef } from 'react'
import { animate, createTimeline } from 'animejs'
import type { AnimationParams, DefaultsParams, TimelineParams } from 'animejs'
import { MOTION_EASINGS } from './tokens'
import type { MotionTier } from './tokens'
import { useMotionTier } from './use-motion-tier'

/** Elements are passed directly (refs) — never global selectors. */
export type AnimeTarget = HTMLElement | SVGElement | readonly (HTMLElement | SVGElement)[]

/** Structural subset of anime instances we track for cleanup. */
interface AnimeInstance {
  revert: () => unknown
}

/** Spatial (transform-family) keys — stripped under the efficient tier. */
const SPATIAL_KEYS = new Set([
  'x',
  'y',
  'z',
  'translateX',
  'translateY',
  'translateZ',
  'scale',
  'scaleX',
  'scaleY',
  'scaleZ',
  'rotate',
  'rotateX',
  'rotateY',
  'rotateZ',
  'skewX',
  'skewY',
])

/** Efficient-tier duration cap (spec §8: ≤75ms). */
const EFFICIENT_CAP_MS = 75

/**
 * Bridge an SDMAS easing token to anime.js's cubicBezier spelling
 * (spec §3.2 — anime consumes the same curves, not a second tuning set).
 */
export function toAnimeEasing(easing: string): string {
  if (easing === 'linear') return 'linear'
  const m = easing.match(/cubic-bezier\(([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\)/)
  if (m) return `cubicBezier(${m[1]}, ${m[2]}, ${m[3]}, ${m[4]})`
  return easing
}

/** Map a named token easing to anime spelling (e.g. `MOTION_EASINGS.enter`). */
export function tokenEasingToAnime(name: keyof typeof MOTION_EASINGS): string {
  return toAnimeEasing(MOTION_EASINGS[name])
}

function capDuration(params: AnimationParams): AnimationParams {
  const duration = params.duration
  if (typeof duration === 'number' && duration > EFFICIENT_CAP_MS) {
    return { ...params, duration: EFFICIENT_CAP_MS }
  }
  return params
}

/** Remove transform-family keys; returns null when nothing remains. */
function withoutSpatial(params: AnimationParams): AnimationParams | null {
  const filtered: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (SPATIAL_KEYS.has(key)) continue
    filtered[key] = value
  }
  return Object.keys(filtered).length === 0 ? null : (filtered as AnimationParams)
}

/**
 * Same policy for TimelineParams — including `defaults`, which anime's
 * timeline applies to every segment (the per-segment `.add` wrap in
 * `scopedTimeline` covers the explicit adds). `DefaultsParams` is
 * timing-only by type, so the realistic violation is the duration cap;
 * the spatial strip stays as a defensive no-op.
 */
function withoutTimelineSpatial(params: TimelineParams): TimelineParams {
  const withDefaults = params as TimelineParams & { defaults?: DefaultsParams }
  if (!withDefaults.defaults) return params
  const stripped = withoutSpatial(capDuration(withDefaults.defaults))
  return {
    ...params,
    defaults: stripped === null ? {} : (stripped as unknown as DefaultsParams),
  }
}

export interface AnimeControls {
  /** Start an animation on the given element(s). Returns null when suppressed. */
  animate: (target: AnimeTarget, params: AnimationParams) => ReturnType<typeof animate> | null
  /** Build a timeline. Returns null when suppressed. */
  timeline: (params?: TimelineParams) => ReturnType<typeof createTimeline> | null
  /** Revert every animation created through this hook. */
  clear: () => void
  /** The active tier — consumers may branch for richer choreography. */
  tier: MotionTier
}

export function useScopedAnime(): AnimeControls {
  const tier = useMotionTier()
  const active = useRef<Set<AnimeInstance>>(new Set())

  const clear = useCallback(() => {
    active.current.forEach((instance) => {
      try {
        instance.revert()
      } catch {
        // Already reverted/completed — nothing to undo.
      }
    })
    active.current.clear()
  }, [])

  // Unmount cleanup: never leave an anime instance running.
  useEffect(() => clear, [clear])

  const scopedAnimate = useCallback<AnimeControls['animate']>(
    (target, params) => {
      if (tier === 'minimal' || !target) return null
      const effective = tier === 'efficient' ? withoutSpatial(capDuration(params)) : params
      if (effective === null) return null // transform-only under reduced motion → suppressed
      const animation = animate(target as Parameters<typeof animate>[0], effective)
      active.current.add(animation as unknown as AnimeInstance)
      return animation
    },
    [tier]
  )

  const scopedTimeline = useCallback<AnimeControls['timeline']>(
    (params) => {
      if (tier === 'minimal') return null
      const timeline = createTimeline(
        tier === 'efficient' && params ? withoutTimelineSpatial(params) : params
      )
      active.current.add(timeline as unknown as AnimeInstance)
      if (tier === 'efficient') {
        // Wrap .add so every segment also honors the reduced tier.
        const rawAdd = timeline.add.bind(timeline)
        timeline.add = ((target, segParams, position) => {
          const effective = withoutSpatial(capDuration(segParams))
          return effective === null ? timeline : rawAdd(target, effective, position)
        }) as typeof timeline.add
      }
      return timeline
    },
    [tier]
  )

  return { animate: scopedAnimate, timeline: scopedTimeline, clear, tier }
}
