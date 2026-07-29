import { useRef, useState, useEffect, useCallback, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'

interface RouteTransitionProps {
  children: ReactNode
}

/**
 * Detects whether the browser supports the View Transitions API.
 * Excludes users who prefer reduced motion.
 */
function supportsViewTransition(): boolean {
  return (
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches &&
    typeof document !== 'undefined' &&
    typeof document.startViewTransition === 'function'
  )
}

export function RouteTransition({ children }: RouteTransitionProps) {
  const location = useLocation()
  const [displayChildren, setDisplayChildren] = useState(children)
  const [transitionState, setTransitionState] = useState<'entering' | 'exiting'>('entering')
  const prevLocationKeyRef = useRef(location.key)
  const cachedChildrenRef = useRef(children)
  const initializedRef = useRef(false)

  // Track the last animation frame ID for cleanup
  const animFrameRef = useRef<number | null>(null)

  // Store the latest location.key to avoid stale closures
  const latestLocationKeyRef = useRef(location.key)
  latestLocationKeyRef.current = location.key

  // On every render, keep cachedChildrenRef up to date with the current route's children.
  useEffect(() => {
    if (location.key === prevLocationKeyRef.current) {
      cachedChildrenRef.current = children
    }
  })

  // ── Route change handler ──
  const handleRouteChange = useCallback(
    (newChildren: ReactNode, newKey: string) => {
      const prevKey = prevLocationKeyRef.current

      // Attempt native View Transitions API
      if (supportsViewTransition()) {
        try {
          // Cast to access startViewTransition (TypeScript might not know it yet)
          const vt = (document as any).startViewTransition(() => {
            // flushSync forces React's concurrent rendering to complete synchronously
            // so the DOM update happens inside the view transition snapshot.
            flushSync(() => {
              setDisplayChildren(newChildren)
              cachedChildrenRef.current = newChildren
              setTransitionState('entering')
              prevLocationKeyRef.current = newKey
            })
          })

          // Cleanup if the transition is abandoned
          vt.finished.catch(() => {})
          return
        } catch {
          // View transition failed — fall through to fallback
        }
      }

      // ── Fallback: exit-before-enter animation ──
      setTransitionState('exiting')

      animFrameRef.current = window.setTimeout(() => {
        setDisplayChildren(newChildren)
        cachedChildrenRef.current = newChildren
        setTransitionState('entering')
        prevLocationKeyRef.current = newKey
      }, 200)
    },
    []
  )

  // ── Effect: react to route changes ──
  useEffect(() => {
    // First mount
    if (!initializedRef.current) {
      initializedRef.current = true
      setDisplayChildren(children)
      cachedChildrenRef.current = children
      setTransitionState('entering')
      prevLocationKeyRef.current = location.key
      return
    }

    // Route changed
    if (location.key !== prevLocationKeyRef.current) {
      handleRouteChange(children, location.key)
    }

    return () => {
      if (animFrameRef.current !== null) {
        clearTimeout(animFrameRef.current)
        animFrameRef.current = null
      }
    }
  }, [location.key, children, handleRouteChange])

  return (
    <div
      className={cn(
        transitionState === 'entering' ? 'animate-fade-in-up' : 'animate-fade-out-down'
      )}
      style={{
        // Assign a unique view-transition-name to the page content area
        viewTransitionName: 'page-content',
      }}
    >
      {displayChildren}
    </div>
  )
}
