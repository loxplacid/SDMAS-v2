import { useEffect, useRef, useState, useMemo, type ReactNode, type MouseEvent, type CSSProperties, useCallback } from 'react'
import { cn } from '../../lib/utils'
import { useMove, buildTransition, type Direction } from '../../lib/motion'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  side?: 'right' | 'left'
  size?: 'sm' | 'md' | 'lg' | 'full'
  panelClassName?: string
  headerClassName?: string
}

const sizeClasses: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  full: 'max-w-full',
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  side = 'right',
  size = 'md',
  panelClassName,
  headerClassName,
}: DrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const [closing, setClosing] = useState(false)
  const [mounted, setMounted] = useState(false)
  const closingRef = useRef(false)
  const exitTimerRef = useRef(0)

  // Choreography (spec §6.9): a side drawer slides E (right side) / W (left)
  // at `slow`. The module resolves the clock — duration, easing, tier — and
  // the component supplies the frames: a side drawer's travel is its own
  // width, which the module's deliberately small slide classes don't express
  // (§6.3). Overlay is `Fade` at `base`.
  const direction: Direction = side === 'right' ? 'E' : 'W'
  // Memoized specs (as in CommandPalette/RouteTransition): a fresh spec object
  // would re-derive `move` → `play` → `handleClose` on every render, re-running
  // the enter effect and snapping the panel back to its off-canvas start frame
  // — a slide-in replay on any parent re-render, and a flash mid-exit.
  const panelSpec = useMemo(
    () => ({ verb: 'slide', direction, distance: 'D3', importance: 'I2' }) as const,
    [direction]
  )
  const overlaySpec = useMemo(
    () => ({ verb: 'fade', distance: 'D2', importance: 'I2' }) as const,
    []
  )
  const panelMove = useMove(panelSpec)
  const overlayMove = useMove(overlaySpec)

  const travel = side === 'right' ? '100%' : '-100%'
  const [panelPhase, setPanelPhase] = useState<'start' | 'rest'>('start')
  const [overlayPhase, setOverlayPhase] = useState<'start' | 'rest'>('start')

  // Reduced tiers: no spatial slide (§8). Efficient may still fade (opacity
  // is legal); minimal is instant. Precise gets the full E/W rail move.
  const panelStyle: CSSProperties =
    panelMove.tier === 'precise'
      ? panelPhase === 'start'
        ? { transform: `translateX(${travel})`, opacity: 1, transition: 'none', willChange: 'transform' }
        : { transform: 'translateX(0)', opacity: 1, transition: buildTransition(panelMove.move, 'enter') }
      : { transform: 'translateX(0)', opacity: 1, transition: 'none' }

  const overlayStyle: CSSProperties =
    overlayMove.tier === 'minimal'
      ? { opacity: 1, transition: 'none' }
      : overlayPhase === 'start'
        ? { opacity: 0, transition: 'none' }
        : { opacity: 1, transition: buildTransition(overlayMove.move, 'enter') }

  // Exit is the reverse of entry at 0.7×: slide back to the edge + fade.
  // Reduced tiers skip the spatial slide (fade at the resolved 75ms clock in
  // efficient; instant in minimal).
  const exitPanel = useCallback(
    (onDone: () => void) => {
      const el = panelRef.current
      if (!el) {
        onDone()
        return
      }
      if (panelMove.tier === 'minimal') {
        onDone()
        return
      }
      window.clearTimeout(exitTimerRef.current)
      el.style.transition = buildTransition(panelMove.move, 'exit')
      if (panelMove.tier === 'precise') {
        el.style.transform = `translateX(${travel})`
      }
      el.style.opacity = '0'
      exitTimerRef.current = window.setTimeout(onDone, panelMove.move.exitDuration + 60)
    },
    [panelMove.move, panelMove.tier, travel]
  )

  const handleClose = useCallback(() => {
    if (closingRef.current) return
    closingRef.current = true
    setClosing(true)
    const done = () => {
      closingRef.current = false
      setClosing(false)
      setMounted(false)
      onClose()
    }
    exitPanel(done)
    overlayMove.play(backdropRef.current, 'exit')
  }, [onClose, exitPanel, overlayMove.play])

  // Latest close handler via ref — lets the Escape listener stay mounted
  // regardless of the parent's `onClose` identity changing between renders.
  const handleCloseRef = useRef(handleClose)
  handleCloseRef.current = handleClose

  // Escape handling (spec §6.1): keyed on `open` only.
  useEffect(() => {
    if (!open) return
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') handleCloseRef.current()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [open])

  // Enter choreography + focus/scroll-lock. Keyed on `[open, tier]` only: a
  // parent's fresh `onClose` (or any unrelated re-render) must never re-run
  // this and snap the panel back to its off-canvas start frame — the enter
  // plays once per open, not once per render.
  useEffect(() => {
    if (!open) return

    setMounted(true)
    setClosing(false)
    closingRef.current = false
    setPanelPhase('start')
    setOverlayPhase('start')
    previousFocusRef.current = document.activeElement as HTMLElement
    document.body.style.overflow = 'hidden'
    requestAnimationFrame(() => panelRef.current?.focus())

    // Commit the off-canvas frame, then flip to rest so the CSS transition
    // plays the E/W slide at `slow`. Reduced tiers flip synchronously
    // (their styles are tier-gated, so no motion plays).
    let cancelled = false
    let rafId = 0
    if (panelMove.tier === 'precise') {
      rafId = requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!cancelled && !closingRef.current) {
            setPanelPhase('rest')
            setOverlayPhase('rest')
          }
        })
      })
    } else {
      setPanelPhase('rest')
      setOverlayPhase('rest')
    }

    return () => {
      cancelled = true
      if (rafId) cancelAnimationFrame(rafId)
      window.clearTimeout(exitTimerRef.current)
      document.body.style.overflow = ''
      previousFocusRef.current?.focus()
    }
  }, [open, panelMove.tier])

  if (!mounted && !open) return null

  const handleOverlayClick = (e: MouseEvent) => {
    if (e.target === overlayRef.current && !closingRef.current) handleClose()
  }

  return (
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 z-[var(--z-dialog)] flex',
        side === 'right' ? 'justify-end' : 'justify-start'
      )}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
    >
      {/* Backdrop */}
      <div
        ref={backdropRef}
        className="fixed inset-0 bg-[var(--color-surface-overlay)] backdrop-blur-[3px]"
        style={overlayStyle}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        tabIndex={-1}
        style={panelStyle}
        className={cn(
          'relative w-full h-full shadow-2xl',
          'flex flex-col',
          'focus-visible:outline-none',
          sizeClasses[size],
          side === 'right' ? 'rounded-l-2xl' : 'rounded-r-2xl',
          panelClassName || 'bg-[var(--color-surface)]'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-divider)] shrink-0">
          <h2
            id="drawer-title"
            className={cn(
              'text-lg font-semibold leading-snug',
              headerClassName || 'text-[var(--color-text-primary)]'
            )}
          >
            {title}
          </h2>
          <button
            onClick={handleClose}
            className={cn(
              'flex items-center justify-center h-8 w-8 rounded-xl motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)]',
              headerClassName
                ? 'text-white/60 hover:text-white hover:bg-white/10'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]'
            )}
            aria-label="Close drawer"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--color-divider)] bg-[var(--color-bg)] shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
