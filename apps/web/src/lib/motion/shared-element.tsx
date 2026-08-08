/**
 * P7 — SharedElement: controlled abstraction around Motion's `layoutId`.
 *
 * Two SharedElements that render at different times with the same
 * `layoutId` share an identity in Motion's eyes, so the browser's View
 * Transition / FLIP projection morphs one into the other. Planned use:
 *  - Student list row → Student 360 header
 *  - card → detail panel
 *  - navigation indicators and tabs
 *
 * The primitive only establishes the contract — the complete Student 360
 * transition is a later milestone.
 */

import { motion } from 'motion/react'
import type { HTMLMotionProps } from 'motion/react'
import { MOTION_LAYOUT_TRANSITION } from './presets'

export interface SharedElementProps extends HTMLMotionProps<'div'> {
  /**
   * The identity shared across mounts. Same value in two places = same
   * element in Motion's eyes. Must be unique per visual element.
   */
  layoutId: string
}

export function SharedElement({ layoutId, transition, children, ...props }: SharedElementProps) {
  return (
    <motion.div
      layoutId={layoutId}
      transition={transition ?? MOTION_LAYOUT_TRANSITION}
      {...props}
    >
      {children}
    </motion.div>
  )
}
