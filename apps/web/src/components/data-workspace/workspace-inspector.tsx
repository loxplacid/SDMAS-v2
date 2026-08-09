import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import { cn } from '../../lib/utils'
import { useMove, buildTransition, type MoveSpec } from '../../lib/motion'
import { ErrorState } from '../ui'

/**
 * P9 — WorkspaceInspector: the contextual preview panel of a list workspace.
 *
 * The inspector is *not* an ordinary modal:
 *  - desktop (lg+): a non-modal right-side panel over the list. No backdrop,
 *    no scroll lock, no focus steal — the list stays interactive so the user
 *    can click another row and the preview follows (Linear-style inspector);
 *  - tablet/mobile (< lg): a full-screen sheet over the list (list → detail).
 *    Backdrop, scroll lock, focus into the panel, Escape closes, focus
 *    returns to the previously focused element.
 *
 * The shell owns presentation only — header identity, body content and footer
 * actions are props. Loading / error / empty states are built in so every
 * consumer gets the same async surface.
 *
 * Motion follows the Drawer choreography (slide E at `slow` in the precise
 * tier; opacity-only or instant under reduced-motion tiers via `useMove`).
 */

export interface WorkspaceInspectorProps {
  open: boolean
  onClose: () => void
  /** Accessible name — used for the panel's aria-label. */
  title: string
  /** Sticky header content (identity, badge, context). Close button added. */
  header?: ReactNode
  /** Scrollable body content. */
  children?: ReactNode
  /** Sticky footer actions (Open / Edit / …). */
  footer?: ReactNode
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  emptyMessage?: string
  /** Desktop panel width. Default `min(28rem, 100vw)`. */
  width?: string
  className?: string
}

/** Breakpoint at which the inspector becomes a non-modal side panel. */
const DESKTOP_QUERY = '(min-width: 1024px)'

function useIsDesktop(): boolean {
  const [matches, setMatches] = useState<boolean>(() =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(DESKTOP_QUERY).matches
      : true
  )

  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_QUERY)
    const onChange = () => setMatches(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return matches
}

