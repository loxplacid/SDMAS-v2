import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useLocation, useNavigationType } from 'react-router-dom'
import { useMove, type Direction } from '../../lib/motion'

interface RouteTransitionProps {
  children: ReactNode
}

/**
 * Route transition (spec §6.3): the arriving page is `Slide E + Fade, D4, I3`
 * — 500ms, 8px travel, enter curve; the departing page slides W 8px + fades
 * at 0.7× (≈350ms), exit curve. Back navigation is the exact reverse (W
 * arrival), never a fresh E enter.
 *
 * Prefers the native View Transitions API: the wrapper carries
 * `view-transition-name: page-content`, and the snapshot pair is animated by
 * the `::view-transition-*` CSS in index.css (same tokens). When the API is
 * unavailable — or the active motion tier is below `precise` (the tier system
 * already folds `prefers-reduced-motion` into `efficient`/`minimal`) — the
 * exit-before-enter fallback runs on `useMove`'s WAAPI choreography.
 */
export function RouteTransition({ children }: RouteTransitionProps) {
  const location = useLocation()
  const navigationType = useNavigationType()

  const [displayChildren, setDisplayChildren] = useState(children)
  const prevLocationKeyRef = useRef(location.key)
  const initializedRef = useRef(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const animatingRef = useRef(false)
  const pendingRef = useRef<{ children: ReactNode; key: string } | null>(null)

  // E = forward (PUSH), W = back (POP) — spec §2.2. The spec object is
  // memoized so the resolved move (and `play`) stays referentially stable.
  const direction: Direction = navigationType === 'POP' ? 'W' : 'E'
  const pageSpec = useMemo(
    () => ({ verb: 'slide', direction, distance: 'D4', importance: 'I3' }) as const,
    [direction]
  )
  const pageMove = useMove(pageSpec)

  const commitPending = useCallback(() => {
    const pending = pendingRef.current
    if (!pending) return
    pendingRef.current = null
    setDisplayChildren(pending.children)
    prevLocationKeyRef.current = pending.key
    const el = wrapperRef.current
    if (el && typeof el.animate !== 'function') {
      // No WAAPI (jsdom/legacy engines): the module's CSS-fallback play()
      // parks the element on the target frame and never returns it to rest
      // — so the enter frame (opacity 0) would leave the new page invisible.
      // A plain swap after the exit fade is the correct fallback behavior.
      el.style.transition = 'none'
      el.style.opacity = '1'
      el.style.transform = 'none'
      return
    }
    // Enter the new page on the same node: exit left it at the exit frame.
    pageMove.play(el, 'enter')
  }, [pageMove.play])

  const handleRouteChange = useCallback(
    (newChildren: ReactNode, newKey: string) => {
      // Native View Transitions API path (spec §12). Only in the precise
      // tier: `efficient`/`minimal` fold reduced-motion preferences in, and
      // the fallback below honours them via `useMove` automatically.
      if (
        pageMove.tier === 'precise' &&
        typeof document !== 'undefined' &&
        typeof document.startViewTransition === 'function'
      ) {
        try {
          const vt = (document as any).startViewTransition(() => {
            // flushSync forces React's concurrent render to complete
            // synchronously so the DOM update happens inside the snapshot.
            flushSync(() => {
              setDisplayChildren(newChildren)
              prevLocationKeyRef.current = newKey
            })
          })
          // Cleanup if the transition is abandoned
          vt.finished.catch(() => {})
          return
        } catch {
          // View transition failed — fall through to the fallback
        }
      }

      // Fallback: exit-before-enter on the same node (spec §4.1).
      pendingRef.current = { children: newChildren, key: newKey }
      if (animatingRef.current) return // in-flight exit commits the latest pending
      animatingRef.current = true
      pageMove.play(wrapperRef.current, 'exit', {
        onfinish: () => {
          animatingRef.current = false
          commitPending()
        },
      })
    },
    [pageMove.tier, pageMove.play, commitPending]
  )

  useEffect(() => {
    // First mount
    if (!initializedRef.current) {
      initializedRef.current = true
      setDisplayChildren(children)
      prevLocationKeyRef.current = location.key
      return
    }

    // Route changed
    if (location.key !== prevLocationKeyRef.current) {
      handleRouteChange(children, location.key)
    }
  }, [location.key, children, handleRouteChange])

  return (
    <div
      ref={wrapperRef}
      style={{ ...pageMove.style, viewTransitionName: 'page-content' }}
    >
      {displayChildren}
    </div>
  )
}
