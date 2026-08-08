/**
 * P7 — MotionLayout: reusable layout-animation primitive.
 *
 * `layout` animates position/size changes via transforms (GPU composited)
 * on the token clock (`MOTION_LAYOUT_TRANSITION` = `slow`, standard ease)
 * so layout moves feel like every other move. Use it for expanding cards,
 * collapsing sections, filter-driven reflows, and list rearrangement.
 *
 * Pass a `layoutId` to additionally opt into cross-mount projection
 * (see SharedElement for the controlled abstraction).
 */

import { motion } from 'motion/react'
import type { HTMLMotionProps } from 'motion/react'
import { MOTION_LAYOUT_TRANSITION } from './presets'

export interface MotionLayoutProps extends HTMLMotionProps<'div'> {
  /** Shared identity for cross-mount FLIP (see SharedElement). */
  layoutId?: string
}

export function MotionLayout({ transition, ...props }: MotionLayoutProps) {
  return <motion.div layout transition={transition ?? MOTION_LAYOUT_TRANSITION} {...props} />
}
