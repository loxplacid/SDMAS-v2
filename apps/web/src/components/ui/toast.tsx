import { useState, createContext, useContext, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { useMove } from '../../lib/motion'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: number
  message: string
  type: ToastType
  title?: string
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, title?: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

let toastId = 0

const config: Record<ToastType, { border: string; icon: string }> = {
  success: { border: 'border-l-[var(--color-success)]', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  error: { border: 'border-l-[var(--color-danger)]', icon: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z' },
  info: { border: 'border-l-[var(--color-brand-accent)]', icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  warning: { border: 'border-l-[var(--color-warning)]', icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z' },
}

const dotColor: Record<ToastType, string> = {
  success: 'bg-[var(--color-success)]',
  error: 'bg-[var(--color-danger)]',
  info: 'bg-[var(--color-brand-accent)]',
  warning: 'bg-[var(--color-warning)]',
}

/**
 * One toast (spec §6.9): `Slide S-East, D3, I2` — 16px, `slow`, enter curve,
 * staggered 20ms per sibling. Exit is the reverse of entry at 0.7× (module
 * rule §4.1), then the toast unmounts. Success toasts get one `Pulse` on the
 * status dot once the toast settles, then stillness (§4.5: one Pulse per
 * moment).
 */
function ToastItem({
  toast,
  index,
  leaving,
  onExitFinished,
  onDismiss,
}: {
  toast: Toast
  index: number
  leaving: boolean
  onExitFinished: (id: number) => void
  onDismiss: () => void
}) {
  const { ref, style, play, pulse } = useMove(
    { verb: 'slide', direction: 'SE', distance: 'D3', importance: 'I2' },
    { animateOnMount: true, staggerIndex: index }
  )
  // `useMove`'s ref is a callback ref; keep an object ref for the exit play.
  const itemRef = useRef<HTMLDivElement>(null)
  const dotRef = useRef<HTMLSpanElement>(null)
  const exitPlayedRef = useRef(false)

  // Stable composed ref — a fresh closure per render would make React
  // detach/reattach the ref on every ToastItem render.
  const setItemRef = useCallback(
    (el: HTMLDivElement | null) => {
      itemRef.current = el
      ref(el)
    },
    [ref]
  )

  // Success attention: one Pulse on the status mark after the entrance
  // settles (Glint §3.1 — draw the check, then a single settle pulse).
  useEffect(() => {
    if (toast.type !== 'success') return
    const t = window.setTimeout(() => pulse(dotRef.current), 320)
    return () => window.clearTimeout(t)
  }, [toast.type, pulse])

  // Exit choreography: reverse of entry at 0.7×, then unmount. The ref guard
  // keeps `play` identity changes (tier flips) from replaying the exit.
  useEffect(() => {
    if (!leaving || exitPlayedRef.current) return
    exitPlayedRef.current = true
    play(itemRef.current, 'exit', { onfinish: () => onExitFinished(toast.id) })
  }, [leaving, play, onExitFinished, toast.id])

  return (
    <div
      ref={setItemRef}
      style={style}
      className={cn(
        'pointer-events-auto flex items-start gap-3.5 pl-4 pr-3.5 py-3.5 bg-[var(--color-surface)] rounded-xl shadow-lg',
        'border border-[var(--color-border)]',
        config[toast.type].border,
        'border-l-[3px]'
      )}
      role="alert"
    >
      {toast.type === 'success' ? (
        <span
          ref={dotRef}
          className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center animate-check-settle"

          aria-hidden="true"
        >
          <svg className="h-3.5 w-3.5 text-[var(--color-success)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
            <path
              className="animate-draw-check"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray={24}
              strokeDashoffset={24}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </span>
      ) : (
        <span
          ref={dotRef}
          className={cn('h-2 w-2 rounded-full mt-1.5 flex-shrink-0', dotColor[toast.type])}
          aria-hidden="true"
        />
      )}
      <div className="flex-1 min-w-0">
        {toast.title && <p className="text-sm font-semibold text-[var(--color-text-primary)]">{toast.title}</p>}
        <p className="text-sm text-[var(--color-text-secondary)]">{toast.message}</p>
      </div>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 flex items-center justify-center h-6 w-6 rounded-lg hover:bg-[var(--color-surface-hover)] motion-safe:transition-colors text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
        aria-label="Dismiss"
      >
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [leavingIds, setLeavingIds] = useState<Set<number>>(new Set())

  const handleExitFinished = useCallback((id: number) => {
    setLeavingIds((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Mark a toast as leaving; the actual removal happens when its exit
  // choreography completes (ToastItem's onExitFinished).
  const removeWithAnim = useCallback((id: number) => {
    setLeavingIds((prev) => new Set(prev).add(id))
  }, [])

  const showToast = useCallback((message: string, type: ToastType = 'info', title?: string) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type, title }])
    window.setTimeout(() => removeWithAnim(id), 4000)
  }, [removeWithAnim])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none"
        aria-live="polite"
        aria-label="Notifications"
      >
        {toasts.map((toast, index) => (
          <ToastItem
            key={toast.id}
            toast={toast}
            index={index}
            leaving={leavingIds.has(toast.id)}
            onExitFinished={handleExitFinished}
            onDismiss={() => removeWithAnim(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
