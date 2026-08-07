/**
 * SDMAS Motion System v3 — tokens & the move-spec resolver.
 *
 * Normative source: docs/MOTION_SYSTEM_V3.md ("The Compass").
 *
 * Every animation in the product is described as a *move spec*:
 *
 *     (verb, direction, distance-class, importance-class)
 *
 * and everything else — duration, easing, travel distance, enter/exit
 * transforms — is *derived* by `resolveMove`. Components never author
 * animations; they author move specs.
 *
 * The token values below are the spec's canonical values (§Appendix A).
 * The CSS seed in `src/index.css` carries the same durations under the
 * same names; the easing curves exist there under legacy names
 * (`--ease-emphasized-decelerate` ≈ enter, `--ease-emphasized-accelerate`
 * ≈ exit, `--ease-spring` = spring). Aligning the CSS names is a follow-up
 * to this module — the spec is normative.
 */

export type Verb = 'slide' | 'scale' | 'fade' | 'draw' | 'pulse'
export type Direction = 'N' | 'E' | 'S' | 'W' | 'SE' | 'Z'
export type DistanceClass = 'D1' | 'D2' | 'D3' | 'D4'
export type Importance = 'I1' | 'I2' | 'I3'
export type MotionTier = 'precise' | 'efficient' | 'minimal'
export type MovePhase = 'enter' | 'exit'

export interface MoveSpec {
  /** The verb. Required — there are exactly five. */
  verb: Verb
  /**
   * The compass point (spec §2.2). Semantics, not aesthetics:
   * E = forward · W = back · N = settles from above · S = grounded ·
   * SE = corner toasts · Z = depth (modal, palette, focus).
   * Defaults: slide → E, scale → Z.
   */
  direction?: Direction
  /** Travel class (spec §2.3). Defaults: slide → D3, scale → D4, fade → D2, draw/pulse → D1. */
  distance?: DistanceClass
  /** Importance modifier (spec §2.4): I1 = floor, I2 = middle, I3 = ceiling. Default I2. */
  importance?: Importance
}

export interface MoveKeyframe {
  opacity: number
  transform: string
}

export interface ResolvedMove {
  /** Enter duration, ms (token-grid value). */
  duration: number
  /** Exit duration, ms — 0.7 × enter, never below 75ms (spec §3.2 rule 5). */
  exitDuration: number
  /** Enter easing. */
  easing: string
  /** Exit easing. */
  exitEasing: string
  /** Travel distance in px (0 under reduced tiers). */
  travelPx: number
  /** Scale-from value for Z moves (1 = no scale). */
  scaleFrom: number
  /** Start frame of the enter animation. */
  enter: MoveKeyframe
  /** End frame of the exit animation (reverse of entry). */
  exit: MoveKeyframe
}

/* ------------------------------------------------------------------ */
/* Duration tokens (spec §3.1)                                        */
/* ------------------------------------------------------------------ */

export const MOTION_DURATIONS = {
  instant: 75,
  fast: 120,
  base: 180,
  slow: 260,
  slower: 380,
  slowest: 500,
} as const

/** Duration per distance class, indexed by importance: [I1 floor, I2 middle, I3 ceiling]. */
const DISTANCE_DURATIONS: Record<DistanceClass, readonly [number, number, number]> = {
  D1: [75, 90, 120],
  D2: [120, 150, 180],
  D3: [180, 220, 260],
  D4: [380, 440, 500],
}

/** Travel per distance class (spec §2.3): D4 slides are deliberately small (8px, spec §6.3). */
const TRAVEL_PX: Record<DistanceClass, number> = { D1: 2, D2: 4, D3: 16, D4: 8 }

/** Scale-from per class for Z moves (modal 0.96, everything smaller 0.98). */
const SCALE_FROM: Record<DistanceClass, number> = { D1: 0.98, D2: 0.98, D3: 0.98, D4: 0.96 }

const DEFAULT_DISTANCE: Record<Verb, DistanceClass> = {
  slide: 'D3',
  scale: 'D4',
  fade: 'D2',
  draw: 'D1',
  pulse: 'D1',
}

/* ------------------------------------------------------------------ */
/* Easing tokens (spec §3.2)                                          */
/* ------------------------------------------------------------------ */

export const MOTION_EASINGS = {
  /** Default UI motion — the default for anything unclassified. */
  standard: 'cubic-bezier(0.2, 0, 0, 1)',
  /** Arrivals: fast start, soft landing. Never used for exits. */
  enter: 'cubic-bezier(0.05, 0.7, 0.1, 1)',
  /** Departures: leave quickly, fade at the end. Never used for entrances. */
  exit: 'cubic-bezier(0.3, 0, 0.8, 0.15)',
  /** Micro-springs — small objects (≤44px) and gestures only. */
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  /** The only legal loop easing: spinners, shimmer, determinate progress. */
  linear: 'linear',
} as const

/* ------------------------------------------------------------------ */
/* Choreography constants (spec §4, §6.20)                            */
/* ------------------------------------------------------------------ */

export const MOTION_EXIT_SCALE = 0.7 as const
export const MOTION_PULSE_DURATION = 300 as const
export const MOTION_PARALLAX = { overlay: 16, surface: 8, page: 4 } as const
export const MOTION_STAGGER = { quantum: 20, cap: 150 } as const

