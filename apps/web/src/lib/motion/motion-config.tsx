/**
 * P7 — the single Motion configuration for the whole application.
 *
 * Mounted once at the App root (see App.tsx). Every `motion/react`
 * component below inherits:
 *  - the token clock (`MOTION_DEFAULT_TRANSITION`, presets.ts) as its
 *    default transition,
 *  - the SDMAS reduced-motion policy (`motionReducedMotionValue`,
 *    reduced-motion.ts) for Motion's built-in layout/transform features.
 *
 * The primitives in this folder still resolve their own token-sourced
 * timing from the tier; MotionConfig only supplies the inherited default
 * so hand-rolled motion components stay on the same clock without effort.
 */

import { MotionConfig } from 'motion/react'
import type { ReactNode } from 'react'
import { MOTION_DEFAULT_TRANSITION } from './presets'
import { motionReducedMotionValue } from './reduced-motion'

export interface MotionProviderProps {
  children: ReactNode
}

export function MotionProvider({ children }: MotionProviderProps) {
  return (
    <MotionConfig
      reducedMotion={motionReducedMotionValue}
      transition={MOTION_DEFAULT_TRANSITION}
    >
      {children}
    </MotionConfig>
  )
}