export function WorkspaceInspector({
  open,
  onClose,
  title,
  header,
  children,
  footer,
  loading = false,
  error = null,
  onRetry,
  emptyMessage = 'Nothing to preview.',
  width = 'min(28rem, 100vw)',
  className,
}: WorkspaceInspectorProps) {
  const isDesktop = useIsDesktop()

  const panelRef = useRef<HTMLElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const closingRef = useRef(false)
  const exitTimerRef = useRef(0)

  // Choreography (Drawer, spec §6.9): a right inspector slides E at `slow`.
  // Memoized spec so a parent re-render never re-derives the move and snaps
  // the panel back to its off-canvas start frame.
  const panelSpec = useMemo<MoveSpec>(
    () => ({ verb: 'slide', direction: 'E', distance: 'D3', importance: 'I2' }),
    []
  )
  const backdropSpec = useMemo<MoveSpec>(
    () => ({ verb: 'fade', distance: 'D2', importance: 'I2' }),
    []
  )
  const panelMove = useMove(panelSpec)
  const backdropMove = useMove(backdropSpec)

  const [panelPhase, setPanelPhase] = useState<'start' | 'rest'>('start')
  const [backdropPhase, setBackdropPhase] = useState<'start' | 'rest'>('start')

  // Reduced tiers skip the spatial slide (§8): efficient may still fade,
  // minimal is instant. The precise tier gets the E rail move.
  const panelStyle: CSSProperties = {
    ...(isDesktop ? { width } : { width: '100%' }),
    ...(panelMove.tier === 'precise'
      ? panelPhase === 'start'
        ? { transform: 'translateX(100%)', opacity: 1, transition: 'none', willChange: 'transform' }
        : { transform: 'translateX(0)', opacity: 1, transition: buildTransition(panelMove.move, 'enter') }
      : { transform: 'translateX(0)', opacity: 1, transition: 'none' }),
  }

  const backdropStyle: CSSProperties =
    backdropMove.tier === 'minimal'
      ? { opacity: 1, transition: 'none' }
      : backdropPhase === 'start'
        ? { opacity: 0, transition: 'none' }
        : { opacity: 1, transition: buildTransition(backdropMove.move, 'enter') }

  // Exit is the reverse of entry at 0.7×: slide back to the edge (+ fade for
  // the mobile backdrop). Reduced tiers skip the spatial slide.
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
        el.style.transform = 'translateX(100%)'
      }
      el.style.opacity = '0'
      exitTimerRef.current = window.setTimeout(onDone, panelMove.move.exitDuration + 60)
    },
    [panelMove.move, panelMove.tier]
  )

  const handleClose = useCallback(() => {
    if (closingRef.current) return
    closingRef.current = true
    const done = () => {
      closingRef.current = false
      onClose()
    }
    exitPanel(done)
    if (!isDesktop) backdropMove.play(backdropRef.current, 'exit')
  }, [onClose, exitPanel, isDesktop, backdropMove.play])

  const handleCloseRef = useRef(handleClose)
  handleCloseRef.current = handleClose

  // Escape closes in both variants (spec §18).
  useEffect(() => {
    if (!open) return
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') handleCloseRef.current()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [open])

  // Enter choreography. Mobile only: scroll lock + focus into the panel,
  // restored on close. Keyed on `[open, tier, isDesktop]` — a parent re-render
  // must never re-run this and snap the panel back to its start frame.
  useEffect(() => {
    if (!open) return

    closingRef.current = false
    setPanelPhase('start')
    setBackdropPhase('start')

    if (!isDesktop) {
      previousFocusRef.current = document.activeElement as HTMLElement
      document.body.style.overflow = 'hidden'
      requestAnimationFrame(() => panelRef.current?.focus())
    }

    let cancelled = false
    let rafId = 0
    if (panelMove.tier === 'precise') {
      rafId = requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!cancelled && !closingRef.current) {
            setPanelPhase('rest')
            setBackdropPhase('rest')
          }
        })
      })
    } else {
      setPanelPhase('rest')
      setBackdropPhase('rest')
    }

    return () => {
      cancelled = true
      if (rafId) cancelAnimationFrame(rafId)
      window.clearTimeout(exitTimerRef.current)
      if (!isDesktop) {
        document.body.style.overflow = ''
        previousFocusRef.current?.focus()
      }
    }
  }, [open, panelMove.tier, isDesktop])

  // Gate purely on `open`: URL-driven closes (back navigation) flip `open`
  // without going through `handleClose`, so the panel must unmount then.
  // Exit animations play inside `handleClose` while `open` is still true.
  if (!open) return null

  const panelRole = isDesktop ? 'complementary' : 'dialog'

  return (
    <div
      className={cn(
        'fixed z-[var(--z-overlay)]',
        isDesktop ? 'inset-y-0 right-0' : 'inset-0 z-[var(--z-dialog)] flex justify-end'
      )}
    >
      {/* Backdrop — mobile sheet only; the desktop inspector is non-modal. */}
      {!isDesktop && (
        <div
          ref={backdropRef}
          data-workspace-inspector-backdrop=""
          className="absolute inset-0 bg-[var(--color-surface-overlay)] backdrop-blur-[3px]"
          style={backdropStyle}
          aria-hidden="true"
          onClick={() => handleCloseRef.current()}
        />
      )}

      <aside
        ref={panelRef}
        role={panelRole}
        aria-label={title}
        aria-modal={isDesktop ? undefined : true}
        tabIndex={-1}
        style={panelStyle}
        className={cn(
          'relative flex h-full flex-col bg-[var(--color-surface)] shadow-2xl',
          'focus-visible:outline-none',
          isDesktop ? 'border-l border-[var(--color-border)] rounded-l-2xl' : 'w-full rounded-none',
          className
        )}
      >
        {/* Sticky header */}
        <header className="flex items-start justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3 shrink-0">
          <div className="min-w-0 flex-1">
            {header ?? (
              <h2 className="truncate text-sm font-semibold text-[var(--color-text-primary)]">{title}</h2>
            )}
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close inspector"
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl text-[var(--color-text-tertiary)] motion-safe:transition-colors motion-safe:duration-[var(--motion-fast)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand-accent-ring)]"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div role="status" aria-label="Loading inspector" className="space-y-4 p-5">
              <div className="h-4 w-1/2 rounded bg-[var(--color-border)] animate-pulse" />
              <div className="h-16 rounded-xl bg-[var(--color-surface-hover)] animate-pulse" />
              <div className="h-24 rounded-xl bg-[var(--color-surface-hover)] animate-pulse" />
              <div className="h-20 rounded-xl bg-[var(--color-surface-hover)] animate-pulse" />
            </div>
          ) : error ? (
            <div className="p-4">
              <ErrorState message={error} onRetry={onRetry} />
            </div>
          ) : children === undefined ? (
            <div className="p-8 text-center text-sm text-[var(--color-text-tertiary)]">{emptyMessage}</div>
          ) : (
            children
          )}
        </div>

        {/* Sticky footer */}
        {footer && (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-3">
            {footer}
          </div>
        )}
      </aside>
    </div>
  )
}