/** Cardinal offsets — ±1 per axis; multiplied by travelPx in the resolver. */
const OFFSET: Record<Direction, { x: number; y: number }> = {
  N: { x: 0, y: -1 },
  E: { x: 1, y: 0 },
  S: { x: 0, y: 1 },
  W: { x: -1, y: 0 },
  SE: { x: 1, y: 1 },
  Z: { x: 0, y: 0 },
}

/* ------------------------------------------------------------------ */
/* Tier detection (spec §7, §8)                                       */
/* ------------------------------------------------------------------ */

export const MOTION_TIERS: readonly MotionTier[] = ['precise', 'efficient', 'minimal']

/**
 * Resolve the current motion tier from the environment:
 *  1. An explicit `data-motion-tier` attribute on <html> wins (in-app toggle).
 *  2. `prefers-reduced-motion: reduce` → efficient (opacity-only, ≤75ms).
 *  3. ...combined with `prefers-reduced-transparency: reduce` → minimal.
 *  4. Otherwise precise.
 */
export function getMotionTier(): MotionTier {
  if (typeof window === 'undefined') return 'precise'
  const attr = document.documentElement.dataset.motionTier
  if (attr && (MOTION_TIERS as readonly string[]).includes(attr)) return attr as MotionTier
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  if (!reduced) return 'precise'
  const noTransparency = window.matchMedia?.('(prefers-reduced-transparency: reduce)').matches ?? false
  return noTransparency ? 'minimal' : 'efficient'
}

/* ------------------------------------------------------------------ */
/* The resolver — the heart of the system                             */
/* ------------------------------------------------------------------ */

/**
 * Resolve a move spec into concrete motion tokens (spec §2).
 * Pure and deterministic — unit-testable without a DOM.
 */
export function resolveMove(spec: MoveSpec, tier: MotionTier = 'precise'): ResolvedMove {
  const verb = spec.verb
  const distance = spec.distance ?? DEFAULT_DISTANCE[verb]
  const importance = spec.importance ?? 'I2'
  const direction = spec.direction ?? (verb === 'scale' ? 'Z' : verb === 'slide' ? 'E' : 'Z')

  /* Minimal tier: instant, fade-only (spec §8). */
  if (tier === 'minimal') {
    return {
      duration: 0,
      exitDuration: 0,
      easing: MOTION_EASINGS.linear,
      exitEasing: MOTION_EASINGS.linear,
      travelPx: 0,
      scaleFrom: 1,
      enter: { opacity: 0, transform: 'none' },
      exit: { opacity: 0, transform: 'none' },
    }
  }

  const importanceIndex = importance === 'I1' ? 0 : importance === 'I3' ? 2 : 1
  const rawDuration = DISTANCE_DURATIONS[distance][importanceIndex]
  /* Efficient tier: opacity-only, ≤75ms (spec §8). */
  const duration = tier === 'efficient' ? Math.min(75, rawDuration) : rawDuration
  const travelPx = tier === 'efficient' ? 0 : TRAVEL_PX[distance]
  const scaleFrom = tier === 'efficient' ? 1 : SCALE_FROM[distance]

  /* Enter / exit frames. Exits are the reverse of entry (spec §4.1). */
  let enterTransform = 'none'
  let exitTransform = 'none'

  if (tier === 'precise') {
    if (verb === 'slide') {
      const { x, y } = OFFSET[direction]
      const dx = x * travelPx
      const dy = y * travelPx
      if (dx !== 0 || dy !== 0) {
        enterTransform = `translate(${dx}px, ${dy}px)`
        exitTransform = `translate(${-dx}px, ${-dy}px)`
      }
    } else if (verb === 'scale') {
      enterTransform = `scale(${scaleFrom})`
      exitTransform = 'scale(0.98)'
    }
  }

  const spatial = verb === 'slide' || verb === 'scale'
  const easing = spatial ? MOTION_EASINGS.enter : MOTION_EASINGS.standard
  const exitEasing = spatial ? MOTION_EASINGS.exit : MOTION_EASINGS.standard

  return {
    duration,
    exitDuration: Math.max(MOTION_DURATIONS.instant, Math.round(duration * MOTION_EXIT_SCALE)),
    easing,
    exitEasing,
    travelPx,
    scaleFrom,
    enter: { opacity: 0, transform: enterTransform },
    exit: { opacity: 0, transform: exitTransform },
  }
}

/**
 * Stagger delay for sibling index `i` (spec §4.3):
 * `min(i × 20ms, 150ms)` — reading order on entry, reversed on exit.
 */
export function staggerDelay(index: number, options?: { quantum?: number; cap?: number }): number {
  const quantum = options?.quantum ?? MOTION_STAGGER.quantum
  const cap = options?.cap ?? MOTION_STAGGER.cap
  return Math.min(Math.max(0, index) * quantum, cap)
}

/** Build a CSS transition string for a resolved move (spec §3.3). */
export function buildTransition(move: ResolvedMove, phase: MovePhase = 'enter'): string {
  const duration = phase === 'enter' ? move.duration : move.exitDuration
  const easing = phase === 'enter' ? move.easing : move.exitEasing
  return `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`
}
