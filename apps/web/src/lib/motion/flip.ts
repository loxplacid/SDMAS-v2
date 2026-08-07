import { useCallback, useLayoutEffect, useRef, type RefObject } from 'react'
import { getMotionTier, MOTION_DURATIONS, MOTION_EASINGS } from './tokens'

export interface FlipOptions {
  /** Animation duration in ms. Default: 260 (motion.slow — spec §6.4). */
  duration?: number
  /** Easing. Default: standard. */
  easing?: string
  /** Called once when the flip completes (transitionend or timeout). */
  onComplete?: () => void
}

/**
 * Pure delta math for a FLIP (spec §9.2). Returns the transform that maps
 * the element from its old rect to its new rect, so animating back to the
 * identity transform lands it in the final layout.
 */
export function flipDelta(from: DOMRect, to: DOMRect): { dx: number; dy: number; sx: number; sy: number } {
  const dx = from.left - to.left
  const dy = from.top - to.top
  const sx = from.width > 0 && to.width > 0 ? from.width / to.width : 1
  const sy = from.height > 0 && to.height > 0 ? from.height / to.height : 1
  return { dx, dy, sx, sy }
}

/**
 * Animate one element from its old rect to its new rect via FLIP:
 *  1. apply the inverse delta with `transition: none`,
 *  2. force a reflow so the frame commits,
 *  3. transition back to the identity transform.
 *
 * Spec: transform-only, transform-origin top-left, cleanup on completion.
 * No-op when the element didn't move.
 *
 * Cleanup restores the element's *previous* inline transition, transform,
 * and transform-origin — FLIP never leaves inline styles behind, and never
 * stomps a transition it doesn't own (e.g. `useMove`'s rest style).
 */
export function flipElement(el: HTMLElement, from: DOMRect, to: DOMRect, options?: FlipOptions): void {
  const { dx, dy, sx, sy } = flipDelta(from, to)
  const moved = Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5 || Math.abs(sx - 1) > 0.01 || Math.abs(sy - 1) > 0.01
  if (!moved) {
    options?.onComplete?.()
    return
  }

  const duration = options?.duration ?? MOTION_DURATIONS.slow
  const easing = options?.easing ?? MOTION_EASINGS.standard

  // Preserve what we're about to touch so cleanup restores it exactly.
  const previousTransition = el.style.transition
  const previousTransform = el.style.transform
  const previousTransformOrigin = el.style.transformOrigin

  el.style.transformOrigin = '0 0'
  el.style.transition = 'none'
  el.style.transform = `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`
  void el.offsetWidth // force reflow so the start frame commits

  el.style.transition = `transform ${duration}ms ${easing}`
  el.style.transform = 'none'

  let finished = false
  let timeout = 0
  const done = () => {
    if (finished) return
    finished = true
    el.removeEventListener('transitionend', onEnd)
    clearTimeout(timeout)
    el.style.transition = previousTransition
    el.style.transform = previousTransform
    el.style.transformOrigin = previousTransformOrigin
    options?.onComplete?.()
  }
  // Filter to the transform transition only — a concurrent opacity
  // transition (e.g. from `useMove`) must not tear the flip down early.
  const onEnd = (event: TransitionEvent) => {
    if (event.propertyName === 'transform') done()
  }
  el.addEventListener('transitionend', onEnd)
  timeout = window.setTimeout(done, duration + 100)
}

/**
 * Imperative FLIP for container-level reflows (sidebar collapse, expand/
 * collapse of a section, filter condensation).
 *
 *   withFlip(container, () => setCollapsed(true))
 *
 * Direct children carrying the `data-flip` attribute are the FLIP targets;
 * everything else is left alone. Layout mutation must be synchronous —
 * wrap React state changes in `flushSync` when needed.
 */
export function withFlip(container: HTMLElement, mutate: () => void, options?: FlipOptions): void {
  const targets = Array.from(container.children).filter(
    (child): child is HTMLElement => child instanceof HTMLElement && child.matches('[data-flip]')
  )
  const from = new Map<HTMLElement, DOMRect>(targets.map((el) => [el, el.getBoundingClientRect()]))
  mutate()
  targets.forEach((el) => {
    const to = el.getBoundingClientRect()
    const prev = from.get(el)
    if (prev) flipElement(el, prev, to, options)
  })
}

/**
 * `useFlipList` — keyed FLIP for reorder/reflow (sorting, filtering,
 * expandable rows shifting siblings). Animates only items that existed in
 * the previous commit and moved; entering items are left to `useMove`.
 *
 *   const { containerRef, itemRef } = useFlipList(rows, (r) => r.id)
 *   <div ref={containerRef}>
 *     {rows.map((row) => (
 *       <div key={row.id} ref={itemRef(row.id)}>{...}</div>
 *     ))}
 *   </div>
 *
 * The layout effect re-measures after *every* commit (that is the FLIP
 * contract: positions may change without `items` changing, e.g. a row
 * above expanding). `items` exists for type inference and keying.
 *
 * Reduced-motion tiers skip the animation entirely (positions snap) —
 * FLIP is a spatial move, illegal outside the precise tier (spec §8).
 *
 * Note: FLIP is transform-only, so a *scale* flip stretches children.
 * Reorders and vertical reflows (translate-only) are safe on text;
 * width-changing scale flips should be limited to image/surface rows.
 */
export function useFlipList<T, E extends HTMLElement = HTMLDivElement>(
  items: readonly T[],
  keyOf: (item: T, index: number) => string | number = (item) =>
    (item as { id?: string | number }).id as string | number,
  options?: FlipOptions
): { containerRef: RefObject<E | null>; itemRef: (key: string | number) => (el: HTMLElement | null) => void } {
  const keyOfRef = useRef(keyOf)
  keyOfRef.current = keyOf
  const optionsRef = useRef(options)
  optionsRef.current = options

  const containerRef = useRef<E | null>(null)
  const itemElsRef = useRef<Map<string | number, HTMLElement>>(new Map())
  const prevRectsRef = useRef<Map<string | number, DOMRect>>(new Map())

  useLayoutEffect(() => {
    const next = new Map<string | number, DOMRect>()
    itemElsRef.current.forEach((el, key) => next.set(key, el.getBoundingClientRect()))

    if (getMotionTier() === 'precise') {
      prevRectsRef.current.forEach((from, key) => {
        const el = itemElsRef.current.get(key)
        const to = next.get(key)
        if (el && to) flipElement(el, from, to, optionsRef.current)
      })
    }

    prevRectsRef.current = next
  })

  // Stable per-key callbacks: without memoization a fresh closure per
  // render would make React detach/reattach every item ref each commit.
  const itemRefsRef = useRef<Map<string | number, (el: HTMLElement | null) => void>>(new Map())
  const itemRef = useCallback((key: string | number) => {
    let callback = itemRefsRef.current.get(key)
    if (!callback) {
      callback = (el) => {
        if (el) itemElsRef.current.set(key, el)
        else itemElsRef.current.delete(key)
      }
      itemRefsRef.current.set(key, callback)
    }
    return callback
  }, [])

  return { containerRef, itemRef }
}
