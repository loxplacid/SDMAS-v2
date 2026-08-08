/**
 * P7 — MotionReveal: controlled entrance for pages, sections and cards.
 *
 * One semantic prop (`spec`) drives everything. The move spec is resolved
 * through the SDMAS token system (tokens.ts → presets.ts) so timing,
 * distance and tier behavior are identical to the CSS/useMove world:
 *  - precise   → full choreography (fade + optional translate/scale)
 *  - efficient → opacity-only ≤75ms (zero spatial travel)
 *  - minimal   → instant
 *
 * transform/opacity only — no layout shift while animating. Exposes an
 * `exit` frame so it also choreographs departures inside MotionPresence.
 */

import { motion } from 'motion/react'
import type { HTMLMotionProps, Transition } from 'motion/react'
import { useMemo } from 'react'
import { motionPresetFromMove, withStagger } from './presets'
import type { MoveSpec } from './tokens'
import { useMotionTier } from './use-motion-tier'

const MOTION_TAGS = {
  div: motion.div,
  section: motion.section,
  li: motion.li,
  span: motion.span,
} as const

/** Stable default spec — module constant so `useMemo` stays effective. */
const DEFAULT_REVEAL_SPEC: MoveSpec = { verb: 'fade' }

export interface MotionRevealProps
  extends Omit<HTMLMotionProps<'div'>, 'initial' | 'animate' | 'exit' | 'transition'> {
  /** The move spec. Defaults to a pure fade (no spatial travel). */
  spec?: MoveSpec
  /** Sibling index — applies the 20ms reading-order stagger quantum (§4.3). */
  staggerIndex?: number
  /** Extra enter delay in ms. */
  delay?: number
  /** Rendered element. Default `div`. */
  as?: keyof typeof MOTION_TAGS
}

export function MotionReveal({
  spec = DEFAULT_REVEAL_SPEC,
  staggerIndex = 0,
  delay = 0,
  as = 'div',
  children,
  ...rest
}: MotionRevealProps) {
  const tier = useMotionTier()
  const preset = useMemo(() => motionPresetFromMove(spec, tier), [spec, tier])

  const enterTransition = useMemo(
    // The minimal tier is instant — no stagger delay may linger (spec §8).
    () =>
      tier === 'minimal'
        ? preset.enterTransition
        : withStagger(preset.enterTransition, staggerIndex, delay),
    [preset.enterTransition, tier, staggerIndex, delay]
  )

  const Tag = MOTION_TAGS[as] as typeof motion.div

  // Enter uses the token enter clock; exit uses the token exit clock
  // (0.7× enter). Motion's `Transition` type doesn't model the documented
  // per-variant keys (animate/exit), so the object is asserted explicitly.
  const phaseTransition = {
    animate: enterTransition,
    exit: preset.exitTransition,
  } as unknown as Transition

  return (
    <Tag
      initial={preset.initial}
      animate={preset.animate}
      exit={preset.exit}
      transition={phaseTransition}
      {...rest}
    >
      {children}
    </Tag>
  )
}
