import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import {
  buildTransition,
  MOTION_EASINGS,
  MOTION_PULSE_DURATION,
  resolveMove,
  staggerDelay,
  type MotionTier,
  type MovePhase,
  type MoveSpec,
  type ResolvedMove,
} from './tokens'
import { useMotionTier } from './use-motion-tier'

export interface PlayOptions {
  /** Extra delay before the animation starts (e.g. stagger). */
  delayMs?: number
  /** Called when the animation finishes (exit-before-unmount pattern). */
  onfinish?: () => void
}

export interface UseMoveOptions {
  /** Play the enter animation once on mount. Default: false. */
  animateOnMount?: boolean
  /** Sibling index used for the 20ms stagger quantum (spec §4.3). */
  staggerIndex?: number
}

export interface UseMoveResult {
  /**
   * Stable callback ref — attach to the element. Used by the mount
   * animation; composable with other refs:
   *
   *   <div ref={(el) => { move.ref(el); yourRef.current = el }} />
   */
  ref: (el: HTMLElement | null) => void
  /**
   * Style for the element. While `animateOnMount` is in flight this is the
   * start frame (opacity 0 / offset transform); after it settles it is the
   * rest frame. The rest frame permanently wires transform/opacity
   * transitions by design (spec §11.2) — any later transform, including
   * class-driven hovers, animates on the same clock.
   */
  style: CSSProperties
  /** The fully resolved move (durations, easings, frames). */
  move: ResolvedMove
  /**
   * Imperative enter/exit via the Web Animations API (fallback: CSS
   * transition). The canonical exit pattern:
   *
   *   move.play(el, 'exit', { onfinish: () => unmount() })
   */
  play: (el: HTMLElement | null, phase: MovePhase, options?: PlayOptions) => void
  /** One-shot attention pulse (scale 1 → 1.05 → 1). Legal only in the precise tier. */
  pulse: (el: HTMLElement | null) => void
  /** The active motion tier for this render. */
  tier: MotionTier
}

/**
 * `useMove` — the choreography hook (spec §2, §5).
 *
 * Turns a move spec — (verb, direction, distance-class, importance-class)
 * — into resolved motion tokens, a mount enter animation, and imperative
 * enter/exit/pulse helpers. The spec object must be referentially stable
 * (module constant or useMemo) so the resolved move doesn't churn.
 *
 * Tiers are respected automatically: efficient → opacity-only ≤75ms,
 * minimal → instant. Under those tiers the resolver already zeroes out
 * transforms, so components need no branching.
 */
export function useMove(spec: MoveSpec, options?: UseMoveOptions): UseMoveResult {
  const tier = useMotionTier()
  const move = useMemo(() => resolveMove(spec, tier), [spec, tier])

  const animateOnMount = options?.animateOnMount ?? false
  const staggerIndex = options?.staggerIndex ?? 0

  const [phase, setPhase] = useState<'start' | 'rest'>(animateOnMount ? 'start' : 'rest')
  const innerRef = useRef<HTMLElement | null>(null)

  const ref = useCallback((el: HTMLElement | null) => {
    innerRef.current = el
  }, [])

  /* Mount enter (spec §3.3): commit the start frame without a transition,
   * then — after the browser has computed it — flip to rest so the CSS
   * transition plays. Delay is applied after the double rAF so staggered
   * siblings all start from their frame. */
  useEffect(() => {
    if (!animateOnMount || phase !== 'start') return

    if (tier === 'minimal') {
      setPhase('rest')
      return
    }

    const delay = staggerDelay(staggerIndex)
    let cancelled = false
    const timers: number[] = []

    const raf1 = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (cancelled) return
        const timer = window.setTimeout(() => {
          if (!cancelled) setPhase('rest')
        }, delay)
        timers.push(timer)
      })
    })

    return () => {
      cancelled = true
      cancelAnimationFrame(raf1)
      timers.forEach((t) => clearTimeout(t))
    }
    // Mount-only choreography: intentionally stable deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const style: CSSProperties =
    phase === 'start'
      ? {
          opacity: move.enter.opacity,
          transform: move.enter.transform,
          transition: 'none',
          willChange: 'transform, opacity',
        }
      : {
          opacity: 1,
          transform: 'none',
          transition: buildTransition(move, 'enter'),
        }

  const play = useCallback(
    (el: HTMLElement | null, movePhase: MovePhase, playOptions?: PlayOptions) => {
      if (!el) {
        playOptions?.onfinish?.()
        return
      }
      const delay = playOptions?.delayMs ?? 0
      const duration = movePhase === 'enter' ? move.duration : move.exitDuration
      const easing = movePhase === 'enter' ? move.easing : move.exitEasing
      const target = movePhase === 'enter' ? move.enter : move.exit

      if (tier === 'minimal') {
        // Instant state application — no motion at all (spec §8).
        el.style.transition = 'none'
        el.style.opacity = String(target.opacity)
        el.style.transform = target.transform
        playOptions?.onfinish?.()
        return
      }

      if (typeof el.animate !== 'function') {
        // No WAAPI (jsdom, old engines) — CSS transition fallback.
        el.style.transition = buildTransition(move, movePhase)
        el.style.opacity = String(target.opacity)
        el.style.transform = target.transform
        window.setTimeout(() => playOptions?.onfinish?.(), duration + delay)
        return
      }

      const animation = el.animate(
        movePhase === 'enter'
          ? [{ ...move.enter }, { opacity: 1, transform: 'none' }]
          : [{ opacity: 1, transform: 'none' }, { ...move.exit }],
        { duration, easing, delay, fill: 'both' }
      )
      animation.onfinish = () => playOptions?.onfinish?.()
    },
    [move, tier]
  )

  const pulse = useCallback(
    (el: HTMLElement | null) => {
      // Spec §7: Pulse is gated by the precise tier; suppressed elsewhere.
      if (!el || tier !== 'precise') return
      if (typeof el.animate === 'function') {
        el.animate(
          [
            { transform: 'scale(1)' },
            { transform: 'scale(1.05)', offset: 0.5 },
            { transform: 'scale(1)' },
          ],
          { duration: MOTION_PULSE_DURATION, easing: MOTION_EASINGS.spring }
        )
        return
      }
      el.style.transition = `transform 150ms ${MOTION_EASINGS.spring}`
      el.style.transform = 'scale(1.05)'
      window.setTimeout(() => {
        el.style.transform = 'scale(1)'
      }, 150)
    },
    [tier]
  )

  return { ref, style, move, play, pulse, tier }
}
