import { describe, it, expect, afterEach } from 'vitest'
import {
  MOTION_DURATIONS,
  MOTION_EASINGS,
  MOTION_EXIT_SCALE,
  MOTION_PARALLAX,
  MOTION_STAGGER,
  getMotionTier,
  resolveMove,
  staggerDelay,
  buildTransition,
} from '../lib/motion/tokens'

afterEach(() => {
  delete document.documentElement.dataset.motionTier
})

describe('resolveMove — durations (spec §2.3/§3.1)', () => {
  it('picks the importance floor/middle/ceiling per distance class', () => {
    expect(resolveMove({ verb: 'slide', distance: 'D1', importance: 'I1' }).duration).toBe(75)
    expect(resolveMove({ verb: 'slide', distance: 'D2', importance: 'I2' }).duration).toBe(150)
    expect(resolveMove({ verb: 'slide', distance: 'D3', importance: 'I3' }).duration).toBe(260)
    expect(resolveMove({ verb: 'slide', distance: 'D4', importance: 'I3' }).duration).toBe(500)
  })

  it('applies verb defaults for distance', () => {
    expect(resolveMove({ verb: 'fade' }).duration).toBe(150) // fade → D2, I2
    expect(resolveMove({ verb: 'scale' }).duration).toBe(440) // scale → D4, I2
    expect(resolveMove({ verb: 'pulse' }).duration).toBe(90) // pulse → D1, I2
  })
})

describe('resolveMove — direction semantics (spec §2.2/§4.1)', () => {
  it('slides East: enter offset +X, exit reverses to -X', () => {
    const move = resolveMove({ verb: 'slide', direction: 'E', distance: 'D3' })
    expect(move.enter.transform).toBe('translate(16px, 0px)')
    expect(move.exit.transform).toBe('translate(-16px, 0px)')
    expect(move.travelPx).toBe(16)
  })

  it('slides North: enter offset -Y (settles from above)', () => {
    const move = resolveMove({ verb: 'slide', direction: 'N', distance: 'D1' })
    expect(move.enter.transform).toBe('translate(0px, -2px)')
    expect(move.exit.transform).toBe('translate(0px, 2px)')
  })

  it('slides South-East for corner toasts', () => {
    const move = resolveMove({ verb: 'slide', direction: 'SE', distance: 'D3' })
    expect(move.enter.transform).toBe('translate(16px, 16px)')
  })

  it('scales on Z with D4 using the modal 0.96 entry and 0.98 exit', () => {
    const move = resolveMove({ verb: 'scale', direction: 'Z', distance: 'D4' })
    expect(move.enter.transform).toBe('scale(0.96)')
    expect(move.exit.transform).toBe('scale(0.98)')
  })

  it('keeps the page slide deliberately small for D4 (spec §6.3)', () => {
    const move = resolveMove({ verb: 'slide', direction: 'E', distance: 'D4' })
    expect(move.travelPx).toBe(8)
  })

  it('uses enter easing for arrivals and exit easing for departures', () => {
    const move = resolveMove({ verb: 'slide', direction: 'E', distance: 'D3' })
    expect(move.easing).toBe(MOTION_EASINGS.enter)
    expect(move.exitEasing).toBe(MOTION_EASINGS.exit)
  })

  it('uses standard easing for non-spatial verbs', () => {
    const move = resolveMove({ verb: 'fade', distance: 'D2' })
    expect(move.easing).toBe(MOTION_EASINGS.standard)
    expect(move.enter.transform).toBe('none')
  })
})

describe('resolveMove — exit timing (spec §3.2 rule 5)', () => {
  it('exit duration is 0.7× enter, never below 75ms', () => {
    expect(resolveMove({ verb: 'slide', distance: 'D4', importance: 'I3' }).exitDuration).toBe(
      Math.max(75, Math.round(500 * MOTION_EXIT_SCALE))
    )
    expect(resolveMove({ verb: 'slide', distance: 'D1', importance: 'I1' }).exitDuration).toBe(75)
  })
})

describe('resolveMove — tiers (spec §8)', () => {
  it('efficient tier collapses to opacity-only, ≤75ms, no transform', () => {
    const move = resolveMove({ verb: 'slide', direction: 'E', distance: 'D3' }, 'efficient')
    expect(move.duration).toBeLessThanOrEqual(75)
    expect(move.enter.transform).toBe('none')
    expect(move.exit.transform).toBe('none')
    expect(move.travelPx).toBe(0)
    expect(move.scaleFrom).toBe(1)
  })

  it('minimal tier is instant and fade-only', () => {
    const move = resolveMove({ verb: 'slide', direction: 'E', distance: 'D4', importance: 'I3' }, 'minimal')
    expect(move.duration).toBe(0)
    expect(move.exitDuration).toBe(0)
    expect(move.enter).toEqual({ opacity: 0, transform: 'none' })
  })
})

describe('staggerDelay (spec §4.3)', () => {
  it('caps at 150ms with the 20ms quantum', () => {
    expect(staggerDelay(0)).toBe(0)
    expect(staggerDelay(5)).toBe(100)
    expect(staggerDelay(20)).toBe(150)
  })

  it('supports custom quantum/cap', () => {
    expect(staggerDelay(3, { quantum: 10, cap: 25 })).toBe(25)
  })
})

describe('buildTransition (spec §3.3)', () => {
  it('emits transform + opacity with the phase duration/easing', () => {
    const move = resolveMove({ verb: 'slide', direction: 'E', distance: 'D3' })
    expect(buildTransition(move, 'enter')).toBe(`transform ${move.duration}ms ${move.easing}, opacity ${move.duration}ms ${move.easing}`)
    expect(buildTransition(move, 'exit')).toBe(`transform ${move.exitDuration}ms ${move.exitEasing}, opacity ${move.exitDuration}ms ${move.exitEasing}`)
  })
})

describe('getMotionTier (spec §7)', () => {
  it('the data-motion-tier attribute wins over media queries', () => {
    document.documentElement.dataset.motionTier = 'precise'
    expect(getMotionTier()).toBe('precise')
    document.documentElement.dataset.motionTier = 'minimal'
    expect(getMotionTier()).toBe('minimal')
  })

  it('honours constants', () => {
    expect(MOTION_PARALLAX).toEqual({ overlay: 16, surface: 8, page: 4 })
    expect(MOTION_STAGGER).toEqual({ quantum: 20, cap: 150 })
    expect(MOTION_DURATIONS.slowest).toBe(500)
  })
})
