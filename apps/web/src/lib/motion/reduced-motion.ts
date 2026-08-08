/**
 * P7 — reduced-motion bridge.
 *
 * The SDMAS tier system (tokens.ts §7/§8) is the single reduced-motion
 * authority: `prefers-reduced-motion: reduce` → efficient (opacity-only
 * ≤75ms), + `prefers-reduced-transparency: reduce` → minimal (instant).
 * Motion's own reduced-motion flag must agree with it — it is derived from
 * the same tier, never a second system.
 *
 * `motionReducedMotionValue` feeds MotionConfig's `reducedMotion` prop so
 * Motion's built-in layout/transform features follow the same policy.
 */

import { getMotionTier } from './tokens'
import { useMotionTier } from './use-motion-tier'

/**
 * MotionConfig `reducedMotion` value for the whole app. `"user"` tells
 * Motion to read the OS preference for its own features (layout
 * projection, transform animations); the tier resolver derives from the
 * same media query, so the two can never disagree.
 */
export const motionReducedMotionValue = 'user' as const

/** Reactive — true when the active tier is not `precise`. */
export function useReduceMotion(): boolean {
  return useMotionTier() !== 'precise'
}

/** One-shot read — same policy without subscribing. */
export function isReducedMotion(): boolean {
  return getMotionTier() !== 'precise'
}
