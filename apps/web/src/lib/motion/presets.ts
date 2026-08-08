/**
 * P7 — presets: the bridge from SDMAS move specs to Motion values.
 *
 * The SDMAS tokens (duration, easing, travel distance, importance, tier,
 * reduced-motion policy) remain the source of truth — see `tokens.ts`.
 * `resolveMove` already turns a `MoveSpec` into concrete frames *for the
 * active tier* (minimal → instant/fade-only, efficient → opacity-only ≤75ms,
 * precise → full choreography). This module converts those resolved frames
 * into Motion's declarative shape so `motion/react` consumes the same
 * policies without a second tuning system.
 */

import { resolveMove, staggerDelay, type MotionTier, type MoveSpec } from './tokens'
import type { Easing, TargetAndTransition, Transition } from 'motion/react'

/* ------------------------------------------------------------------ */
/* Frame parsing — resolveMove emits CSS transform strings; Motion      */
/* wants numeric values. Parse, never re-derive (single source of truth). */
/* ------------------------------------------------------------------ */

export interface NumericFrame {
  x?: number
  y?: number
  scale?: number
}

function parseFrameTransform(transform: string): NumericFrame {
  if (!transform || transform === 'none') return {}
  const translate = transform.match(/translate\((-?[\d.]+)px,?\s*(-?[\d.]+)?px?\)/)
  if (translate) {
    return { x: parseFloat(translate[1]), y: translate[2] ? parseFloat(translate[2]) : 0 }
  }
  const scale = transform.match(/scale\(([\d.]+)\)/)
  if (scale) return { scale: parseFloat(scale[1]) }
  return {}
}

/** Convert a CSS `cubic-bezier(...)` token into Motion's easing shape. */
export function parseEasing(easing: string): Easing {
  if (easing === 'linear') return 'linear'
  const m = easing.match(/cubic-bezier\(([\d.]+),?\s*([\d.]+),?\s*([\d.]+),?\s*([\d.]+)\)/)
  if (m) {
    return [
      parseFloat(m[1]),
      parseFloat(m[2]),
      parseFloat(m[3]),
      parseFloat(m[4]),
    ] as [number, number, number, number]
  }
  return 'easeOut'
}

/* ------------------------------------------------------------------ */
/* The preset resolver                                                  */
/* ------------------------------------------------------------------ */

export interface MotionPreset {
  /** The from-frame for entrances. */
  initial: TargetAndTransition
  /** The rest frame — everything resolves to this. */
  animate: TargetAndTransition
  /** The reversed from-frame for exits (exit = reverse of entry). */
  exit: TargetAndTransition
  /** Enter timing (duration from the resolved move). */
  enterTransition: Transition
  /** Exit timing — 0.7× of enter, per the module rule. */
  exitTransition: Transition
}

function frameFrom(resolved: ReturnType<typeof resolveMove>, phase: 'enter' | 'exit'): TargetAndTransition {
  const numeric = parseFrameTransform(
    phase === 'enter' ? resolved.enter.transform : resolved.exit.transform
  )
  return {
    opacity: phase === 'enter' ? resolved.enter.opacity : resolved.exit.opacity,
    ...(numeric.x !== undefined ? { x: numeric.x } : {}),
    ...(numeric.y !== undefined ? { y: numeric.y } : {}),
    ...(numeric.scale !== undefined ? { scale: numeric.scale } : {}),
  }
}

export function motionPresetFromMove(spec: MoveSpec, tier: MotionTier): MotionPreset {
  const resolved = resolveMove(spec, tier)
  return {
    initial: frameFrom(resolved, 'enter'),
    animate: { opacity: 1 },
    exit: frameFrom(resolved, 'exit'),
    enterTransition: {
      duration: resolved.duration / 1000,
      ease: parseEasing(resolved.easing),
    },
    exitTransition: {
      duration: resolved.exitDuration / 1000,
      ease: parseEasing(resolved.exitEasing),
    },
  }
}

/**
 * Apply the reading-order stagger quantum (tokens §4.3) to an enter
 * transition. `index` and `extraDelay` are in milliseconds (the token
 * clock); Motion's `delay` is in seconds, so the conversion happens here —
 * the token system stays the source of truth for the value.
 */
export function withStagger(
  transition: Transition,
  index = 0,
  extraDelay = 0
): Transition {
  const delayMs = staggerDelay(index) + extraDelay
  const delay = delayMs / 1000
  return delay > 0 ? { ...transition, delay } : transition
}

/* ------------------------------------------------------------------ */
/* Shared defaults for MotionConfig + layout animations                 */
/* ------------------------------------------------------------------ */

import { MOTION_DURATIONS, MOTION_EASINGS } from './tokens'

/** The single default transition the whole Motion tree inherits. */
export const MOTION_DEFAULT_TRANSITION: Transition = {
  duration: MOTION_DURATIONS.base / 1000,
  ease: parseEasing(MOTION_EASINGS.standard),
}

/**
 * Layout animation timing — token-sourced. Motion's `layout` animates
 * position/size via transforms (GPU composited); we keep the duration and
 * easing on the token clock so layout moves feel like every other move.
 */
export const MOTION_LAYOUT_TRANSITION: Transition = {
  duration: MOTION_DURATIONS.slow / 1000,
  ease: parseEasing(MOTION_EASINGS.standard),
}
