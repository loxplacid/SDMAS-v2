import { useCallback, useState, type CSSProperties, type ReactNode, type Ref } from 'react'
import { useMotionTier } from './use-motion-tier'

/**
 * Glint §2.1 — the magnetic hover-pull (L1 flagship).
 *
 * A control translates a few pixels *toward the cursor* while the pointer is
 * inside it, and springs back on leave. Transform-only (compositor), clamped
 * to `MAGNET_MAX_PX` so the pull is felt, never followed. Legal only in the
 * `precise` motion tier — reduced tiers are inert (no listeners, no pull).
 *
 * The pull is applied to the element the hook returns a ref for. On
 * interactive surfaces whose own transform is owned by hover/active CSS
 * (Button, Card) apply it to an *inner* wrapper so the pull never fights the
 * component's own lift/scale — the magnetic element is the content, not the
 * frame.
 */

export const MAGNET_MAX_PX = 3

/** `--motion-base` × `--ease-spring-gentle` — quick to follow, soft to return. */
const MAGNET_TRANSITION = 'transform 180ms cubic-bezier(0.25, 1.3, 0.5, 1)'

export interface MagneticOptions {
  /** Pull radius in px. Default: 3 (spec §2.1: ±3px, never followed). */
  max?: number
  /** Disable the pull for this instance (e.g. dense rows). Default: false. */
  disabled?: boolean
}

export interface MagneticResult {
  /** Attach to the element that should pull. */
  ref: (el: HTMLElement | null) => void
  /** Inline style — the resting frame wires the spring return transition. */
  style: CSSProperties
}

export function useMagnetic(options: MagneticOptions = {}): MagneticResult {
  const { max = MAGNET_MAX_PX, disabled = false } = options
  // Reactive tier (same shared hook `useMove`/`frame.tsx` consume): a
  // mid-session reduced-motion flip detaches the listeners.
  const tier = useMotionTier()
  const enabled = !disabled && tier === 'precise'

  const onPointerMove = useCallback(
    (event: PointerEvent) => {
      const el = event.currentTarget as HTMLElement
      if (!el || event.pointerType === 'touch') return
      const rect = el.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const dx = event.clientX - cx
      const dy = event.clientY - cy
      const pullX = Math.max(-max, Math.min(max, dx))
      const pullY = Math.max(-max, Math.min(max, dy))
      el.style.transform = `translate(${pullX}px, ${pullY}px)`
    },
    [max]
  )

  const onPointerLeave = useCallback((event: PointerEvent) => {
    const el = event.currentTarget as HTMLElement
    if (!el) return
    el.style.transform = 'none'
  }, [])

  const ref = useCallback(
    (el: HTMLElement | null) => {
      if (!enabled || !el) return
      // Element-level leave — fires when the cursor leaves the element's
      // bounds, wherever it goes next (the pull must reset on mouse-out,
      // not only when the pointer exits the whole window).
      el.addEventListener('pointermove', onPointerMove)
      el.addEventListener('pointerleave', onPointerLeave)
      // Unsubscribe in the cleanup of the same callback ref: React fires the
      // old ref with null before the new ref with the element on re-render,
      // and with null on unmount.
      return () => {
        el.removeEventListener('pointermove', onPointerMove)
        el.removeEventListener('pointerleave', onPointerLeave)
      }
    },
    [enabled, onPointerMove, onPointerLeave]
  )

  return {
    ref,
    style: enabled ? { transition: MAGNET_TRANSITION } : {},
  }
}

/**
 * Convenience wrapper for components that want the pull without owning the
 * hook (e.g. Card's content region). Renders the children inside a block
 * span the pull is applied to — the span must be a *real box* (the pull
 * rect comes from its geometry; a `display: contents` span has none), so it
 * is `block` by default and layout-behaved like the div it replaces.
 */
export function Magnetic({
  children,
  max,
  disabled,
  style,
  className,
}: {
  children: ReactNode
  max?: number
  disabled?: boolean
  style?: CSSProperties
  className?: string
}) {
  const { ref, style: magneticStyle } = useMagnetic({ max, disabled })

  return (
    <span ref={ref} className={className} style={{ display: 'block', ...style, ...magneticStyle }}>
      {children}
    </span>
  )
}
